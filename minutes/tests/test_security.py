"""One test per finding of the security review (2026-09-26)."""

import os

import pytest

from mom.normalize import load_transcript
from mom.pipeline import attendees, run
from mom.schemas import Line, Meeting, fresh
from mom.write import check_body

PATIENTS = [{"name": "Maria Ionescu", "age": 67, "bed": 12}]


def test_patient_name_as_action_owner_becomes_initials():
    rows = [{"id": "T1", "kind": "topic", "text": "Contract"},
            {"id": "A1", "kind": "action", "topic": "T1", "text": "Trimite documentele.", "owner": "Maria Ionescu", "deadline": ""}]
    body = "\\topic{T1}{Contract}\n\\action{A1}{x}{}{Trimite documentele.}\n"
    out, _ = check_body(body, rows, {}, patients=PATIENTS, names=[], lang="ro")
    assert "Ionescu" not in out and "M.I." in out


def test_patient_name_as_speaker_label_becomes_initials():
    people = attendees([Line("L0001", 0.0, 40.0, "Maria Ionescu", "Bună ziua.")], "ro", PATIENTS)
    assert "Ionescu" not in people[0]["name"]


def test_deeply_nested_json_is_read_as_text_not_a_crash(tmp_path):
    f = tmp_path / "t.json"
    f.write_text("[" * 200000 + "]" * 200000)
    load_transcript(f)   # must not raise RecursionError


def test_planted_symlink_is_replaced_not_followed(tmp_path):
    target, link = tmp_path / "victim.txt", tmp_path / "out.pdf"
    target.write_text("keep")
    os.symlink(target, link)
    fresh(link).write_text("new")
    assert target.read_text() == "keep" and not link.is_symlink()


@pytest.mark.parametrize("meeting", [Meeting(type="../../etc"), Meeting(type="medical", date="2026-09-26/../../x")])
def test_bad_meeting_type_or_date_is_refused_before_any_file(tmp_path, meeting):
    with pytest.raises(ValueError):
        run(tmp_path / "none.txt", tmp_path / "out", llm=None, meeting=meeting)
    assert not (tmp_path / "out").exists()
