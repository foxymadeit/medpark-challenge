from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .config import settings


@dataclass(frozen=True)
class AudioBatch:
    index: int
    start: float
    end: float
    samples: np.ndarray


def pack_batches(
    audio: np.ndarray,
    spans: list[tuple[float, float]],
    *,
    sample_rate: int | None = None,
    max_batch_s: float | None = None,
    merge_gap_s: float | None = None,
) -> list[AudioBatch]:
    sr = sample_rate or settings.sample_rate
    max_batch_s = max_batch_s or settings.max_batch_s
    merge_gap_s = merge_gap_s if merge_gap_s is not None else settings.merge_gap_s
    max_samples = int(max_batch_s * sr)

    glued: list[tuple[float, float]] = []
    for start, end in spans:
        if glued and start - glued[-1][1] <= merge_gap_s:
            glued[-1] = (glued[-1][0], end)
        else:
            glued.append((start, end))

    batches: list[AudioBatch] = []
    idx = 0
    for start, end in glued:
        cursor = start
        while cursor < end:
            chunk_end = min(end, cursor + max_batch_s)
            a = int(cursor * sr)
            b = int(chunk_end * sr)
            piece = audio[a:b]
            if piece.size > max_samples:
                piece = piece[:max_samples]
                chunk_end = cursor + piece.size / sr
            if piece.size == 0:
                break
            batches.append(AudioBatch(index=idx, start=cursor, end=chunk_end, samples=piece))
            idx += 1
            cursor = chunk_end
    return batches
