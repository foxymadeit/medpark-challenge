"""Standard medical terms in Romanian, Russian and English, for the writing
step. The table (data/medical_ro_ru_en.json, see data/NOTICE.md) is read once;
terms_for() picks the rows whose term appears in the facts, so the model uses
the standard form in each language. It never adds a fact."""

import json
import re
from functools import lru_cache
from pathlib import Path

from .verify import fold

DATA = Path(__file__).resolve().parent.parent / "data" / "medical_ro_ru_en.json"
LANGS = ("ro", "ru", "en")
STEM = 5   # words this long or longer also match inflected forms (infarct -> infarctul)


def _stem(word: str) -> str:
    return word if len(word) < STEM else word[:max(STEM, len(word) - 2)]


@lru_cache(maxsize=1)
def _table() -> tuple:
    """(row, [(lang, term, stems)]) for every aligned row; "nor = noradrenalină"
    and "eco = ecografie / ecocardiografie" give one alternative per side."""
    out = []
    for row in json.loads(DATA.read_text(encoding="utf-8"))["aligned"]:
        forms = []
        for lang in LANGS:
            for alt in re.split(r"\s*[=/]\s*", row.get(lang, "")):
                words = fold(alt.replace("…", "")).split()
                if words:
                    forms.append((lang, alt.strip(), tuple(_stem(w) for w in words)))
        out.append((row, forms))
    return tuple(out)


def terms_for(texts, lang: str, limit: int = 24) -> list:
    """Rows whose term occurs in texts, most specific (longest) first. Each
    result is the row plus "matched": the form found in the text."""
    words = set(fold(" ".join(texts)).split())
    prefixes = words | {w[:n] for w in words for n in range(STEM, len(w))}
    hits = []
    for row, forms in _table():
        for _, term, stems in forms:
            if all((s in prefixes) if len(s) >= STEM else (s in words) for s in stems):
                if row.get(lang):
                    hits.append((len(stems), len(term), {**row, "matched": term}))
                break
    hits.sort(key=lambda h: (-h[0], -h[1]))
    return [h[2] for h in hits[:limit]]
