"""End to end with the network switched off: any socket use fails the test."""
import json
import shutil
import socket

import pytest
from docx import Document

from mom.pipeline import run
from mom.schemas import Meeting
from mom.write import EXAMPLE

TRANSCRIPT = """[00:00:05] Speaker 1: Bună ziua, începem. Primul punct, contractul de mentenanță pentru RMN.
[00:00:12] Speaker 2: Contractul actual expiră la sfârșitul lunii, trebuie reînnoit.
[00:00:20] Speaker 1: Propun să începem reînnoirea săptămâna aceasta. Suntem de acord? Pro 4, contra 0.
[00:00:28] Speaker 3: Da, de acord. Verific eu condițiile până pe 30 septembrie.
[00:00:35] Speaker 2: Și cine trimite documentele la minister?
"""
EXTRACTION = {
    "topics": [{"id": "T1", "title": "Contractul de mentenanță RMN", "evidence": ["L0001"], "quote": "contractul de mentenanță pentru RMN"}],
    "items": [
        {"id": "N1", "kind": "note", "topic": "T1", "text": "Contractul actual de mentenanță pentru RMN expiră la sfârșitul lunii.", "owner": "", "deadline_phrase": "", "vote": "",
         "evidence": ["L0002"], "quote": "Contractul actual expiră la sfârșitul lunii", "why": "L0002 reports"},
        {"id": "D1", "kind": "decision", "topic": "T1", "text": "Se începe reînnoirea contractului în această săptămână.", "owner": "", "deadline_phrase": "", "vote": "pro 4, contra 0",
         "evidence": ["L0003", "L0004"], "quote": "Suntem de acord? Pro 4, contra 0", "why": "L0003 votes, L0004 agrees"},
        {"id": "A1", "kind": "action", "topic": "T1", "text": "Verifică condițiile de reînnoire.", "owner": "Speaker 3", "deadline_phrase": "până pe 30 septembrie", "vote": "",
         "evidence": ["L0004"], "quote": "Verific eu condițiile până pe 30 septembrie", "why": "L0004 takes it"},
        {"id": "A2", "kind": "action", "topic": "T1", "text": "Trimite documentele la minister.", "owner": "", "deadline_phrase": "", "vote": "",
         "evidence": ["L0005"], "quote": "cine trimite documentele la minister", "why": "L0005 asks, nobody takes it"},
    ],
    "patients": [],
}


class FakeLLM:
    model = "fake-model"
    stats = {}

    def chat_json(self, system, user, schema, max_tokens=0, think=None):
        return EXTRACTION

    def chat(self, system, user, schema=None, max_tokens=0, think=None):
        lang = "ru" if "Russian" in system.split("\n")[0] else "en" if "English" in system.split("\n")[0] else "ro"
        return EXAMPLE[lang].replace("30.09.2026", "30.09.2026").replace("\\needsconfirmation{C1}", "\\needsconfirmation{C1}")


@pytest.fixture
def no_network(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("network used")
    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


@pytest.mark.skipif(not shutil.which("latexmk"), reason="needs TeX Live")
def test_transcript_to_six_documents_offline(tmp_path, no_network):
    t = tmp_path / "meeting.txt"
    t.write_text(TRANSCRIPT, encoding="utf-8")
    result = run(t, tmp_path / "out", FakeLLM(), Meeting(type="administrative", date="2026-09-24", start="14:00", number="3"))
    assert result["checks"]["ok"] == 4 and result["checks"]["confirm"] == 1
    for lang in ("ro", "ru", "en"):
        files = result["files"][lang]
        doc = Document(files["docx"])
        text = "\n".join(c.text for t_ in doc.tables for r in t_.rows for c in r.cells)
        assert "30" in text
    facts = json.loads((tmp_path / "out" / "MoM_2026-09-24_administrative.facts.json").read_text())
    a1 = next(f for f in facts["facts"] if f["id"] == "A1")
    assert a1["deadline"] == "2026-09-30" and a1["status"] == "ok"
    a2 = next(f for f in facts["facts"] if f["id"] == "A2")
    assert a2["status"] == "confirm"


def test_purge_deletes_only_old_minutes_files(tmp_path):
    import os
    import time
    from mom.cli import purge
    old, new, other = tmp_path / "MoM_2026-01-01_medical_ro.pdf", tmp_path / "MoM_2026-09-26_medical_ro.pdf", tmp_path / "notes.txt"
    for f in (old, new, other):
        f.write_text("x")
    stale = time.time() - 40 * 86400
    os.utime(old, (stale, stale))
    os.utime(other, (stale, stale))
    assert purge(tmp_path, 30) == 1
    assert not old.exists() and new.exists() and other.exists()
