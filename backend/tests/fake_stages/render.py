"""Stands in for `mom render MINUTES/MoM_<date>_<type>.render.json --type T`."""
import json
import sys
from pathlib import Path

state_file, new_type = Path(sys.argv[1]), sys.argv[sys.argv.index("--type") + 1]
state = json.loads(state_file.read_text())
stem = f"MoM_{state['meeting']['date']}_{new_type}"
for lang in ("ro", "ru", "en"):
    (state_file.parent / f"{stem}_{lang}.pdf").write_bytes(f"%PDF-1.7 fake {new_type} {lang}".encode())
    (state_file.parent / f"{stem}_{lang}.docx").write_bytes(b"PK fake")
state["meeting"]["type"] = new_type
moved = state_file.parent / f"{stem}.render.json"
moved.write_text(json.dumps(state))
if moved != state_file:
    state_file.unlink()
