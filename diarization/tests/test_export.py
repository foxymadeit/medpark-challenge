import csv
import json
from datetime import datetime

from diarizer.export import build_session, clock, summary, write_all
from diarizer.timeline import Turn

START = datetime(2026, 9, 25, 14, 2, 0).timestamp()
TURNS = [Turn(1, 3.12, 10.88), Turn(2, 11.0, 14.5), Turn(1, 15.0, 16.0)]
LABELS = {1: "Speaker 1", 2: "Ana"}


def session():
    return build_session(TURNS, LABELS, session_start=START, source="mic", model="resnet34")


def test_clock_is_local_wall_time_with_millis():
    assert clock(START + 3.12) == "14:02:03.120"


def test_session_lists_turns_with_three_fields_each():
    s = session()
    first = s["turns"][0]
    assert first["speaker"] == "Speaker 1"
    assert first["start_clock"] == "14:02:03.120"
    assert first["end_clock"] == "14:02:10.880"
    assert s["speakers"]["Speaker 1"]["talk_time"] == 8.76
    assert s["speakers"]["Ana"]["turns"] == 1


def test_summary_prints_one_line_per_turn():
    text = summary(session())
    assert "Speaker 1  14:02:03.120 → 14:02:10.880  (7.76 s)" in text
    ana = next(line for line in text.splitlines() if line.startswith("Ana "))
    assert ana.split() == ["Ana", "14:02:11.000", "→", "14:02:14.500", "(3.50", "s)"]


def test_write_all_creates_json_rttm_csv(tmp_path):
    paths = write_all(tmp_path, session(), uri="meeting")
    names = sorted(p.name for p in paths)
    assert names == ["meeting.csv", "meeting.json", "meeting.rttm"]
    data = json.loads((tmp_path / "meeting.json").read_text())
    assert len(data["turns"]) == 3
    rttm = (tmp_path / "meeting.rttm").read_text().splitlines()
    assert rttm[0] == "SPEAKER meeting 1 3.120 7.760 <NA> <NA> Speaker_1 <NA> <NA>"
    rows = list(csv.DictReader((tmp_path / "meeting.csv").open()))
    assert rows[1]["speaker"] == "Ana"
    assert rows[1]["start"] == "14:02:11.000"


def test_file_mode_numbers_speakers_by_first_appearance():
    from diarizer.export import consecutive_labels
    turns = [Turn(5, 0.0, 1.0), Turn(2, 1.0, 2.0), Turn(5, 2.0, 3.0), Turn(9, 3.0, 4.0)]
    names = {5: "Speaker 5", 2: "Ana", 9: "Speaker 9"}
    assert consecutive_labels(turns, names) == {5: "Speaker 1", 2: "Ana", 9: "Speaker 2"}
