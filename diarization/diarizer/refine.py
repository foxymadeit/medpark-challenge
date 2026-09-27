"""Second pass over a finished session.

Online labels are decided before the voiceprints have matured: the first
seconds of a new voice may be glued to someone else. Once the session is
over we know every speaker's full average voice, so we re-score every
observation against those final centroids (a few k-means style rounds,
starting from the online labels) and keep the result. Speaker ids keep their
online numbers, so what was shown live and what is exported line up.
"""

import numpy as np


def refine(embs_per_obs, ids_per_obs, *, new_th: float, iters: int = 3) -> list:
    ids = [list(x) for x in ids_per_obs]
    for _ in range(iters):
        cents = _centroids(embs_per_obs, ids)
        if not cents:
            return ids
        keys = list(cents)
        C = np.array([cents[k] for k in keys])
        changed = False
        for n, embs in enumerate(embs_per_obs):
            if len(embs) == 0:
                continue
            new = _assign(np.asarray(embs), C, keys, new_th)
            for i, old in enumerate(ids[n]):  # nothing clearly better: keep the online label
                if new[i] is None and old is not None and old not in new:
                    new[i] = old
            if new != ids[n]:
                ids[n], changed = new, True
        if not changed:
            break
    return ids


def _centroids(embs_per_obs, ids) -> dict:
    sums: dict = {}
    for embs, row in zip(embs_per_obs, ids):
        for e, sid in zip(embs, row):
            if sid is not None:
                sums[sid] = sums.get(sid, 0) + np.asarray(e, dtype=np.float64)
    return {k: v / (np.linalg.norm(v) + 1e-9) for k, v in sums.items()}


def _assign(E, C, keys, new_th) -> list:
    """One-to-one: two local speakers of one window never share a label."""
    S = E @ C.T
    out: list = [None] * len(E)
    taken: set = set()
    for flat in np.argsort(-S, axis=None):
        i, j = divmod(int(flat), S.shape[1])
        if out[i] is not None or j in taken or S[i, j] < new_th:
            continue
        out[i] = keys[j]
        taken.add(j)
    return out
