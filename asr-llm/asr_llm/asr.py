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
    "nu uitați să dați like",
    "vă abonați la canalul",
    "thank you for watching",
    "thanks for watching",
    "спасибо что вы посетили",
    "спасибо за внимание",
}
_HALLUCINATION_MAX_WORDS = 12  # a long real sentence may quote one of these; a short line is the credit itself
_HALLUCINATION_PREFIX_WORDS = 4  # a line that opens with a credit this long is the credit, however long it runs


def _is_hallucination(text: str) -> bool:
    folded = _fold(text)
    if any(folded.startswith(p) for p in _HALLUCINATIONS if len(p.split()) >= _HALLUCINATION_PREFIX_WORDS):
        return True
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
        # Word timings and joint language tokens only exist on the one-at-a-time path.
        self.batched = settings.asr_batch_size > 1 and not settings.cs_merge and not settings.asr_joint_languages

    def _languages(self, probs: list[tuple[str, float]], always: list[str] | None = None) -> list[str]:
        languages = list(settings.asr_always_decode if always is None else always)
        ranked = rank_languages(probs, settings.asr_languages)
        if ranked and ranked[0][0] not in languages:
            languages.append(ranked[0][0])
        return languages or [settings.home_language]

    def transcribe_all(self, pieces: list[np.ndarray]) -> list[tuple[str, str | None, list[Hypothesis]]]:
        """transcribe_batch over every piece in order, with the GPU work batched (asr_batched.py)."""
        from .asr_batched import BatchedDecoder, kept_languages, short_languages

        decoder = BatchedDecoder(self._model, settings.asr_batch_size)

        def fallback(samples: np.ndarray, lang: str) -> tuple[str, float]:
            text, _, score, _ = self._decode(samples, lang)
            return text, score

        short = [p.size < settings.min_lid_s * settings.sample_rate for p in pieces]
        lead = [i for i in range(len(pieces)) if i == 0 or not short[i]]
        probe = lead[:settings.asr_probe_pieces] if settings.asr_adaptive_languages else lead
        found = dict(zip(probe, decoder.run([pieces[i] for i in probe], {}, self._languages, fallback)))
        self.meeting_languages = list(settings.asr_always_decode)
        rest = lead[len(probe):]
        if rest:
            always = kept_languages([pick_language(found[i])[1] for i in probe])
            self.meeting_languages = always
            decoder.stats["always_decoded_after_probe"] = len(always)
            found.update(zip(rest, decoder.run([pieces[i] for i in rest], {}, lambda p: self._languages(p, always), fallback)))
        winners = {i: pick_language(found[i])[1] for i in lead}
        shorts = short_languages(short, winners)
        order = sorted(shorts)
        for i, got in zip(order, decoder.run([pieces[i] for i in order], {k: [shorts[i]] for k, i in enumerate(order)}, self._languages, fallback)):
            found[i] = got
        self.batch_stats = decoder.stats
        out = []
        for i in range(len(pieces)):
            text, language = pick_language(found[i])
            hypotheses = [Hypothesis(language=lang, text=t, score=sc, words=[]) for lang, (t, sc) in found[i].items() if t]
            out.append((text, language, hypotheses))
        return out

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
            languages = list(settings.asr_always_decode)
            _, _, probs = self._model.detect_language(samples)
            ranked = rank_languages(probs, settings.asr_languages)
            if ranked and ranked[0][0] not in languages:
                languages.append(ranked[0][0])
        results = [self._decode(samples, lang) for lang in languages]
        text, language = pick_language({lang: (t, sc) for t, lang, sc, _ in results})
        hypotheses = [Hypothesis(language=lang, text=t, score=s, words=w) for t, lang, s, w in results if t]
        if settings.cs_merge and len(hypotheses) > 1:
            best = next(h for h in hypotheses if h.language == language)
            merged, switched = merge_words(best, [h for h in hypotheses if h is not best])
            if switched:
                return merged, f"{language}+{'+'.join(switched)}", hypotheses
        return text, language, hypotheses

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
        words = [(w.start, w.end, w.word.strip(), w.probability) for s in kept for w in (getattr(s, "words", None) or [])]
        return " ".join(s.text.strip() for s in kept).strip(), language, score, words

    def close(self) -> None:
        self._model = None
        gc.collect()


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


def _biased_score(language: str, score: float) -> float:
    return score + (settings.home_bias if language == settings.home_language else 0.0)


_SAME_WORDS = 0.6  # word overlap (Jaccard) at which a forced decode just repeated the English decode
_SAME_WORDS_MIN = 3  # "Da." or "4-5" reads the same in every language: too short to tell


def _script_fits(text: str, language: str) -> bool:
    """A forced decode that ignored its language: Russian not in Cyrillic, Romanian or English in it.
    Digits and punctuation fit any language."""
    letters = [c for c in text if c.isalpha()]
    if not letters or language not in ("ro", "ru", "en"):
        return True
    cyrillic = sum("\u0400" <= c <= "\u04ff" for c in letters) > len(letters) / 2
    return cyrillic == (language == "ru")


def _same_words(a: str, b: str) -> bool:
    x, y = set(_fold(a).split()), set(_fold(b).split())
    return len(x | y) >= _SAME_WORDS_MIN and len(x & y) / len(x | y) >= _SAME_WORDS


def pick_language(results: dict[str, tuple[str, float]]) -> tuple[str, str]:
    """(text, language) for one utterance from its forced decodes, {language: (text, avg_logprob)}.

    Both engines (batched GPU and one-at-a-time/MLX) pick here. Measured on hour test 3: English
    speech came out Romanian in 14% of an English hour, because (1) the home bias meant for Moldovan
    Romanian against Russian also beat English, (2) a forced decode that kept the English words or
    wrote the wrong script still counted as its language. So: decodes in the wrong script are out,
    a decode repeating the English decode's words is English, the home bias settles only the
    always-decoded pair (ro/ru), and English then needs the better plain score. Ties go to the
    first language, as max() does."""
    pool = {lang: r for lang, r in results.items() if r[0] and _script_fits(r[0], lang)}
    english = pool.get("en")
    if english:
        pool = {lang: r for lang, r in pool.items() if lang == "en" or not _same_words(r[0], english[0])}
    pool = pool or results  # nothing plausible: the old pick over everything
    pair = [lang for lang in pool if lang in settings.asr_always_decode]
    best = max(pair, key=lambda lang: _biased_score(lang, pool[lang][1])) if pair else None
    for lang in pool:
        if lang not in settings.asr_always_decode and (best is None or pool[lang][1] > pool[best][1]):
            best = lang
    return pool[best][0], best


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
    batches = list(batches)
    if getattr(engine, "batched", False):
        found = engine.transcribe_all([b.samples for b in batches])
        return [AsrChunk(start=b.start, end=b.end, text=t, language=lang, hypotheses=h) for b, (t, lang, h) in zip(batches, found)]
    chunks: list[AsrChunk] = []
    language: str | None = None
    for batch in batches:
        text, language, hypotheses = engine.transcribe_batch(batch.samples, language)
        chunks.append(AsrChunk(start=batch.start, end=batch.end, text=text, language=language, hypotheses=hypotheses))
    return chunks
