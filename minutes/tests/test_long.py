import json
import re

import pytest

from eval.long import build
from eval.meetings import DATE
from mom.dates import resolve
from mom.extract import windows
from mom.normalize import load_transcript


@pytest.fixture(scope="module")
def meeting(tmp_path_factory):
    out = tmp_path_factory.mktemp("long")
    build(out)
    lines = load_transcript(out / "long01.txt")
    gold = json.loads((out / "long01.gold.json").read_text(encoding="utf-8"))
    return lines, gold


def test_one_hour_no_names_meeting_is_long_enough(meeting):
    lines, gold = meeting
    words = sum(len(l.text.split()) for l in lines)
    assert 600 <= len(lines) <= 900 and 8000 <= words <= 10000
    assert 55 * 60 <= lines[-1].start <= 60 * 60
    assert {l.speaker for l in lines} == {f"Speaker {n}" for n in range(1, 8)}
    assert len(gold["decisions"]) >= 12 and len(gold["actions"]) >= 12
    assert len(gold["not_decisions"]) >= 4 and len(gold["old"]) >= 2 and len(gold["patients"]) >= 2


def test_answer_key_matches_the_transcript(meeting):
    lines, gold = meeting
    by_id = {l.id: l for l in lines}
    cited = [i for v in gold["decisions"].values() for i in v] + [i for a in gold["actions"].values() for i in a["lines"]] \
        + [i for v in gold["old"].values() for i in v] + gold["not_decisions"] + [i for v in gold["proposals"].values() for i in v]
    assert all(i in by_id for i in cited)
    for key, a in gold["actions"].items():
        line = by_id[a["lines"][0]]
        assert re.fullmatch(r"Speaker \d", a["owner"]) and line.speaker == a["owner"], key   # "I'll do it": owner is the speaker
        assert resolve(line.text, DATE) == a["deadline"], key
    text = " ".join(l.text for l in lines)
    assert all(name in text for name in gold["patients"])


def test_two_decisions_are_settled_a_window_after_they_were_proposed(meeting):
    lines, gold = meeting
    parts = [{l.id for l in w} for w in windows(lines)]
    crossing = [k for k, p in gold["proposals"].items()
                if not any(set(p + gold["decisions"][k]) <= w for w in parts)]
    assert len(crossing) >= 2
