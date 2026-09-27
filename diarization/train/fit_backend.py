"""Train the embedding backend (LDA + WCCN) on labelled meetings.

  python -m train.fit_backend --data ../data/ami/train --embedder titanet-small --dims 32 64 96

Cuts every speaker's clean (non-overlapped) speech into 1-3 s pieces, the
same lengths the live engine embeds, embeds them, and fits one projection
per requested size. AMI speaker ids are global, so the same person heard in
different meetings and rooms teaches the projection what to ignore.
"""

import argparse
from pathlib import Path

import numpy as np

from diarizer import models
from diarizer.audio import load
from diarizer.backend import fit_lda_wccn
from diarizer.neural import SR, Embedder
from eval.der import read_rttm

CACHE = Path(__file__).resolve().parents[1] / "eval" / "cache"


def clean_intervals(ref):
    """Per speaker: the parts of their turns where nobody else talks."""
    out = {}
    for i, (spk, a, b) in enumerate(ref):
        pieces = [(a, b)]
        for j, (_, c, d) in enumerate(ref):
            if j == i or d <= a or c >= b:
                continue
            pieces = [(x, y) for p, q in pieces for x, y in ((p, min(q, c)), (max(p, d), q)) if y - x > 0]
        out.setdefault(spk, []).extend(pieces)
    return out


def chunks(intervals, rng, max_per_speaker=120):
    out = []
    for a, b in intervals:
        t = a
        while b - t >= 1.0:
            n = min(b - t, rng.uniform(1.0, 3.0))
            out.append((t, t + n))
            t += n
    rng.shuffle(out)
    return out[:max_per_speaker]


def embed_meetings(data: Path, embedder: str, threads: int):
    cache = CACHE / f"train.{data.name}.{embedder}.npz"
    if cache.exists():
        d = np.load(cache)
        return d["X"], d["y"]
    emb = Embedder(models.embedder_path(embedder), threads)
    rng = np.random.default_rng(0)
    X, y = [], []
    for flac in sorted(data.glob("*.Array1-01.flac")):
        meeting = flac.name.split(".")[0]
        rttm = data / f"{meeting}.rttm"
        if not rttm.exists():
            continue
        audio = load(flac)
        for spk, iv in clean_intervals(read_rttm(rttm)).items():
            for a, b in chunks(iv, rng):
                X.append(emb(audio[int(a * SR):int(b * SR)]))
                y.append(spk)
        print(f"  {meeting}: {len(X)} pieces so far", flush=True)
    X, y = np.array(X), np.array(y)
    CACHE.mkdir(exist_ok=True)
    np.savez(cache, X=X, y=y)
    return X, y


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--embedder", default=models.DEFAULT_EMBEDDER)
    ap.add_argument("--dims", type=int, nargs="+", default=[64])
    ap.add_argument("--threads", type=int, default=2)
    a = ap.parse_args()
    X, y = embed_meetings(a.data, a.embedder, a.threads)
    print(f"{len(X)} pieces from {len(set(y))} speakers")
    for d in a.dims:
        out = models.MODELS_DIR / f"{a.embedder}.backend.d{d}.npz"
        fit_lda_wccn(X, y, dim=d).save(out)
        print(f"wrote {out}")


if __name__ == "__main__":
    main()
