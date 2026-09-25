"""Streaming diarization loop (the diart method, rebuilt on ONNX models).

Every `step` seconds we look at the last `window` seconds of audio:
1. the segmenter says which of up to 3 local speakers talk in each frame;
2. each local speaker active in the region being labelled gets a voice
   embedding from its clean (non-overlapped) frames nearest that region;
3. the tracker maps local speakers to global ids (Speaker 1, 2, 3...);
4. the labelled region feeds the timeline, which emits start/end events.

The region labelled at time T is [T - latency - step, T - latency), so the
segmenter has already heard `latency` seconds past it. Smaller latency means
faster labels and less context.

Steps 1-2 (Observer) are the slow neural part and do not depend on any
threshold. Steps 3-4 (Labeler) are cheap. Keeping them apart lets the eval
record observations once and replay them under many threshold settings.
"""

from dataclasses import dataclass

import numpy as np

from .neural import SR
from .recluster import recluster
from .refine import refine
from .timeline import Timeline
from .tracker import SpeakerTracker


@dataclass
class Observation:
    region_end: float           # seconds; everything before this is final
    embs: list                  # one unit vector per active local speaker
    can_create: list            # enough clean speech to found a new speaker?
    runs: list                  # per local speaker: [(start_s, end_s), ...] in the region


class Observer:
    def __init__(self, segmenter, embedder, *, window=5.0, step=0.5, latency=1.0,
                 min_assign=0.4, min_create=1.0, max_embed=3.0):
        if not step <= latency <= window - step:
            raise ValueError("need step <= latency <= window - step")
        self.seg, self.emb = segmenter, embedder
        self.W, self.S, self.L = (int(round(x * SR)) for x in (window, step, latency))
        self.min_assign, self.min_create, self.max_embed = min_assign, min_create, max_embed
        self._buf = np.zeros(0, dtype=np.float32)
        self._buf_start = 0
        self._total = 0
        self._next = self.S

    def feed(self, samples) -> list:
        samples = np.asarray(samples, dtype=np.float32)
        self._buf = np.concatenate([self._buf, samples])
        self._total += len(samples)
        out = []
        while self._total >= self._next:
            obs = self._observe(self._next)
            if obs is not None:
                out.append(obs)
            self._next += self.S
        keep_from = max(0, self._next - self.S - self.W)
        if keep_from > self._buf_start:
            self._buf = self._buf[keep_from - self._buf_start:]
            self._buf_start = keep_from
        return out

    def flush(self) -> list:
        """Pad with silence so the last `latency` seconds get observed too."""
        pad = (self._next - self._total) + self.L
        return self.feed(np.zeros(max(pad, 0), dtype=np.float32))

    def _observe(self, t_end: int):
        w0 = max(0, t_end - self.W)
        audio = self._buf[w0 - self._buf_start: t_end - self._buf_start]
        r0, r1 = max(0, t_end - self.L - self.S), t_end - self.L
        if r1 <= r0 or len(audio) < self.seg.receptive:
            return None
        act = self.seg(audio)
        spans = np.array([self.seg.frame_span(i) for i in range(len(act))]) + w0
        centers = spans.mean(axis=1)
        in_region = (centers >= r0) & (centers < r1)
        obs = Observation(r1 / SR, [], [], [])
        for k in range(act.shape[1]):
            if act[in_region, k].sum() < 3:
                continue
            clip, clean_s = self._clip_for(k, act, spans, audio, w0, (r0 + r1) / 2)
            if clip is None:
                continue
            obs.embs.append(self.emb(clip))
            obs.can_create.append(clean_s >= self.min_create)
            obs.runs.append([(max(spans[a, 0], r0) / SR, min(spans[b - 1, 1], r1) / SR)
                             for a, b in _runs(act[:, k] & in_region)])
        return obs

    def _clip_for(self, k, act, spans, audio, w0, center):
        """Audio of local speaker k for embedding: clean frames nearest `center`,
        falling back to overlapped frames when there is too little clean speech."""
        clean = act[:, k] & (act.sum(axis=1) == 1)
        frames = np.flatnonzero(clean)
        clean_s = len(frames) * self.seg.hop / SR
        if clean_s < self.min_assign:
            frames = np.flatnonzero(act[:, k])
            if len(frames) * self.seg.hop / SR < self.min_assign:
                return None, 0.0
        limit = int(self.max_embed * SR / self.seg.hop)
        if len(frames) > limit:
            dist = np.abs(spans[frames].mean(axis=1) - center)
            frames = np.sort(frames[np.argsort(dist)[:limit]])
        pieces = [audio[max(0, a - w0):max(0, b - w0)] for a, b in spans[frames]]
        return np.concatenate(pieces), min(clean_s, self.max_embed)


class Labeler:
    def __init__(self, tracker: SpeakerTracker, timeline: Timeline | None = None, *,
                 merge=0.75, merge_every=10, final="refine", cluster=0.5):
        if final not in ("recluster", "refine", "none"):
            raise ValueError(f"unknown final pass {final!r}")
        self.tracker = tracker
        self.timeline = timeline or Timeline()
        self.merge, self.merge_every = merge, merge_every
        self.final, self.cluster = final, cluster
        self._n = 0
        self._history: list = []   # (observation, online ids) for the final pass

    def apply(self, obs: Observation) -> list:
        """Timeline events: ('start', id, t), ('end', Turn), ('merge', {old: new})."""
        self._n += 1
        events = []
        ids = self.tracker.assign(obs.embs, obs.can_create) if obs.embs else []
        self._history.append((obs, ids))
        for sid, runs in zip(ids, obs.runs):
            if sid is not None:
                for start, end in runs:
                    events += self.timeline.add(sid, start, end)
        if self._n % self.merge_every == 0:
            remap = self.tracker.merge_pass(self.merge)
            if remap:
                self.timeline.relabel(remap)
                events.append(("merge", remap))
        return events + self.timeline.close_idle(now=obs.region_end)

    def finish(self) -> list:
        remap = self.tracker.merge_pass(self.merge)
        if self.final == "none":
            self.timeline.relabel(remap)
            return self.timeline.finish()
        # Decide the final labels with everything heard, then rebuild the turns.
        embs = [o.embs for o, _ in self._history]
        online = [[None if i is None else self.tracker.resolve(i) for i in ids] for _, ids in self._history]
        if self.final == "recluster":
            durs = [[sum(e - s for s, e in runs) for runs in o.runs] for o, _ in self._history]
            final = recluster(embs, online, durs, threshold=self.cluster,
                              max_speakers=self.tracker.max_speakers)
        else:
            final = refine(embs, online, new_th=self.tracker.new_th)
        tl = Timeline(self.timeline.min_gap, self.timeline.min_dur)
        for (obs, _), ids in zip(self._history, final):
            for sid, runs in zip(ids, obs.runs):
                if sid is not None:
                    for start, end in runs:
                        tl.add(sid, start, end)
        return tl.finish()


class StreamingDiarizer:
    """Observer + Labeler: audio in, speaker events out."""

    def __init__(self, observer: Observer, labeler: Labeler):
        self.observer, self.labeler = observer, labeler

    def feed(self, samples) -> list:
        return [e for obs in self.observer.feed(samples) for e in self.labeler.apply(obs)]

    def finish(self) -> list:
        for obs in self.observer.flush():
            self.labeler.apply(obs)
        return self.labeler.finish()

    def label(self, sid: int) -> str:
        return self.labeler.tracker.label(sid)


def _runs(mask: np.ndarray):
    """[start, stop) index pairs of consecutive True values."""
    edges = np.diff(np.concatenate([[0], mask.astype(np.int8), [0]]))
    return zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1))
