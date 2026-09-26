from mom.extract import merge, windows
from mom.schemas import Line


def test_windows_cover_every_line_and_overlap_a_little():
    lines = [Line(f"L{i + 1:04d}", i * 10.0, i * 10.0 + 9, "Speaker 1", f"text {i}") for i in range(200)]  # 2000 s
    parts = windows(lines)
    assert len(parts) >= 3
    covered = {l.id for w in parts for l in w}
    assert covered == {l.id for l in lines}
    assert set(x.id for x in parts[0]) & set(x.id for x in parts[1])  # overlap exists


def test_merge_joins_continuing_topics_drops_overlap_duplicates_and_renumbers():
    w1 = {"topics": [{"id": "T1", "title": "Contractul RMN", "evidence": ["L0001"], "quote": "contractul RMN"}],
          "items": [{"id": "D1", "kind": "decision", "topic": "T1", "text": "Se aprobă reînnoirea contractului RMN.", "owner": "", "deadline_phrase": "",
                     "vote": "", "evidence": ["L0003"], "quote": "aprobăm reînnoirea", "why": ""}],
          "patients": [{"name": "Ana Lungu", "age": "70", "bed": "4"}]}
    w2 = {"topics": [{"id": "T1", "title": "Contractul RMN", "evidence": ["L0003"], "quote": "contractul"},
                     {"id": "T2", "title": "Paturi ATI", "evidence": ["L0009"], "quote": "paturi"}],
          "items": [{"id": "D1", "kind": "decision", "topic": "T1", "text": "Se aprobă reînnoirea contractului RMN", "owner": "", "deadline_phrase": "",
                     "vote": "", "evidence": ["L0003"], "quote": "aprobăm reînnoirea", "why": ""},
                    {"id": "A1", "kind": "action", "topic": "T2", "text": "Confirmă paturile.", "owner": "Speaker 2", "deadline_phrase": "luni",
                     "vote": "", "evidence": ["L0010"], "quote": "confirm eu", "why": ""}],
          "patients": [{"name": "Ana Lungu", "age": "70", "bed": "4"}]}
    facts, patients = merge([w1, w2])
    assert [f.id for f in facts] == ["T1", "T2", "D1", "A1"]
    assert next(f for f in facts if f.id == "A1").topic == "T2"
    assert len(patients) == 1


def test_a_window_whose_answer_breaks_is_read_in_halves():
    import json
    import re

    from mom.extract import extract
    from mom.schemas import Line

    lines = [Line(f"L{i:04d}", float(i * 10), float(i * 10 + 5), "Speaker 1", f"fraza {i}") for i in range(1, 41)]
    asked = []

    class Llm:
        def chat_json(self, system, user, schema, max_tokens=0, think=None, retry=True):
            n = len(re.findall(r"\nL\d{4} ", user))
            asked.append((n, retry))
            if n > 20:   # too dense for one answer: the JSON comes back cut off
                raise json.JSONDecodeError("cut off", "{", 1)
            first = user.split("Lines:\n")[1].split(" ")[0]
            return {"topics": [], "patients": [], "items": [{"id": "D1", "kind": "decision", "topic": "", "text": {"L0001": "Se aprobă bugetul anual.", "L0021": "Comisia de audit se reunește lunar."}[first],
                    "owner": "", "deadline_phrase": "", "vote": "", "evidence": [first], "quote": "fraza", "why": first}]}

    facts, _ = extract(Llm(), lines, "administrative")
    assert [n for n, _ in asked] == [40, 20, 20] and not any(r for _, r in asked)
    assert [f.evidence for f in facts if f.kind == "decision"] == [["L0001"], ["L0021"]]
