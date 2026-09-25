from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

# Whisper's initial_prompt is tiny (~224 tokens). Dumping Harvard Health
# into it hurts more than it helps. Keep a hospital-meeting seed and optionally
# append a handful of short dictionary terms.
HOSPITAL_SEED = [
    "pacient",
    "diagnostic",
    "tratament",
    "internare",
    "externare",
    "consiliu medical",
    "protocol",
    "laborator",
    "CT",
    "RMN",
    "MRI",
    "EKG",
    "ecografie",
    "anestezie",
    "chirurgie",
    "oncologie",
    "cardiologie",
    "antibiotice",
    "doză",
    "urgență",
    "deadline",
    "action item",
    "responsible",
    "board",
    "бюджет",
    "пациент",
    "диагноз",
    "лечение",
]


@lru_cache(maxsize=1)
def load_harvard_terms(path: str) -> list[str]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    terms: list[str] = []
    for letter_terms in data.values():
        for row in letter_terms:
            term = (row.get("term") or "").strip()
            if term:
                terms.append(term)
    return terms


def whisper_initial_prompt(glossary_path: Path | None = None, extra: int = 40) -> str:
    terms = list(HOSPITAL_SEED)
    if glossary_path and glossary_path.exists():
        harvard = [
            t for t in load_harvard_terms(str(glossary_path))
            if 3 <= len(t) <= 24 and " " not in t
        ]
        terms.extend(harvard[:extra])
    # Whisper copies the prompt style; keep it as a term list, not a paragraph.
    uniq: list[str] = []
    seen: set[str] = set()
    for term in terms:
        key = term.lower()
        if key not in seen:
            seen.add(key)
            uniq.append(term)
    return ", ".join(uniq)
