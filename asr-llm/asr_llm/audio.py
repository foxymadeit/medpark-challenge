from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

from .config import settings


def decode_audio(path: Path, sample_rate: int | None = None) -> np.ndarray:
    """Decode any ffmpeg-readable file to float32 mono PCM."""
    sr = sample_rate or settings.sample_rate
    cmd = [
        settings.ffmpeg_bin,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(path),
        "-ac",
        "1",
        "-ar",
        str(sr),
        "-f",
        "f32le",
        "pipe:1",
    ]
    proc = subprocess.run(cmd, check=True, capture_output=True)
    audio = np.frombuffer(proc.stdout, dtype=np.float32)
    if audio.size == 0:
        raise RuntimeError(f"ffmpeg produced empty audio for {path}")
    return audio


def duration_s(audio: np.ndarray, sample_rate: int | None = None) -> float:
    sr = sample_rate or settings.sample_rate
    return float(audio.size) / sr
