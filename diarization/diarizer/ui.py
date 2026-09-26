"""The terminal interface: one amber colour, a scrolling voice waveform, and
plain text around it. Small pure functions draw the pieces; Screen puts them
together for rich's Live display, which redraws in place about 12 times a
second. `--plain`, NO_COLOR or output to a pipe fall back to line-by-line text.

The waveform follows cava's trick: each column is one 50 ms loudness reading
drawn with the eighth blocks ▁▂▃▄▅▆▇█, so three text rows give 24 levels.
"""

import math
import time
from collections import deque
from pathlib import Path

import numpy as np
from rich.console import Console
from rich.text import Text

AMBER = "#ffb000"
BRIGHT, BASE, DIM = f"bold {AMBER}", AMBER, f"dim {AMBER}"
BLOCKS = " ▁▂▃▄▅▆▇█"
FLOOR_DB, TOP_DB = -62.0, -12.0


def level_db(samples) -> float:
    x = np.asarray(samples, dtype=np.float32)
    return 20 * math.log10(float(np.sqrt(np.mean(x * x))) + 1e-9) if x.size else FLOOR_DB


def wave(levels, width: int, rows: int = 3) -> list:
    """Loudness history as `rows` lines of eighth blocks, newest on the right."""
    vals = list(levels)[-width:]
    vals = [FLOOR_DB] * (width - len(vals)) + vals
    cells = rows * 8
    heights = [min(cells, max(0, round((v - FLOOR_DB) / (TOP_DB - FLOOR_DB) * cells))) for v in vals]
    return ["".join(BLOCKS[min(8, max(0, h - r * 8))] for h in heights) for r in range(rows - 1, -1, -1)]


def meter(frac: float, width: int) -> str:
    n = round(min(1.0, max(0.0, frac)) * width)
    return "█" * n + "░" * (width - n)


def mmss(seconds: float) -> str:
    s = int(max(0, seconds))
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60:02d}:{s % 60:02d}"


def spread(left: str, right: str, width: int) -> str:
    return left + " " * max(1, width - len(left) - len(right)) + right


class Screen:
    """What the live display shows. Feed it audio and diarizer events from
    the main loop; rich calls __rich__ from its own refresh thread."""

    def __init__(self, label, console: Console, title="DIARIZER"):
        self.label, self.console, self.title = label, console, title
        self.levels: deque = deque(maxlen=600)
        self.talk: dict = {}
        self.turns: dict = {}
        self.first: dict = {}
        self.log: deque = deque(maxlen=6)
        self.now: list = []      # everyone talking right now (two at once in overlaps)
        self.last = None         # who finished the most recent turn
        self.t0 = time.time()
        self.phase, self.hint, self.status, self.profile = "LIVE", "", "", ""
        self.progress = None     # 0..1 in file mode
        self.passage = ""        # shown while enrolling

    def audio(self, samples, sr: int = 16000) -> None:
        step = sr // 20
        for i in range(0, max(len(samples) - step + 1, 1), step):
            self.levels.append(level_db(samples[i:i + step]))

    def event(self, e, clock_at) -> None:
        """Log lines: ("new", sid, clock) when a voice is heard for the first
        time; ("turn", sid, start, end, seconds, back) when a turn ends, with
        back=True when the voice returns after someone else spoke."""
        kind = e[0]
        if kind == "start":
            sid = e[1]
            if sid not in self.first:
                self.first[sid] = e[2]
                self.log.appendleft(("new", sid, clock_at(e[2])))
            if sid not in self.now:
                self.now.append(sid)
        elif kind == "end":
            t = e[1]
            back = self.turns.get(t.speaker, 0) > 0 and self.last not in (None, t.speaker)
            self.talk[t.speaker] = self.talk.get(t.speaker, 0.0) + t.duration
            self.turns[t.speaker] = self.turns.get(t.speaker, 0) + 1
            self.first.setdefault(t.speaker, t.start)
            self.log.appendleft(("turn", t.speaker, clock_at(t.start), clock_at(t.end), t.duration, back))
            self.now = [x for x in self.now if x != t.speaker]
            self.last = t.speaker
        elif kind == "merge":
            for old, new in e[1].items():
                self.talk[new] = self.talk.get(new, 0.0) + self.talk.pop(old, 0.0)
                self.turns[new] = self.turns.get(new, 0) + self.turns.pop(old, 0)
                if old in self.first:
                    self.first[new] = min(self.first.pop(old), self.first.get(new, math.inf))
                self.now = list(dict.fromkeys(new if x == old else x for x in self.now))
                self.last = new if self.last == old else self.last
                self.log = deque(((k, new if sid == old else sid, *rest) for k, sid, *rest in self.log), maxlen=6)

    def voices(self) -> list:
        """Speaker ids in order of first appearance."""
        return sorted(self.first, key=self.first.get)

    def __rich__(self):
        w = max(40, self.console.width - 2)
        out = Text()
        rec = "●" if int(time.time() * 2) % 2 else "○"
        out.append(spread(f" SECURE MOM ▸ {self.title}", f"{rec} {self.phase} {mmss(time.time() - self.t0)} ", w + 1) + "\n", BRIGHT)
        out.append(" " + "─" * w + "\n", DIM)
        for row in wave(self.levels, w):
            out.append(" " + row + "\n", BASE)
        if self.progress is not None:
            out.append(f" DONE {meter(self.progress, w - 13)} {self.progress:>5.0%}\n", BRIGHT)
        if self.passage:
            out.append("\n")
            for line in _wrap(self.passage, w - 2):
                out.append(f"  {line}\n", BRIGHT)
            out.append("\n")
        now = " ▶ NOW  " + "  +  ".join(self.label(i).upper() for i in self.now) if self.now else " · LISTENING"
        out.append(now + "\n", BRIGHT if self.now else DIM)
        ids = sorted(self.talk, key=self.talk.get, reverse=True)
        if ids:
            out.append(" " + "─" * w + "\n", DIM)
            top = max(self.talk.values()) or 1.0
            name_w = min(24, max(len(self.label(i)) for i in ids[:8]) + 2)
            bar_w = max(8, w - name_w - 20)
            for i in ids[:8]:
                out.append(f" {self.label(i).upper()[:name_w - 1]:<{name_w}}{meter(self.talk[i] / top, bar_w)}"
                           f"  {mmss(self.talk[i])}  {self.turns[i]:>3} turn{'s' if self.turns[i] != 1 else ''}\n",
                           BRIGHT if i in self.now else BASE)
            if len(ids) > 8:
                out.append(f" + {len(ids) - 8} more voices\n", DIM)
        if self.log:
            out.append(" " + "─" * w + "\n", DIM)
            for item in self.log:
                if item[0] == "new":
                    out.append(f" {item[2][:8]}              + NEW VOICE  {self.label(item[1]).upper()}\n", BASE)
                else:
                    _, sid, a, b, d, back = item
                    out.append(f" {a[:8]} → {b[:8]}  {self.label(sid).upper():<22} {d:5.1f} s"
                               f"{'  ↺ BACK' if back else ''}\n", DIM)
        out.append(" " + "─" * w + "\n", DIM)
        out.append(spread(f" {self.hint}", f"{self.status} ", w + 1), BASE)
        return out


def _wrap(text: str, width: int) -> list:
    lines, cur = [], ""
    for word in text.split():
        if cur and len(cur) + 1 + len(word) > width:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    return lines + ([cur] if cur else [])


def summary(console: Console, session: dict, paths) -> None:
    """The end-of-session printout: talk time per person, then every turn."""
    w = min(console.width - 2, 96)
    turns = session["turns"]
    total = sum(s["talk_time"] for s in session["speakers"].values()) or 1.0
    console.print(Text(f" SESSION {session['session_start'][:19].replace('T', ' ')}  ·  "
                       f"{len(session['speakers'])} VOICES  ·  {len(turns)} TURNS", BRIGHT))
    console.print(Text(" " + "─" * w, DIM))
    for name, s in sorted(session["speakers"].items(), key=lambda kv: -kv[1]["talk_time"]):
        console.print(Text(f" {name.upper()[:23]:<24}{meter(s['talk_time'] / total, 24)}  {mmss(s['talk_time'])}"
                           f"  {s['talk_time'] / total:>4.0%}  {s['turns']:>3} turn{'s' if s['turns'] != 1 else ''}", BASE))
    console.print(Text(" " + "─" * w, DIM))
    for t in turns:
        console.print(Text(f" {t['start_clock']} → {t['end_clock']}  {t['speaker'].upper()}", DIM))
    console.print(Text(" " + "─" * w, DIM))
    for p in paths:
        try:
            p = Path(p).resolve().relative_to(Path.cwd())
        except ValueError:
            pass
        console.print(Text(f" saved {p}", BASE))
