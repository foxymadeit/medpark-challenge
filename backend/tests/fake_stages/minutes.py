"""Stands in for `mom report WORK/transcript.json --session S --type T ... --out WORK/minutes`.
Set FAKE_CONFIRM=1 to leave one item for a person to confirm."""
import json
import os
import sys
from pathlib import Path

args = sys.argv[1:]
out = Path(args[args.index("--out") + 1])
out.mkdir(parents=True, exist_ok=True)
assert json.loads(Path(args[0]).read_text())["segments"], "transcript.json must hold the segments"
facts = [
    {"id": "T1", "kind": "topic", "text": "Protocolul ATI", "evidence": ["L0001"], "status": "ok"},
    {"id": "D1", "kind": "decision", "text": "Se aprobă protocolul ATI.", "evidence": ["L0002", "L0003"], "status": "ok"},
    {"id": "A1", "kind": "action", "text": "Send the report.", "evidence": ["L0004"], "owner": "Speaker 3",
     "deadline": "2026-10-02", "status": "ok"},
]
if os.getenv("FAKE_CONFIRM") == "1":
    facts.append({"id": "A2", "kind": "action", "text": "Order new leads.", "evidence": ["L0002"], "owner": "",
                  "deadline": "", "status": "confirm", "problems": ["action without an owner"]})
stem = "MoM_2026-09-26_medical"
(out / f"{stem}.facts.json").write_text(json.dumps({"meeting": {}, "facts": facts}))
for lang in ("ro", "ru", "en"):
    (out / f"{stem}_{lang}.pdf").write_bytes(b"%PDF-1.7 fake " + lang.encode())
    (out / f"{stem}_{lang}.docx").write_bytes(b"PK fake")
