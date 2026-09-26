"""Stands in for `python -m asr_llm.cli AUDIO --skip-llm --out WORK/asr.json`."""
import json
import sys
from pathlib import Path

audio, work = sys.argv[1], Path(sys.argv[2])
segments = [
    {"start": 0.0, "end": 4.0, "text": "Bună ziua, începem consiliul.", "language": "ro"},
    {"start": 4.0, "end": 9.0, "text": "Propun să aprobăm protocolul ATI.", "language": "ro"},
    {"start": 9.0, "end": 12.0, "text": "Да, согласен, утверждаем.", "language": "ru"},
    {"start": 12.0, "end": 16.0, "text": "I will send the report by Friday.", "language": "en"},
]
(work / "asr.json").write_text(json.dumps({"transcript": {"source": audio, "duration_s": 16, "asr_device": "cpu",
                                                          "asr_model": "fake", "segments": segments, "text": ""},
                                           "minutes": {}, "elapsed_s": {}}))
