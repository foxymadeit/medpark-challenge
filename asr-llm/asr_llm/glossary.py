from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

GLOSSARY_PATH = Path(__file__).resolve().parents[1] / "data" / "medical_ro_ru_en.json"


@lru_cache(maxsize=1)
def load_glossary(path: str | None = None) -> dict:
    target = Path(path) if path else GLOSSARY_PATH
    return json.loads(target.read_text(encoding="utf-8"))


def _short_terms(aligned: list[dict]) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()

    def add(row: dict) -> None:
        for lang in ("ro", "ru", "en"):
            value = (row.get(lang) or "").strip()
            if not value or len(value) > 28:
                continue
            key = value.casefold()
            if key in seen:
                continue
            seen.add(key)
            terms.append(value)

    ops = [row for row in aligned if row.get("source") == "hospital-ops"]
    rest = [row for row in aligned if row.get("source") != "hospital-ops"]
    for row in ops + rest:
        add(row)
    return terms


def asr_hotwords(max_terms: int = 80) -> str:
    """Short term list for faster-whisper `hotwords`. Do not dump the full JSON."""
    data = load_glossary()
    terms = _short_terms(data.get("aligned", []))
    return " ".join(terms[:max_terms])


def whisper_initial_prompt(max_terms: int = 40) -> str:
    data = load_glossary()
    terms = _short_terms(data.get("aligned", []))
    return ", ".join(terms[:max_terms])


def llm_term_table(max_rows: int = 90) -> str:
    """Aligned RO / RU / EN names for the minutes LLM. Fits a 4k context."""
    data = load_glossary()
    lines = ["ro | ru | en"]
    for row in data.get("aligned", [])[:max_rows]:
        lines.append(f"{row['ro']} | {row['ru']} | {row['en']}")
    return "\n".join(lines)
