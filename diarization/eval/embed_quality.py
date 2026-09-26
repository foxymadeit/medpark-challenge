"""How well do voiceprints separate real people? Scores the embeddings the
engine produced on AMI dev meetings against ground truth, with and without
a trained backend.

  python -m eval.embed_quality --meetings ES2011a IS1008a --backend models/titanet-small.backend.d64.npz
"""

import argparse
import collections
from pathlib import Path

import numpy as np

from diarizer.backend import Backend

from . import run_eval
from .der import read_rttm
from .run_eval import observe


def labelled(cached, meeting, purity=0.8):
    ref = read_rttm(run_eval.DATA / f"{meeting}.rttm")
    E, L = [], []
    for o in cached["obs"]:
        for emb, runs in zip(o.embs, o.runs):
            ov = collections.Counter()
            for s, e in runs:
                for spk, a, b in ref:
                    if min(e, b) > max(s, a):
                        ov[spk] += min(e, b) - max(s, a)
            total = sum(e - s for s, e in runs)
            if ov and ov.most_common(1)[0][1] / max(total, 1e-9) >= purity:
                E.append(emb)
                L.append(ov.most_common(1)[0][0])
    return np.array(E), np.array(L)


def dprime(E, L, n=1500, seed=0):
    idx = np.random.default_rng(seed).choice(len(E), min(n, len(E)), replace=False)
    S = E[idx] @ E[idx].T
    same = L[idx][:, None] == L[idx][None, :]
    iu = np.triu_indices(len(idx), 1)
    a, b = S[iu][same[iu]], S[iu][~same[iu]]
    return (a.mean() - b.mean()) / np.sqrt((a.var() + b.var()) / 2), a.mean(), b.mean()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--meetings", nargs="+", default=["ES2011a", "IS1008a"])
    ap.add_argument("--embedder", default="titanet-small")
    ap.add_argument("--backend", nargs="*", default=[])
    ap.add_argument("--data", type=Path, help="meeting folder (default data/ami)")
    ap.add_argument("--kind", default="Array1-01")
    a = ap.parse_args()
    if a.data:
        run_eval.DATA = a.data.resolve()
    raw = []
    for m in a.meetings:
        E, L = labelled(observe(m, a.kind, a.embedder, 1.0), m)
        d, s, x = dprime(E, L)
        raw.append(d)
        print(f"{m:8s} raw                d' {d:5.2f}  same {s:.3f} diff {x:.3f}")
        for p in a.backend:
            d, s, x = dprime(Backend.load(p)(E), L)
            print(f"{m:8s} {p.split('/')[-1]:18s} d' {d:5.2f}  same {s:.3f} diff {x:.3f}")
    print(f"mean raw d' {np.mean(raw):.2f}")


if __name__ == "__main__":
    main()
