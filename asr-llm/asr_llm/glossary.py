from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

GLOSSARY_PATH = Path(__file__).resolve().parents[1] / "data" / "medical_ro_ru_en.json"


@lru_cache(maxsize=1)
def load_glossary(path: str | None = None) -> dict:
    target = Path(path) if path else GLOSSARY_PATH
    return json.loads(target.read_text(encoding="utf-8"))
