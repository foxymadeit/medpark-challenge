"""Snap near-miss medical terms back to their dictionary spelling, after ASR.

ASR mishears rare terms by a letter or two ("miocardită" as "miocradită",
"эхокардиография" as "эхокардеография"). Each utterance is compared, in its own
language, with the glossary's terms (ICD-10, hospital terms, and the Harvard
dictionary with Wikidata's human RO/RU labels). A span is replaced only when:

- it is at least MIN_CHARS long and scores at least THRESHOLD against the term,
  on a key that ignores case, diacritics and doubled letters;
- the difference is inside the word, not only in its ending. Romanian and
  Russian inflect ("ecografia", "ecografie", "эхокардиографии"); an ending is
  grammar, not an error, so it is never "corrected";
- the term is in the utterance's language (a Russian term never lands in a
  Romanian sentence).

Every change is kept, before and after, so a reviewer can undo it.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

from rapidfuzz import fuzz, process

from .glossary import load_glossary

THRESHOLD = 88.0
MIN_CHARS = 6
MAX_WORDS = 4
ENDING = 3  # letters at the end of a word that may change with inflection

_WORD = re.compile(r"[^\W\d_]+(?:-[^\W\d_]+)*", re.UNICODE)


def key(text: str) -> str:
    """Case, diacritics, ё and doubled letters folded; spaces kept."""
    text = unicodedata.normalize("NFKD", text.casefold().replace("ё", "е").replace("й", "и"))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"(.)\1+", r"\1", re.sub(r"\s+", " ", text)).strip()


@lru_cache(maxsize=1)
def _terms() -> dict[str, dict[int, dict[str, str]]]:
    """lang -> words in term -> {key: spelling}."""
    out: dict[str, dict[int, dict[str, str]]] = {"ro": {}, "ru": {}, "en": {}}
    data = load_glossary()
    rows = list(data.get("aligned", [])) + [{"en": t} for t in data.get("english_extra") or []]
    for row in rows:
        for lang in out:
            term = (row.get(lang) or "").strip()
            if len(term) < MIN_CHARS or any(ch.isdigit() for ch in term):
                continue
            n = len(term.split())
            if n <= MAX_WORDS:
                out[lang].setdefault(n, {})[key(term)] = term
    return out


def _only_ending_differs(a: str, b: str) -> bool:
    last_a, last_b = a.split(" ")[-1], b.split(" ")[-1]
    stem = 0
    while stem < min(len(last_a), len(last_b)) and last_a[stem] == last_b[stem]:
        stem += 1
    return a.rsplit(" ", 1)[:-1] == b.rsplit(" ", 1)[:-1] and stem >= max(len(last_a), len(last_b)) - ENDING


def _same_endings(a: str, b: str) -> bool:
    """Each word keeps its last two letters: the case ending ("пневманией") must
    not be overwritten by the dictionary form ("пневмония")."""
    wa, wb = a.split(" "), b.split(" ")
    return len(wa) == len(wb) and all(x[-2:] == y[-2:] for x, y in zip(wa, wb))


def _match_case(original: str, term: str) -> str:
    if original.isupper() and len(original) > 1:
        return term.upper()
    return term[:1].upper() + term[1:] if original[:1].isupper() else term[:1].lower() + term[1:]


def correct_text(text: str, language: str | None) -> tuple[str, list[dict]]:
    """(corrected text, [{before, after, score}]). Unknown language: English terms only."""
    lang = language if language in ("ro", "ru", "en") else "en"
    by_len = _terms()[lang]
    words = list(_WORD.finditer(text))
    taken = [False] * len(words)
    edits: list[tuple[int, int, str, dict]] = []
    for n in range(MAX_WORDS, 0, -1):
        choices = by_len.get(n)
        if not choices:
            continue
        for i in range(len(words) - n + 1):
            if any(taken[i : i + n]):
                continue
            start, end = words[i].start(), words[i + n - 1].end()
            span = text[start:end]
            k = key(span)
            if len(k.replace(" ", "")) < MIN_CHARS or k in choices:
                continue
            hit = process.extractOne(k, choices.keys(), scorer=fuzz.ratio, score_cutoff=THRESHOLD)
            if not hit or hit[0][:1] != k[:1] or _only_ending_differs(k, hit[0]) or not _same_endings(k, hit[0]):
                continue
            term = choices[hit[0]]
            new = " ".join(_match_case(w, t) for w, t in zip(span.split(), term.split()))
            edits.append((start, end, new, {"before": span, "after": new, "score": round(hit[1], 1)}))
            taken[i : i + n] = [True] * n
    for start, end, new, _ in sorted(edits, key=lambda e: e[0], reverse=True):
        text = text[:start] + new + text[end:]
    return text, [e[3] for e in sorted(edits, key=lambda e: e[0])]


def correct_segments(segments) -> list[dict]:
    """Correct each segment's text in place; returns every change with its time."""
    log = []
    for seg in segments:
        fixed, changes = correct_text(seg.text, seg.language)
        if changes:
            seg.text = fixed
            log.extend({"start": seg.start, "language": seg.language, **c} for c in changes)
    return log
