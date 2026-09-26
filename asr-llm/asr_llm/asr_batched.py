"""Many utterances per GPU call, same answers as one at a time.

WhisperAsr.transcribe_batch decodes one utterance at a time: detect the
language, then one faster-whisper transcribe per candidate language, each
encoding the audio again. On an hour of meeting that leaves the GPU mostly
idle (23 min on a T4). Here each utterance is encoded once, the encoding is
shared by language detection and every decode, and decodes run in batches.

Each decode repeats what faster-whisper's transcribe does for one 30-second
window at temperature 0 (same prompt, beam, penalties, suppressed tokens,
no-speech skip and segment split). Where faster-whisper would go further,
retrying at a higher temperature or decoding a second window, the utterance
is decoded again the old way, so those answers are unchanged too.
"""

from __future__ import annotations

import numpy as np

from .config import settings

# faster-whisper's TranscriptionOptions defaults, which WhisperAsr._decode uses.
BEAM, PATIENCE, LENGTH_PENALTY = 5, 1.0, 1.0
COMPRESSION_MAX, LOGPROB_MIN, NO_SPEECH = 2.4, -1.0, 0.6
MAX_INITIAL_TIMESTAMP_S = 1.0


def short_languages(short: list[bool], winners: dict[int, str]) -> dict[int, str]:
    """A short utterance is decoded only in the language the previous one came out in,
    as transcribe_batch's prev_lang does: that is the nearest earlier long one's winner."""
    out, last = {}, None
    for i, is_short in enumerate(short):
        if i in winners:
            last = winners[i]
        elif is_short and last is not None:
            out[i] = last
    return out


def split_window(tokens: list[int], ts_begin: int, content_frames: int, input_stride: int = 2) -> tuple[list[tuple[int, int, list[int]]], bool]:
    """faster-whisper's _split_segments_by_timestamps for a window at seek 0.
    Returns (start, end, tokens) per segment in timestamp positions, and whether the
    window covered the whole utterance (False: faster-whisper would decode another window)."""
    single_ending = len(tokens) >= 2 and tokens[-2] < ts_begin <= tokens[-1]
    consecutive = [i for i in range(1, len(tokens)) if tokens[i] >= ts_begin and tokens[i - 1] >= ts_begin]
    if not consecutive:
        stamps = [t for t in tokens if t >= ts_begin]
        end = stamps[-1] - ts_begin if stamps and stamps[-1] != ts_begin else None
        return [(0, end if end is not None else -1, tokens)], True
    slices = consecutive + ([len(tokens)] if single_ending else [])
    segments, last = [], 0
    for cut in slices:
        part = tokens[last:cut]
        segments.append((part[0] - ts_begin, part[-1] - ts_begin, part))
        last = cut
    if single_ending:
        return segments, True
    seek = (tokens[last - 1] - ts_begin) * input_stride
    return segments, seek >= content_frames


class BatchedDecoder:
    def __init__(self, whisper, batch_size: int) -> None:
        from faster_whisper.tokenizer import Tokenizer
        from faster_whisper.transcribe import get_compression_ratio, get_suppressed_tokens

        self.fw = whisper                       # faster_whisper.WhisperModel
        self.batch = max(1, batch_size)
        self.compression = get_compression_ratio
        self.tokenizers = {}
        self._tok = lambda lang: self.tokenizers.setdefault(
            lang, Tokenizer(whisper.hf_tokenizer, whisper.model.is_multilingual, task="transcribe", language=lang))
        self.suppress = list(get_suppressed_tokens(self._tok("en"), [-1]))
        self.max_initial = int(round(MAX_INITIAL_TIMESTAMP_S / whisper.time_precision))
        # "all": every decode faster-whisper would retry goes the old way (identical answers).
        # "loops": only repetition loops do; a quiet, low-confidence decode is kept as it is,
        # which is what faster-whisper's own batched pipeline does. Far-field audio is mostly
        # low-confidence, and the old way decodes it up to five more times.
        self.retry = settings.asr_retry
        self.stats = {"decodes": 0, "retried": 0, "second_window": 0}

    def features(self, samples: np.ndarray) -> tuple[np.ndarray, int]:
        from faster_whisper.audio import pad_or_trim

        feats = self.fw.feature_extractor(samples.astype(np.float32))
        frames = feats.shape[-1] - 1
        return pad_or_trim(feats[:, :frames]), frames

    def encode(self, feats: list[np.ndarray]) -> np.ndarray:
        """Encoder output on the CPU, so rows can be shared between decodes."""
        from faster_whisper.transcribe import get_ctranslate2_storage

        out = self.fw.model.encode(get_ctranslate2_storage(np.stack(feats)), to_cpu=True)
        return np.array(out)

    def detect(self, encoded: np.ndarray) -> list[list[tuple[str, float]]]:
        from faster_whisper.transcribe import get_ctranslate2_storage

        results = self.fw.model.detect_language(get_ctranslate2_storage(encoded))
        return [[(token[2:-2], p) for token, p in r] for r in results]

    def decode(self, encoded: np.ndarray, languages: list[str], frames: list[int]) -> list[tuple[str, float] | None]:
        """(text, score) per row as WhisperAsr._decode would give it, or None where
        faster-whisper would retry or read on, so the caller decodes that one the old way."""
        from faster_whisper.transcribe import get_ctranslate2_storage

        from .asr import _is_hallucination

        prompts = [self._tok(lang).sot_sequence for lang in languages]
        results = self.fw.model.generate(
            get_ctranslate2_storage(encoded), prompts, beam_size=BEAM, patience=PATIENCE,
            length_penalty=LENGTH_PENALTY, repetition_penalty=1.0, no_repeat_ngram_size=0,
            max_length=self.fw.max_length, return_scores=True, return_no_speech_prob=True,
            suppress_blank=True, suppress_tokens=self.suppress, max_initial_timestamp_index=self.max_initial)
        out: list[tuple[str, float] | None] = []
        for lang, n_frames, r in zip(languages, frames, results):
            tok = self._tok(lang)
            tokens = r.sequences_ids[0]
            avg = r.scores[0] * (len(tokens) ** LENGTH_PENALTY) / (len(tokens) + 1)
            self.stats["decodes"] += 1
            silence = r.no_speech_prob > NO_SPEECH and avg < LOGPROB_MIN
            loop = self.compression(tok.decode(tokens).strip()) > COMPRESSION_MAX
            if not silence and (loop or (avg < LOGPROB_MIN and self.retry == "all")):
                self.stats["retried"] += 1
                out.append(None)             # faster-whisper retries at a higher temperature
                continue
            if r.no_speech_prob > NO_SPEECH and not avg > LOGPROB_MIN:
                out.append(("", float("-inf")))   # the window is skipped as silence
                continue
            segments, complete = split_window(tokens, tok.timestamp_begin, n_frames)
            if not complete:
                self.stats["second_window"] += 1
                out.append(None)             # faster-whisper decodes a second window
                continue
            texts = [tok.decode(t) for s, e, t in segments if s != e]
            kept = [t.strip() for t in texts if t.strip() and not _is_hallucination(t)]
            out.append((" ".join(kept).strip(), avg) if kept else ("", float("-inf")))
        return out

    def run(self, pieces: list[np.ndarray], fixed: dict[int, list[str]], decide, fallback) -> list[dict[str, tuple[str, float]]]:
        """{language: (text, score)} per piece. Pieces in fixed decode those languages; the
        rest are language-detected and decode the languages decide(probs) names."""
        out: list[dict[str, tuple[str, float]]] = [{} for _ in pieces]
        for start in range(0, len(pieces), self.batch):
            idx = list(range(start, min(start + self.batch, len(pieces))))
            feats = [self.features(pieces[i]) for i in idx]
            encoded = self.encode([f for f, _ in feats])
            wanted = [fixed.get(i) for i in idx]
            lid = [k for k, w in enumerate(wanted) if w is None]
            if lid:
                for k, probs in zip(lid, self.detect(encoded[lid])):
                    wanted[k] = decide(probs)
            rows = [(k, lang) for k, langs in enumerate(wanted) for lang in langs]
            for s in range(0, len(rows), self.batch):
                part = rows[s:s + self.batch]
                got = self.decode(encoded[[k for k, _ in part]], [lang for _, lang in part], [feats[k][1] for k, _ in part])
                for (k, lang), res in zip(part, got):
                    out[idx[k]][lang] = res if res is not None else fallback(pieces[idx[k]], lang)
        return out
