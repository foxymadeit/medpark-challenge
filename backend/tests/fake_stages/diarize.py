"""Stands in for `diarizer file AUDIO --out WORK/diarization`."""
import json
import sys
from pathlib import Path

out = Path(sys.argv[2]) / "diarization"
out.mkdir(parents=True, exist_ok=True)
turns = [{"speaker": "Speaker 1", "start": 0.0, "end": 9.0}, {"speaker": "Speaker 2", "start": 9.0, "end": 12.0},
         {"speaker": "Speaker 3", "start": 12.0, "end": 16.0}]
(out / "audio.json").write_text(json.dumps({"session_start": "2026-09-26T10:00:00", "turns": turns, "speakers": {}}))
