from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

GLOSSARY_PATH = Path(__file__).resolve().parents[1] / "data" / "medical_ro_ru_en.json"


@lru_cache(maxsize=1)
def load_glossary(path: str | None = None) -> dict:
    """The bundled table, plus the rows of the site glossary at
    LIMINAL_SITE_GLOSSARY (terms a site's administrators approved) when set."""
    target = Path(path) if path else GLOSSARY_PATH
    data = json.loads(target.read_text(encoding="utf-8"))
    site = os.environ.get("LIMINAL_SITE_GLOSSARY")
    if not path and site and Path(site).is_file():
        extra = json.loads(Path(site).read_text(encoding="utf-8")).get("aligned") or []
        data = {**data, "aligned": list(data.get("aligned", [])) + extra}
    return data
