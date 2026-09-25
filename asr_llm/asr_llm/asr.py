from __future__ import annotations

import platform
from dataclasses import dataclass

import numpy as np

from .config import settings
from .glossary import whisper_initial_prompt


@dataclass
class AsrChunk:
    start: float
    end: float
    text: str
    language: str | None


class AsrEngine:
    def transcribe_batch(self, samples: np.ndarray, sample_rate: int) -> tuple[str, str | None]:
        raise NotImplementedError

    @property
    def name(self) -> str:
        raise NotImplementedError

    @property
    def model_id(self) -> str:
        raise NotImplementedError


def pick_backend(name: str | None = None) -> AsrEngine:
    choice = (name or settings.asr_backend).lower()
    if choice == "auto":
        choice = "mlx" if platform.system() == "Darwin" and platform.machine() == "arm64" else "faster-whisper"
    if choice == "mlx":
        return MlxWhisperEngine()
    if choice in {"faster-whisper", "faster_whisper", "cpu"}:
        return FasterWhisperEngine()
    raise ValueError(f"Unknown ASR backend: {choice}")


class MlxWhisperEngine(AsrEngine):
    def __init__(self, model: str | None = None) -> None:
        import mlx_whisper

        self._mlx = mlx_whisper
        self._model = model or settings.asr_model
        self._path = _mlx_model_path(self._model)
        self._prompt = whisper_initial_prompt(settings.glossary_path)

    @property
    def name(self) -> str:
        return "mlx-whisper"

    @property
    def model_id(self) -> str:
        return self._path

    def transcribe_batch(self, samples: np.ndarray, sample_rate: int) -> tuple[str, str | None]:
        result = self._mlx.transcribe(
            samples.astype(np.float32),
            path_or_hf_repo=self._path,
            word_timestamps=False,
            initial_prompt=self._prompt,
            condition_on_previous_text=False,
        )
        text = (result.get("text") or "").strip()
        language = result.get("language")
        return text, language


class FasterWhisperEngine(AsrEngine):
    def __init__(self, model: str | None = None) -> None:
        from faster_whisper import WhisperModel

        self._model_name = model or settings.asr_model
        self._model = WhisperModel(self._model_name, compute_type=settings.asr_compute_type)
        self._prompt = whisper_initial_prompt(settings.glossary_path)

    @property
    def name(self) -> str:
        return "faster-whisper"

    @property
    def model_id(self) -> str:
        return self._model_name

    def transcribe_batch(self, samples: np.ndarray, sample_rate: int) -> tuple[str, str | None]:
        segments, info = self._model.transcribe(
            samples.astype(np.float32),
            language=None,
            initial_prompt=self._prompt,
            condition_on_previous_text=False,
            vad_filter=False,
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
        language = getattr(info, "language", None)
        return text, language


def transcribe_batches(engine: AsrEngine, batches, sample_rate: int) -> list[AsrChunk]:
    chunks: list[AsrChunk] = []
    for batch in batches:
        text, language = engine.transcribe_batch(batch.samples, sample_rate)
        chunks.append(AsrChunk(start=batch.start, end=batch.end, text=text, language=language))
    return chunks


def _mlx_model_path(model: str) -> str:
    aliases = {
        "large-v3-turbo": "mlx-community/whisper-large-v3-turbo",
        "large-v3": "mlx-community/whisper-large-v3-mlx",
        "medium": "mlx-community/whisper-medium-mlx",
        "small": "mlx-community/whisper-small-mlx",
    }
    return aliases.get(model, model)
