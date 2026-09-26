"""Enrolled voiceprints. These are biometric data: they stay on this machine
(voices/ is gitignored) and are only ever compared locally."""

import os
import re
import sys
from pathlib import Path

import numpy as np

from .neural import SR

VOICES_DIR = Path(os.environ.get("DIARIZER_VOICES") or Path(__file__).resolve().parent.parent / "voices")
CHUNK_S = 3.0


def voice_embeddings(audio, segmenter, embedder) -> list:
    """Keep the speech, cut it into 3 s pieces, embed each piece."""
    speech = []
    for w0 in range(0, len(audio), 10 * SR):
        win = audio[w0:w0 + 10 * SR]
        if len(win) < segmenter.receptive:
            break
        act = segmenter(win).any(axis=1)
        speech += [win[max(0, a):b] for (a, b), on in
                   zip((segmenter.frame_span(i) for i in range(len(act))), act) if on]
    if not speech:
        return []
    speech = np.concatenate(speech)
    n = int(CHUNK_S * SR)
    return [embedder(speech[i:i + n]) for i in range(0, len(speech) - n + 1, n)]


def save_voice(name: str, embedder_name: str, embs, add: bool = False) -> Path:
    """add=True keeps what is already saved, e.g. a second language."""
    VOICES_DIR.mkdir(parents=True, exist_ok=True)
    path = VOICES_DIR / f"{_slug(name)}.{embedder_name}.npz"
    old = list(np.load(path)["embs"]) if add and path.exists() and "space" in np.load(path).files else []
    np.savez(path, name=name, embs=np.asarray(old + list(embs), dtype=np.float32), space="raw")
    return path


def closest_voice(embs, known: dict, skip: str = None):
    """(name, cosine) of the enrolled person whose average voiceprint is
    nearest to these, or (None, 0.0). Above the tracker's 0.70 anchor the
    two could be confused in a meeting."""
    def unit(v):
        v = np.mean(np.asarray(v, dtype=np.float32), axis=0)
        return v / (np.linalg.norm(v) + 1e-9)
    new = unit(embs)
    sims = [(name, float(unit(vs) @ new)) for name, vs in known.items() if name != skip]
    return max(sims, key=lambda x: x[1]) if sims else (None, 0.0)


def load_voices(embedder_name: str) -> dict:
    out = {}
    for p in sorted(VOICES_DIR.glob(f"*.{embedder_name}.npz")) if VOICES_DIR.is_dir() else []:
        data = np.load(p)
        if "space" not in data.files:  # saved before voiceprints were stored raw
            print(f"skipping {data['name']}: enrolled with an older version, please enroll again", file=sys.stderr)
            continue
        out[str(data["name"])] = list(data["embs"])
    return out


def _slug(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_") or "voice"
