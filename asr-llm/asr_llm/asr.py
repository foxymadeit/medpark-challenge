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

    def transcribe_batch(
        self, samples: np.ndarray, prev_lang: str | None = None
    ) -> tuple[str, str | None, list[Hypothesis]]:
        samples = samples.astype(np.float32)
        if prev_lang and samples.size < settings.min_lid_s * settings.sample_rate:
            languages = [prev_lang]
        else:
            languages = list(settings.asr_always_decode)
            _, _, probs = self._model.detect_language(samples)
            ranked = rank_languages(probs, settings.asr_languages)
            if ranked and ranked[0][0] not in languages:
                languages.append(ranked[0][0])
        results = [self._decode(samples, lang) for lang in languages]
        text, language, _, _ = max(results, key=_biased_score)
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
            beam_size=5,
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
    chunks: list[AsrChunk] = []
    language: str | None = None
    for batch in batches:
        text, language, hypotheses = engine.transcribe_batch(batch.samples, language)
        chunks.append(AsrChunk(start=batch.start, end=batch.end, text=text, language=language, hypotheses=hypotheses))
    return chunks
