from __future__ import annotations

import gc
from dataclasses import dataclass

import numpy as np

from .config import settings
from .local import pick_device, require_local_path


@dataclass
class AsrChunk:
    start: float
    end: float
    text: str
    language: str | None


def rank_languages(probs: list[tuple[str, float]], allowed: tuple[str, ...]) -> list[tuple[str, float]]:
    """Keep only the meeting's languages and renormalize, best first."""
    kept = [(lang, p) for lang, p in probs if lang in allowed]
    total = sum(p for _, p in kept) or 1.0
    return sorted(((lang, p / total) for lang, p in kept), key=lambda item: item[1], reverse=True)


def candidate_languages(ranked: list[tuple[str, float]], margin: float) -> list[str]:
    if len(ranked) > 1 and ranked[0][1] - ranked[1][1] < margin:
        return [ranked[0][0], ranked[1][0]]
    return [ranked[0][0]]


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

    def transcribe_batch(self, samples: np.ndarray, prev_lang: str | None = None) -> tuple[str, str | None]:
        samples = samples.astype(np.float32)
        if prev_lang and samples.size < settings.min_lid_s * settings.sample_rate:
            languages = [prev_lang]
        else:
            _, _, probs = self._model.detect_language(samples)
            languages = candidate_languages(rank_languages(probs, settings.asr_languages), settings.lid_margin)
        text, language, _ = max((self._decode(samples, lang) for lang in languages), key=lambda r: r[2])
        return text, language

    def _decode(self, samples: np.ndarray, language: str) -> tuple[str, str, float]:
        """Text in one forced language, scored by duration-weighted avg_logprob."""
        segments, _ = self._model.transcribe(
            samples,
            language=language,
            task="transcribe",
            beam_size=5,
            condition_on_previous_text=False,
            vad_filter=False,
        )
        # Whisper's own silence rule, applied per utterance.
        kept = [s for s in segments if not (s.no_speech_prob > 0.6 and s.avg_logprob < -1.0)]
        if not kept:
            return "", language, float("-inf")
        weights = [max(s.end - s.start, 1e-3) for s in kept]
        score = sum(s.avg_logprob * w for s, w in zip(kept, weights)) / sum(weights)
        return " ".join(s.text.strip() for s in kept).strip(), language, score

    def close(self) -> None:
        self._model = None
        gc.collect()


def transcribe_batches(engine: WhisperAsr, batches) -> list[AsrChunk]:
    chunks: list[AsrChunk] = []
    language: str | None = None
    for batch in batches:
        text, language = engine.transcribe_batch(batch.samples, language)
        chunks.append(AsrChunk(start=batch.start, end=batch.end, text=text, language=language))
    return chunks
