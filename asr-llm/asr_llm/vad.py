from __future__ import annotations

import numpy as np

from .config import settings


def speech_spans(audio: np.ndarray, sample_rate: int | None = None) -> list[tuple[float, float]]:
    """Silero VAD (ONNX bundled with faster-whisper, no download). Cuts at pauses.

    A pause of `vad_min_silence_ms` ends an utterance, so one span is usually one
    speaker in one language. Long monologues are split at their last silence
    before `max_batch_s`. Returns (start_s, end_s).
    """
    from faster_whisper.vad import VadOptions, get_speech_timestamps

    sr = sample_rate or settings.sample_rate
    options = VadOptions(
        threshold=settings.vad_threshold,
        min_silence_duration_ms=settings.vad_min_silence_ms,
        min_speech_duration_ms=int(settings.min_speech_s * 1000),
        speech_pad_ms=int(settings.vad_pad_s * 1000),
        max_speech_duration_s=settings.max_batch_s,
    )
    chunks = get_speech_timestamps(audio, options, sampling_rate=sr)
    return [(c["start"] / sr, c["end"] / sr) for c in chunks]
