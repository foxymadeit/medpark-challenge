"""Speaker memory for streaming diarization.

Every speaker keeps a running-mean centroid plus a few prototypes: embeddings
that matched the speaker but looked unlike anything stored so far (a switch
from Romanian to Russian, a different distance to the mic). A new embedding
is scored against the best of those, so one person keeps one label across
languages. Scores are cosine similarities of unit-length embeddings.
"""

from dataclasses import dataclass, field

import numpy as np


def _unit(v) -> np.ndarray:
    v = np.asarray(v, dtype=np.float32)
    return v / (np.linalg.norm(v) + 1e-9)


@dataclass
class Speaker:
    id: int
    centroid: np.ndarray
    weight: float = 1.0
    name: str | None = None
    protos: list = field(default_factory=list)


class SpeakerTracker:
    """Maps per-window embeddings onto stable global speaker ids (1, 2, 3...).

    assign   match an existing speaker at or above this similarity
    new      create a speaker only when every existing one scores below this
    anchor   an enrolled (named) speaker needs this much to claim a turn
    max_speakers  0 means unknown; otherwise never create more than this

    Voiceprints that land between `new` and `assign` go to the nearest speaker
    for now. With `pending_min` > 0 they also go into a pending pool. Once `pending_min` of them agree
    with each other and their average matches nobody, that average founds a
    new speaker. A group mean is far steadier than one noisy far-field
    voiceprint, so newcomers who sound a bit like someone still get found.
    """

    def __init__(self, *, assign=0.5, new=0.3, anchor=0.7, max_speakers=0,
                 max_protos=8, proto_novelty=0.85, max_weight=50.0,
                 pending_min=0, pending_agree=0.6, max_pending=20):
        self.assign_th = assign
        self.new_th = new
        self.anchor_th = anchor
        self.max_speakers = max_speakers
        self.max_protos = max_protos
        self.proto_novelty = proto_novelty
        self.max_weight = max_weight
        self.pending_min, self.pending_agree, self.max_pending = pending_min, pending_agree, max_pending
        self._pending: list = []
        self._speakers: list[Speaker] = []
        self._merged: dict[int, int] = {}
        self._next_id = 1

    @property
    def speakers(self) -> list[Speaker]:
        return list(self._speakers)

    def resolve(self, sid: int) -> int:
        while sid in self._merged:
            sid = self._merged[sid]
        return sid

    def label(self, sid: int) -> str:
        spk = self._by_id(self.resolve(sid))
        return spk.name or f"Speaker {spk.id}"

    def similarity(self, emb, spk: Speaker) -> float:
        emb = _unit(emb)
        return max([float(emb @ spk.centroid)] + [float(emb @ p) for p in spk.protos])

    def enroll(self, name: str, embeddings) -> int:
        embs = [_unit(e) for e in embeddings]
        spk = self._create(_unit(np.mean(embs, axis=0)), name=name)
        spk.protos = []
        for e in embs:
            self._maybe_add_proto(spk, e)
        spk.weight = float(len(embs))
        return spk.id

    def assign(self, embeddings, can_create) -> list:
        """Label each local speaker of one window. Two local speakers never
        share a global id. Returns an id or None (not enough evidence yet)."""
        embs = [_unit(e) for e in embeddings]
        sims = np.array([[self.similarity(e, s) for s in self._speakers] for e in embs])
        sims = sims.reshape(len(embs), len(self._speakers))
        result: list = [None] * len(embs)
        taken: set = set()
        # Greedy best-pair-first. With at most 3 local speakers this matches
        # the optimal assignment in practice and needs no solver.
        pairs = sorted(((sims[i, j], i, j) for i in range(len(embs))
                        for j in range(len(self._speakers))), reverse=True)
        for s, i, j in pairs:
            if result[i] is not None or j in taken:
                continue
            spk = self._speakers[j]
            if s >= self._gate(spk):
                result[i] = spk.id
                taken.add(j)
                self._update(spk, embs[i], s)
            elif self._full():
                result[i] = spk.id  # capped: nearest wins, but don't learn from it
                taken.add(j)
        for i, e in enumerate(embs):
            if result[i] is None:
                result[i] = self._undecided(i, e, sims, taken, can_create[i])
        return result

    def merge_pass(self, threshold: float) -> dict:
        """Fold speakers whose centroids converged into the older id."""
        remap: dict = {}
        merged = True
        while merged:
            merged = False
            for a in self._speakers:
                for b in self._speakers:
                    if b.id <= a.id or float(a.centroid @ b.centroid) < threshold:
                        continue
                    if a.name and b.name and a.name != b.name:
                        continue
                    self._absorb(a, b)
                    remap[b.id] = a.id
                    merged = True
                    break
                if merged:
                    break
        return remap

    # internals

    def _undecided(self, i, e, sims, taken, can_create):
        if sims.shape[1] == 0:
            return self._create(e).id if can_create else None
        best = int(np.argmax(sims[i]))
        if sims[i, best] < self.new_th and can_create and not self._full():
            return self._create(e).id
        if best not in taken and sims[i, best] >= self.new_th:
            taken.add(best)
            founded = self._found_from_pending(e)
            return founded.id if founded else self._speakers[best].id  # unsure: no learning
        return None

    def _found_from_pending(self, e):
        self._pending = (self._pending + [e])[-self.max_pending:]
        if not self.pending_min or len(self._pending) < self.pending_min or self._full():
            return None
        P = np.array(self._pending)
        agree = P @ _unit(P.mean(axis=0)) >= self.pending_agree
        if agree.sum() < self.pending_min:
            return None
        mean = _unit(P[agree].mean(axis=0))
        if max(self.similarity(mean, s) for s in self._speakers) >= self.assign_th:
            return None  # the group is just a noisy stretch of a known voice
        self._pending = [p for p, ok in zip(self._pending, agree) if not ok]
        return self._create(mean)

    def _gate(self, spk: Speaker) -> float:
        return self.anchor_th if spk.name else self.assign_th

    def _full(self) -> bool:
        return self.max_speakers > 0 and len(self._speakers) >= self.max_speakers

    def _create(self, emb, name=None) -> Speaker:
        spk = Speaker(id=self._next_id, centroid=_unit(emb), name=name, protos=[_unit(emb)])
        self._next_id += 1
        self._speakers.append(spk)
        return spk

    def _update(self, spk: Speaker, emb, score: float) -> None:
        spk.centroid = _unit(spk.centroid * spk.weight + emb)
        spk.weight = min(spk.weight + 1.0, self.max_weight)
        self._maybe_add_proto(spk, emb)

    def _maybe_add_proto(self, spk: Speaker, emb) -> None:
        if spk.protos and max(float(emb @ p) for p in spk.protos) >= self.proto_novelty:
            return
        spk.protos.append(emb)
        if len(spk.protos) > self.max_protos:
            del spk.protos[1]  # keep the first voiceprint, drop the oldest after it

    def _absorb(self, keep: Speaker, gone: Speaker) -> None:
        total = keep.weight + gone.weight
        keep.centroid = _unit(keep.centroid * keep.weight + gone.centroid * gone.weight)
        keep.weight = min(total, self.max_weight)
        keep.name = keep.name or gone.name
        for p in gone.protos:
            self._maybe_add_proto(keep, p)
        self._speakers.remove(gone)
        self._merged[gone.id] = keep.id

    def _by_id(self, sid: int) -> Speaker:
        return next(s for s in self._speakers if s.id == sid)
