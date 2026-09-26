from __future__ import annotations

import gc
from dataclasses import dataclass

import numpy as np

from .clean import _fold
from .config import settings
from .schemas import Hypothesis
from .local import pick_device, require_local_path


@dataclass
class AsrChunk:
    start: float
    end: float
    text: str
    language: str | None
    hypotheses: list[Hypothesis]


def rank_languages(probs: list[tuple[str, float]], allowed: tuple[str, ...]) -> list[tuple[str, float]]:
    """Keep only the meeting's languages and renormalize, best first."""
    kept = [(lang, p) for lang, p in probs if lang in allowed]
    total = sum(p for _, p in kept) or 1.0
    return sorted(((lang, p / total) for lang, p in kept), key=lambda item: item[1], reverse=True)


# Subtitle credits Whisper learned from web video; it emits them on noise.
_HALLUCINATIONS = {
    "продолжение следует",
    "субтитры сделал dimatorzok",
    "субтитры создавал dimatorzok",
    "спасибо за просмотр",
    "să vă mulțumim",
    "vă mulțumim pentru vizionare",
    "nu uitați să vă abonați",
    "nu uitați să dați like să lăsați un comentariu și să distribuiți acest video",
    "thank you for watching",
    "thanks for watching",
    "спасибо что вы посетили",
    "спасибо за внимание",
}
_HALLUCINATION_MAX_WORDS = 12  # a long real sentence may quote one of these; a short line is the credit itself


def _is_hallucination(text: str) -> bool:
    folded = _fold(text)
    return len(folded.split()) <= _HALLUCINATION_MAX_WORDS and any(p in folded for p in _HALLUCINATIONS)


class WhisperAsr:
    def __init__(self) -> None:
        from faster_whisper import WhisperModel

        model_dir = require_local_path(settings.asr_model_dir, "Whisper model dir")
        self.device = pick_device(settings.device)
        self.model_id = str(model_dir)
        self._model = WhisperModel(
            self.model_id,
            device=self.device,
            compute_type=settings.asr_compute_type,
            cpu_threads=settings.cpu_threads,
        )
        if settings.asr_joint_languages:
            _use_joint_language_tokens(settings.asr_joint_languages)

    def transcribe_batch(
        self, samples: np.ndarray, prev_lang: str | None = None
    ) -> tuple[str, str | None, list[Hypothesis]]:
        samples = samples.astype(np.float32)
        if settings.asr_joint_languages:  # one decode, prompted with every language token
            text, _, score, words = self._decode(samples, settings.asr_joint_languages[0])
            cyr = sum("Ѐ" <= c <= "ӿ" for c in text) > len(text) / 2
            language = "ru" if cyr else settings.asr_joint_languages[0]
            return text, language, [Hypothesis(language=language, text=text, score=score, words=words, source="whisper-joint")] if text else []
        if prev_lang and samples.size < settings.min_lid_s * settings.sample_rate:
            languages = [prev_lang]
        else:
            languages = self._languages(samples)
        return _pick([self._decode(samples, lang) for lang in languages])

    def _languages(self, samples: np.ndarray) -> list[str]:
        """Always the home languages; plus the detector's top pick among the meeting's languages."""
        if samples.size < settings.min_lid_s * settings.sample_rate:
            return list(settings.asr_always_decode)
        return _with_detected(self._model.detect_language(samples)[2])

    def _languages_batched(self, samples: list[np.ndarray]) -> list[list[str]]:
        """_languages for many clips: the encoder and language detector run on up to asr_batch_size
        clips per GPU call instead of one."""
        from faster_whisper.audio import pad_or_trim

        fe = self._model.feature_extractor
        out = [list(settings.asr_always_decode) for _ in samples]
        todo = [i for i, x in enumerate(samples) if x.size >= settings.min_lid_s * settings.sample_rate]
        for k in range(0, len(todo), settings.asr_batch_size):
            idx = todo[k : k + settings.asr_batch_size]
            feats = np.stack([pad_or_trim(fe(samples[i][: fe.n_samples])) for i in idx])
            for i, res in zip(idx, self._model.model.detect_language(self._model.encode(feats))):
                out[i] = _with_detected([(token[2:-2], prob) for token, prob in res])
        return out

    def transcribe_all(self, batches) -> list[AsrChunk]:
        """Every utterance at once: one batched GPU pass per language instead of one call per
        utterance and language. Same languages, scores and pick as transcribe_batch, except that
        a clip too short for LID gets the home languages rather than the previous clip's."""
        from faster_whisper import BatchedInferencePipeline

        batches = list(batches)
        samples = [b.samples.astype(np.float32) for b in batches]
        wanted = self._languages_batched(samples)
        gap = np.zeros(settings.sample_rate, np.float32)  # 1 s between clips: a segment maps to one clip unambiguously
        audio = np.concatenate([part for x in samples for part in (x, gap)]) if samples else gap
        starts = np.cumsum([0] + [x.size + gap.size for x in samples[:-1]]) / settings.sample_rate
        pipeline = BatchedInferencePipeline(model=self._model)
        results: list[list[tuple]] = [[] for _ in batches]
        for lang in dict.fromkeys(lang for langs in wanted for lang in langs):
            idx = [i for i, langs in enumerate(wanted) if lang in langs]
            clips = [{"start": starts[i], "end": starts[i] + samples[i].size / settings.sample_rate} for i in idx]
            segments, _ = pipeline.transcribe(
                audio,
                language=lang,
                task="transcribe",
                beam_size=settings.asr_beam_size,
                condition_on_previous_text=False,
                clip_timestamps=clips,
                batch_size=settings.asr_batch_size,
                word_timestamps=settings.cs_merge,
            )
            clip_starts = [c["start"] for c in clips]
            per_clip: dict[int, list] = {i: [] for i in idx}
            for seg in segments:
                per_clip[idx[max(0, int(np.searchsorted(clip_starts, seg.start + 1e-3)) - 1)]].append(seg)
            for i, segs in per_clip.items():
                results[i].append(_score(segs, lang, offset=starts[i]))
        chunks = []
        for b, res in zip(batches, results):
            text, language, hypotheses = _pick(res)
            chunks.append(AsrChunk(start=b.start, end=b.end, text=text, language=language, hypotheses=hypotheses))
        return chunks

    def _decode(self, samples: np.ndarray, language: str) -> tuple[str, str, float, list]:
        """Text in one forced language, scored by duration-weighted avg_logprob."""
        segments, _ = self._model.transcribe(
            samples,
            language=language,
            task="transcribe",
            beam_size=settings.asr_beam_size,
            condition_on_previous_text=False,
            vad_filter=False,
            word_timestamps=settings.cs_merge,
        )
        return _score(segments, language)

    def close(self) -> None:
        self._model = None
        gc.collect()


def _with_detected(probs: list[tuple[str, float]]) -> list[str]:
    languages = list(settings.asr_always_decode)
    ranked = rank_languages(probs, settings.asr_languages)
    if ranked and ranked[0][0] not in languages:
        languages.append(ranked[0][0])
    return languages


def _score(segments, language: str, offset: float = 0.0) -> tuple[str, str, float, list]:
    """Text in one forced language, scored by duration-weighted avg_logprob. Word times are
    made clip-relative (offset = the clip's start in a batched decode)."""
    # Whisper's own silence rule, applied per utterance.
    kept = [
        s
        for s in segments
        if not (s.no_speech_prob > 0.6 and s.avg_logprob < -1.0) and not _is_hallucination(s.text)
    ]
    if not kept:
        return "", language, float("-inf"), []
    weights = [max(s.end - s.start, 1e-3) for s in kept]
    score = sum(s.avg_logprob * w for s, w in zip(kept, weights)) / sum(weights)
    words = [(w.start - offset, w.end - offset, w.word.strip(), w.probability) for s in kept for w in (getattr(s, "words", None) or [])]
    return " ".join(s.text.strip() for s in kept).strip(), language, score, words


def _pick(results: list[tuple]) -> tuple[str, str | None, list[Hypothesis]]:
    """The best-scoring language's text (home language favoured on close calls), merged with
    confident runs from the other decodes when settings.cs_merge is on."""
    text, language, _, _ = max(results, key=_biased_score)
    hypotheses = [Hypothesis(language=lang, text=t, score=s, words=w) for t, lang, s, w in results if t]
    if settings.cs_merge and len(hypotheses) > 1:
        best = next(h for h in hypotheses if h.language == language)
        merged, switched = merge_words(best, [h for h in hypotheses if h is not best])
        if switched:
            return merged, f"{language}+{'+'.join(switched)}", hypotheses
    return text, language, hypotheses


def _use_joint_language_tokens(languages: tuple[str, ...]) -> None:
    """Prompt Whisper with several language tokens at once (<|ro|><|ru|>) instead of one.
    Concatenated language tokens were reported to help code-switched speech zero-shot
    (Peng et al. 2023, arXiv:2305.11095). Patches faster-whisper's start-of-transcript
    sequence for this process."""
    from faster_whisper import tokenizer as fw

    def sot_sequence(self) -> list[int]:
        ids = [self.tokenizer.token_to_id(f"<|{lang}|>") for lang in languages]
        return [self.sot, *ids, *([self.task] if self.task is not None else [])]

    fw.Tokenizer.sot_sequence = property(sot_sequence)


def _biased_score(result: tuple) -> float:
    _, language, score, _ = result
    return score + (settings.home_bias if language == settings.home_language else 0.0)


def _script_ok(word: str, language: str) -> bool:
    letters = [c for c in word if c.isalpha()]
    cyr = sum("\u0400" <= c <= "\u04ff" for c in letters)
    return bool(letters) and (cyr == len(letters) if language == "ru" else cyr == 0)


def merge_words(best: Hypothesis, others: list[Hypothesis]) -> tuple[str, list[str]]:
    """Winner's words, with runs from another language's decode swapped in where that decode
    was clearly more confident over the same time span and wrote the run in its own script.
    Two monolingual decodes chosen per span by confidence, as in Weiner et al. 2021 (arXiv:2109.00921)."""
    words = list(best.words)
    switched: list[str] = []

    def beats(w) -> bool:  # this word, in its own script, clearly above the winner's words it overlaps
        inside = [x[3] for x in best.words if x[1] > w[0] and x[0] < w[1]]
        return _script_ok(w[2], other.language) and w[3] >= (sum(inside) / len(inside) if inside else 0.0) + settings.cs_margin

    for other in others:
        run: list[tuple[float, float, str, float]] = []
        for w in list(other.words) + [None]:
            if w is not None and beats(w):
                run.append(w)
                continue
            if len(run) >= settings.cs_min_words:
                t0, t1 = run[0][0], run[-1][1]
                words = sorted([x for x in words if not (x[1] > t0 and x[0] < t1)] + run, key=lambda x: x[0])
                if other.language not in switched:
                    switched.append(other.language)
            run = []
    return " ".join(w[2] for w in words), switched


def transcribe_batches(engine: WhisperAsr, batches) -> list[AsrChunk]:
    batched = settings.asr_batch_size > 1 and not settings.asr_joint_languages
    if isinstance(engine, WhisperAsr) and engine.device == "cuda" and batched:
        return engine.transcribe_all(batches)
    chunks: list[AsrChunk] = []
    language: str | None = None
    for batch in batches:
        text, language, hypotheses = engine.transcribe_batch(batch.samples, language)
        chunks.append(AsrChunk(start=batch.start, end=batch.end, text=text, language=language, hypotheses=hypotheses))
    return chunks
