import io

import numpy as np
from rich.console import Console

from diarizer.timeline import Turn
from diarizer.ui import BLOCKS, Screen, level_db, meter, mmss, summary, wave


def test_wave_draws_newest_on_the_right_in_eighths():
    rows = wave([-62.0, -12.0], width=4, rows=3)
    assert len(rows) == 3 and all(len(r) == 4 for r in rows)
    assert [r[-1] for r in rows] == ["█", "█", "█"]  # loudest reading fills all three rows
    assert all(r[0] == " " for r in rows)            # silence and padding stay empty
    mid = wave([-37.0], width=1, rows=3)             # halfway: bottom full, middle half, top empty
    assert mid[2] == "█" and mid[1] in BLOCKS[3:6] and mid[0] == " "


def test_meter_time_and_level_helpers():
    assert meter(0.5, 10) == "█████░░░░░" and meter(2, 4) == "████" and meter(-1, 3) == "░░░"
    assert mmss(75) == "01:15" and mmss(3725) == "1:02:05"
    assert level_db(np.zeros(800)) < -150 and abs(level_db(np.full(800, 0.1)) + 20) < 0.1


def test_screen_counts_talk_and_follows_merges():
    s = Screen(lambda i: f"Speaker {i}", Console(file=io.StringIO(), width=80))
    clk = lambda t: f"{t:05.1f}"  # noqa: E731
    s.event(("start", 1, 0.0), clk)
    s.event(("start", 2, 3.5), clk)                  # overlap: both talking
    assert s.now == [1, 2]
    s.event(("end", Turn(1, 0.0, 4.0)), clk)
    s.event(("end", Turn(2, 3.5, 7.0)), clk)
    s.event(("start", 1, 8.0), clk)
    s.event(("end", Turn(1, 8.0, 9.0)), clk)          # speaker 1 comes back after speaker 2
    s.event(("end", Turn(3, 10.0, 11.0)), clk)
    s.event(("merge", {3: 2}), clk)
    assert s.talk == {1: 5.0, 2: 4.5} and s.turns == {1: 2, 2: 2} and s.now == []
    assert s.voices() == [1, 2]
    kinds = [item[0] for item in s.log]
    assert kinds.count("new") == 2 and s.log[1][5] is True  # the second turn of speaker 1 is marked back


def test_screen_and_summary_render_without_errors():
    out = io.StringIO()
    con = Console(file=out, width=90, force_terminal=True, color_system="truecolor")
    s = Screen(lambda i: "Dr. Ana Popescu" if i == 1 else f"Speaker {i}", con)
    s.audio(np.random.default_rng(0).standard_normal(16000).astype(np.float32) * 0.05)
    s.event(("end", Turn(1, 0.0, 4.0)), lambda t: "14:02:03.000")
    s.hint, s.status, s.progress = "[ENTER] FINISH", "CLOSE MIC · 24 dB", 0.4
    con.print(s)
    summary(con, {"session_start": "2026-09-26T14:00:00.000", "speakers": {"Dr. Ana Popescu": {"talk_time": 4.0, "turns": 1}},
                  "turns": [{"speaker": "Dr. Ana Popescu", "start_clock": "14:00:00.000", "end_clock": "14:00:04.000"}]},
            ["sessions/x.json"])
    text = out.getvalue()
    assert "SECURE MOM" in text and "DR. ANA POPESCU" in text and "saved sessions/x.json" in text
