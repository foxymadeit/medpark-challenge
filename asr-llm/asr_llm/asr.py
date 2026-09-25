from __future__ import annotations

import gc
from dataclasses import dataclass

import numpy as np

from .config import settings
from .glossary import asr_hotwords, whisper_initial_prompt
from .local import pick_device, require_local_path


@dataclass
class AsrChunk:
    start: float
    end: float
    text: str
    language: str | None


class WhisperAsr:
    def __init__(self) -> None:
        from faster_whisper import WhisperModel

        model_dir = require_local_path(settings.asr_model_dir, "Whisper model dir")
        self.device = pick_device(settings.device)
        self.model_id = str(model_dir)
        self._prompt = whisper_initial_prompt()
        self._hotwords = asr_hotwords()
        self._model = WhisperModel(
            self.model_id,
            device=self.device,
            compute_type=settings.asr_compute_type,
        )

    def transcribe_batch(self, samples: np.ndarray) -> tuple[str, str | None]:
        segments, info = self._model.transcribe(
            samples.astype(np.float32),
            language=None,
            multilingual=True,
            task="transcribe",
            beam_size=8,
            initial_prompt=self._prompt,
            hotwords=self._hotwords,
            condition_on_previous_text=False,
            vad_filter=False,
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
        return text, getattr(info, "language", None)

    def close(self) -> None:
        self._model = None
        gc.collect()


def transcribe_batches(engine: WhisperAsr, batches) -> list[AsrChunk]:
    chunks: list[AsrChunk] = []
    for batch in batches:
        text, language = engine.transcribe_batch(batch.samples)
        chunks.append(AsrChunk(start=batch.start, end=batch.end, text=text, language=language))
    return chunks
