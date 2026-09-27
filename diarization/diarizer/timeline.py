"""Turns speaker activity segments into turns: (speaker, start, end).

Times are seconds from the start of the stream. A speaker's turn stays open
through pauses shorter than `min_gap`; turns shorter than `min_dur` are
treated as blips and dropped. Live mode reads the events returned by `add`
and `close_idle` to print a line when someone starts and stops talking.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Turn:
    speaker: int
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start


class Timeline:
    def __init__(self, min_gap: float = 0.5, min_dur: float = 0.3):
        self.min_gap = min_gap
        self.min_dur = min_dur
        self._open: dict[int, list] = {}  # speaker -> [start, end, announced]
        self._closed: list[Turn] = []

    def add(self, speaker: int, start: float, end: float) -> list:
        events = []
        cur = self._open.get(speaker)
        if cur and start - cur[1] > self.min_gap:
            events += self._close(speaker)
            cur = None
        if cur is None:
            cur = self._open[speaker] = [start, end, False]
        cur[1] = max(cur[1], end)
        if not cur[2] and cur[1] - cur[0] >= self.min_dur:
            cur[2] = True
            events.append(("start", speaker, cur[0]))
        return events

    def close_idle(self, now: float) -> list:
        events = []
        for spk in [s for s, cur in self._open.items() if now - cur[1] > self.min_gap]:
            events += self._close(spk)
        return events

    def relabel(self, remap: dict) -> None:
        if not remap:
            return
        self._closed = [Turn(remap.get(t.speaker, t.speaker), t.start, t.end) for t in self._closed]
        for old, new in remap.items():
            cur = self._open.pop(old, None)
            if cur is None:
                continue
            if new in self._open:
                keep = self._open[new]
                keep[0], keep[1] = min(keep[0], cur[0]), max(keep[1], cur[1])
                keep[2] = keep[2] or cur[2]
            else:
                self._open[new] = cur

    def finish(self) -> list[Turn]:
        for spk in list(self._open):
            self._close(spk)
        return _merge_adjacent(sorted(self._closed, key=lambda t: (t.start, t.speaker)), self.min_gap)

    def _close(self, speaker: int) -> list:
        start, end, announced = self._open.pop(speaker)
        if end - start < self.min_dur:
            return []
        turn = Turn(speaker, start, end)
        self._closed.append(turn)
        return [("end", turn)] if announced else []


def _merge_adjacent(turns: list[Turn], min_gap: float) -> list[Turn]:
    """Join same-speaker turns separated by less than min_gap (after relabel)."""
    out: list[Turn] = []
    last: dict[int, int] = {}  # speaker -> index in out
    for t in turns:
        i = last.get(t.speaker)
        if i is not None and t.start - out[i].end <= min_gap:
            out[i] = Turn(t.speaker, out[i].start, max(out[i].end, t.end))
            continue
        last[t.speaker] = len(out)
        out.append(t)
    return out
