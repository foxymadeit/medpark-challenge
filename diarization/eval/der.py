"""Diarization error rate, scored the strict way: 10 ms frames, no collar,
overlapped speech counted. Hypothesis labels are mapped to reference
speakers with the assignment that maximises matched time.

DER = (missed speech + false alarm + speaker confusion) / reference speech.
"""

import numpy as np
from scipy.optimize import linear_sum_assignment


def read_rttm(path) -> list:
    out = []
    for line in open(path):
        f = line.split()
        if f and f[0] == "SPEAKER":
            start, dur = float(f[3]), float(f[4])
            out.append((f[7], start, start + dur))
    return out


def _matrix(segs, n_frames, step):
    names = sorted({s for s, _, _ in segs})
    m = np.zeros((n_frames, len(names)), dtype=bool)
    for s, a, b in segs:
        m[int(round(a / step)):int(round(b / step)), names.index(s)] = True
    return m


def der(ref, hyp, step: float = 0.01, collar: float = 0.0) -> dict:
    end = max([b for _, _, b in ref] + [b for _, _, b in hyp] + [0.0])
    n = int(np.ceil(end / step)) + 1
    R, H = _matrix(ref, n, step), _matrix(hyp, n, step)
    scored = np.ones(n, dtype=bool)
    if collar > 0:
        c = int(round(collar / step))
        for _, a, b in ref:
            for t in (a, b):
                i = int(round(t / step))
                scored[max(0, i - c):i + c] = False
    R, H = R[scored], H[scored]
    n_ref, n_hyp = R.sum(1), H.sum(1)
    if R.shape[1] and H.shape[1]:
        overlap = R.T.astype(np.int64) @ H.astype(np.int64)
        ri, hi = linear_sum_assignment(-overlap)
        correct = sum((R[:, r] & H[:, h]).astype(int) for r, h in zip(ri, hi))
    else:
        correct = np.zeros(len(R), dtype=int)
    total = n_ref.sum()
    miss = np.maximum(n_ref - n_hyp, 0).sum()
    fa = np.maximum(n_hyp - n_ref, 0).sum()
    conf = (np.minimum(n_ref, n_hyp) - correct).sum()
    return {
        "der": (miss + fa + conf) / total,
        "miss": miss / total,
        "false_alarm": fa / total,
        "confusion": conf / total,
        "ref_speakers": R.shape[1],
        "hyp_speakers": H.shape[1],
    }
