"""Global clustering once a session is over.

The live tracker decides as it goes, so a speaker who was glued onto someone
else early on can stay hidden for the whole session. At the end we have every
voiceprint, so we cluster them all at once:

1. consecutive observations with the same online label are pooled into
   chunks of about 3 s (one averaged embedding each);
2. average-linkage clustering on cosine similarity, cut at `threshold`
   (average linkage compares group means, which separate far more cleanly
   than single turns do);
3. clusters with less than `min_speaker_s` of speech are folded into the
   nearest real speaker;
4. clusters take the online number they overlap most, so the ids printed
   live and the ids in the exported minutes agree wherever possible;
5. every observation is then matched once more against the final speakers,
   which splits chunks that straddled a change of speaker.
"""

import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage

from .refine import refine


def recluster(embs_per_obs, ids_per_obs, durs_per_obs, *, threshold: float,
              chunk_s: float = 3.0, min_speaker_s: float = 2.0, max_speakers: int = 0) -> list:
    items = _chunks(embs_per_obs, ids_per_obs, durs_per_obs, chunk_s)
    if len(items) < 2:
        return [list(r) for r in ids_per_obs]
    X = np.array([it["emb"] for it in items])
    Z = linkage(X, method="average", metric="cosine")
    labels = fcluster(Z, t=1.0 - threshold, criterion="distance")
    if max_speakers and labels.max() > max_speakers:
        labels = fcluster(Z, t=max_speakers, criterion="maxclust")
    labels = _fold_small(X, labels, np.array([it["dur"] for it in items]), min_speaker_s)
    clustered = [list(r) for r in ids_per_obs]
    for it, lab in zip(items, labels):
        for n, k in it["members"]:
            clustered[n][k] = ("c", int(lab))
    clustered = refine(embs_per_obs, clustered, new_th=0.0, iters=2)
    names = _name_after_online(ids_per_obs, clustered, durs_per_obs)
    return [[None if c is None else names[c] for c in row] for row in clustered]


def _chunks(embs_per_obs, ids_per_obs, durs_per_obs, chunk_s):
    items: list = []
    open_: dict = {}
    for n, (embs, ids, durs) in enumerate(zip(embs_per_obs, ids_per_obs, durs_per_obs)):
        seen = set()
        for k, (e, sid, d) in enumerate(zip(embs, ids, durs)):
            if sid is None:
                continue
            seen.add(sid)
            it = open_.get(sid)
            if it is None or it["dur"] >= chunk_s:
                it = open_[sid] = {"sum": 0.0, "dur": 0.0, "members": [], "online": sid}
                items.append(it)
            it["sum"] = it["sum"] + np.asarray(e, dtype=np.float64) * max(d, 1e-3)
            it["dur"] += d
            it["members"].append((n, k))
        for sid in [s for s in open_ if s not in seen]:  # label paused: close its chunk
            del open_[sid]
    for it in items:
        it["emb"] = it["sum"] / (np.linalg.norm(it["sum"]) + 1e-9)
    return items


def _fold_small(X, labels, durs, min_s):
    labels = labels.copy()
    while True:
        talk = {c: durs[labels == c].sum() for c in np.unique(labels)}
        small = [c for c, t in talk.items() if t < min_s]
        if not small or len(talk) == 1:
            return labels
        c = min(small, key=talk.get)
        cent = {k: _mean(X[labels == k]) for k in talk if k != c}
        target = max(cent, key=lambda k: float(_mean(X[labels == c]) @ cent[k]))
        labels[labels == c] = target


def _name_after_online(online_rows, cluster_rows, dur_rows):
    """Each cluster takes the online id it shares the most speech with
    (ties go to whoever appeared first); leftovers get fresh numbers."""
    overlap: dict = {}
    first: dict = {}
    for n, (on, cl, du) in enumerate(zip(online_rows, cluster_rows, dur_rows)):
        for o, c, d in zip(on, cl, du):
            if c is None:
                continue
            first.setdefault(c, n)
            if o is not None:
                overlap[(c, o)] = overlap.get((c, o), 0.0) + d
    names, used = {}, set()
    for (c, o), _ in sorted(overlap.items(), key=lambda kv: (-kv[1], first[kv[0][0]])):
        if c not in names and o not in used:
            names[c] = o
            used.add(o)
    next_id = max([o for row in online_rows for o in row if o is not None] + [0]) + 1
    for c in sorted(first, key=first.get):
        if c not in names:
            names[c] = next_id
            next_id += 1
    return names


def _mean(X):
    v = X.mean(axis=0)
    return v / (np.linalg.norm(v) + 1e-9)
