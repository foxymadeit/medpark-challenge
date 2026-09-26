"""Read the diarizer's session JSON (Coflazo-Branch `diarizer file … --out DIR`).

Contract: `{"turns": [{"speaker": "Speaker 1", "start": 0.0, "end": 4.2, ...}]}`,
seconds from the start of the same file. Both sides decode with ffmpeg to
16 kHz mono, so the clocks line up.
"""

from __future__ import annotations

import json
from pathlib import Path

Turn = tuple[float, float, str]

# Do not cut a VAD span into slivers Whisper cannot transcribe.
MIN_PIECE_S = 0.5


def load_turns(path: Path) -> list[Turn]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [(float(t["start"]), float(t["end"]), str(t["speaker"])) for t in raw.get("turns") or []]


def split_at_turns(spans: list[tuple[float, float]], turns: list[Turn]) -> list[tuple[float, float]]:
    """Cut each speech span where the speaker changes: that is where the language usually switches."""
    bounds = sorted({x for start, end, _ in turns for x in (start, end)})
    out: list[tuple[float, float]] = []
    for a, b in spans:
        cursor = a
        for x in bounds:
            if cursor + MIN_PIECE_S <= x <= b - MIN_PIECE_S:
                out.append((cursor, x))
                cursor = x
        out.append((cursor, b))
    return out


def speaker_for(start: float, end: float, turns: list[Turn]) -> str | None:
    """Speaker with the largest overlap, or None when no turn touches the span."""
    best, best_overlap = None, 0.0
    for t_start, t_end, speaker in turns:
        overlap = min(end, t_end) - max(start, t_start)
        if overlap > best_overlap:
            best, best_overlap = speaker, overlap
    return best
