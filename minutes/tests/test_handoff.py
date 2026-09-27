"""The diarizer's session feeds the minutes: `mom report transcript --session s.json`.
Fixture: the diarizer demo's reference turns (tests/fixtures/make_demo_session.py)."""

import json
from pathlib import Path

import pytest

from mom.normalize import load_transcript
from mom.pipeline import attendees
from mom.write import check_body

SESSION = Path(__file__).parent / "fixtures" / "demo_session.json"
TURNS = json.loads(SESSION.read_text(encoding="utf-8"))["turns"]


def _whisper(tmp_path, segments):
    f = tmp_path / "asr.json"
    f.write_text(json.dumps({"segments": segments}), encoding="utf-8")
    return f


def _most_overlap(a, b):
    total = {}
    for t in TURNS:
        total[t["speaker"]] = total.get(t["speaker"], 0.0) + max(0.0, min(b, t["end"]) - max(a, t["start"]))
    return max(total, key=total.get)


def test_every_line_goes_to_the_speaker_whose_turns_overlap_it_most(tmp_path):
    # ASR segments a little off the turn edges, carrying the ASR's own labels, which the diarizer must override
    segs = [{"start": t["start"] + 0.12, "end": t["end"] + 0.3, "text": f"line {i}", "speaker": "SPEAKER_07"}
            for i, t in enumerate(TURNS)]
    lines = load_transcript(_whisper(tmp_path, segs), session=SESSION)
    assert len(lines) == len(TURNS)
    for l in lines:
        assert l.speaker == _most_overlap(l.start, l.end), l


def test_a_line_in_a_pause_goes_to_the_nearest_turn(tmp_path):
    first = TURNS[0]
    lines = load_transcript(_whisper(tmp_path, [{"start": first["end"] + 0.15, "end": first["end"] + 0.6, "text": "da"}]),
                            session=SESSION)
    assert lines[0].speaker == first["speaker"]


def test_attendees_match_the_diarizer_speakers_and_talk_time(tmp_path):
    speakers = json.loads(SESSION.read_text(encoding="utf-8"))["speakers"]
    segs = [{"start": t["start"] + 0.05, "end": t["end"] - 0.05, "text": "text"} for t in TURNS]
    lines = load_transcript(_whisper(tmp_path, segs), session=SESSION)
    people = attendees(lines, "en")
    assert [p["name"] for p in people] == ["Ion Rusu", "Maria Ciobanu", "Participant 1", "Participant 2", "Participant 3"]
    talk = {}
    for l in lines:
        talk[l.speaker] = talk.get(l.speaker, 0.0) + l.end - l.start
    for name, s in speakers.items():
        assert talk[name] == pytest.approx(s["talk_time"], rel=0.05), name


def test_diarizer_attach_output_is_read_as_is(tmp_path):
    # `diarizer attach` writes {"session_start", "lines": [{speaker, start, end, text, start_clock, end_clock}]}
    f = tmp_path / "meeting.transcript.json"
    f.write_text(json.dumps({"session_start": "2026-09-24T14:10:00.000", "lines": [
        {"speaker": "Speaker 2", "start": 1.0, "end": 3.0, "text": "Bună ziua.", "start_clock": "14:10:01.000", "end_clock": "14:10:03.000"},
        {"speaker": None, "start": 3.0, "end": 4.0, "text": "zgomot", "start_clock": "", "end_clock": ""}]}), encoding="utf-8")
    lines = load_transcript(f)
    assert [(l.speaker, l.start, l.end) for l in lines] == [("Speaker 2", 1.0, 3.0), ("", 3.0, 4.0)]


def test_an_enrolled_name_in_a_sentence_is_rejected():
    rows = [{"id": "T1", "kind": "topic", "text": "Contract"}, {"id": "N1", "kind": "note", "topic": "T1", "text": "Contractul expiră."}]
    body = "\\topic{T1}{Contract}\n\\noted{N1}{Ion Rusu a comunicat că contractul expiră.}\n"
    _, errors = check_body(body, rows, {"N1": "contractul expiră"}, names=["Ion Rusu", "Speaker 1"], lang="ro")
    assert any("Ion Rusu" in e for e in errors)
