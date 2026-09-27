"""Rebuilds demo_session.json from the diarizer demo's reference turns
(diarization/demo/meeting.rttm) in the shape `diarizer file` writes
(diarizer/export.py build_session). Three voices stay anonymous, two are
enrolled names, as in a real meeting.

  python tests/fixtures/make_demo_session.py
"""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RTTM = HERE.parents[2] / "diarization" / "demo" / "meeting.rttm"
NAMES = {"David": "Speaker 1", "Sofia": "Speaker 2", "Alexandru": "Speaker 3", "Ion": "Ion Rusu", "Maria": "Maria Ciobanu"}

turns, speakers = [], {}
for line in RTTM.read_text().splitlines():
    f = line.split()
    start, dur, who = float(f[3]), float(f[4]), NAMES[f[7]]
    turns.append({"speaker": who, "start": round(start, 3), "end": round(start + dur, 3)})
    s = speakers.setdefault(who, {"talk_time": 0.0, "turns": 0})
    s["talk_time"] = round(s["talk_time"] + dur, 3)
    s["turns"] += 1
session = {"session_start": "2026-09-24T14:10:00.000", "source": "diarization/demo/meeting.wav (reference turns)",
           "model": "titanet_small", "speakers": speakers, "turns": turns}
(HERE / "demo_session.json").write_text(json.dumps(session, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"{len(turns)} turns, {len(speakers)} speakers")
