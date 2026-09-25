from __future__ import annotations

import numpy as np

from .config import settings


def energy_vad(
    audio: np.ndarray,
    sample_rate: int | None = None,
    *,
    frame_ms: int | None = None,
    threshold_ratio: float = 0.5,
    min_speech_s: float | None = None,
    pad_s: float | None = None,
) -> list[tuple[float, float]]:
    """Lightweight RMS VAD. Good enough to skip silence before Whisper.

    Replace with Silero ONNX later if the Medpark file has quiet speakers
    that this misses. Returns (start_s, end_s) speech spans.
    """
    sr = sample_rate or settings.sample_rate
    frame_ms = frame_ms or settings.vad_frame_ms
    min_speech_s = min_speech_s if min_speech_s is not None else settings.min_speech_s
    pad_s = pad_s if pad_s is not None else settings.vad_pad_s

    frame = max(1, int(sr * frame_ms / 1000))
    n_frames = audio.size // frame
    if n_frames == 0:
        return []

    frames = audio[: n_frames * frame].reshape(n_frames, frame)
    rms = np.sqrt(np.mean(np.square(frames), axis=1) + 1e-12)
    noise = float(np.median(rms))
    threshold = noise * (1.0 + threshold_ratio) + 1e-4
    voiced = rms > threshold

    spans: list[tuple[int, int]] = []
    start: int | None = None
    for i, flag in enumerate(voiced):
        if flag and start is None:
            start = i
        elif not flag and start is not None:
            spans.append((start, i))
            start = None
    if start is not None:
        spans.append((start, n_frames))

    pad_frames = int(pad_s * 1000 / frame_ms)
    min_frames = max(1, int(min_speech_s * 1000 / frame_ms))
    padded: list[tuple[int, int]] = []
    for a, b in spans:
        if b - a < min_frames:
            continue
        padded.append((max(0, a - pad_frames), min(n_frames, b + pad_frames)))

    merged: list[tuple[int, int]] = []
    for a, b in padded:
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))

    return [(i * frame / sr, j * frame / sr) for i, j in merged]
