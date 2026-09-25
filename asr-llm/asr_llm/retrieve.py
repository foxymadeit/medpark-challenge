from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

from .glossary import load_glossary

_WORD = re.compile(r"[^\W_]+", re.UNICODE)
_DIM = 4096
_NGRAM = 4


def _ngrams(text: str) -> list[str]:
    folded = " ".join(_WORD.findall(text.casefold()))
    if len(folded) < _NGRAM:
        return [folded] if folded else []
    return [folded[i : i + _NGRAM] for i in range(len(folded) - _NGRAM + 1)]


def _hash_vec(text: str) -> np.ndarray:
    vec = np.zeros(_DIM, dtype=np.float32)
    for gram in _ngrams(text):
        vec[hash(gram) % _DIM] += 1.0
    n = float(np.linalg.norm(vec))
    if n:
        vec /= n
    return vec


def _tokens(text: str) -> set[str]:
    return {t for t in _WORD.findall(text.casefold()) if len(t) >= 4}


@dataclass(frozen=True)
class GlossaryHit:
    ro: str
    ru: str
    en: str
    score: float
    source: str


def retrieve_terms(query: str, *, k: int = 24) -> list[GlossaryHit]:
    """Pick glossary rows that look like the transcript. No learned weights.

    This is retrieval, not training — it cannot overfit a neural net because
    there is no neural net. It can still fetch an unused term; the LLM prompt
    must say not to invent facts from the list.
    """
    data = load_glossary()
    docs: list[tuple[str, dict, str]] = []
    for row in data.get("aligned", []):
        blob = " ".join(row.get(lang) or "" for lang in ("ro", "ru", "en"))
        docs.append((blob, row, row.get("source") or "aligned"))
    for term in data.get("english_extra") or []:
        docs.append((term, {"ro": term, "ru": term, "en": term}, "english_extra"))

    q_vec = _hash_vec(query)
    q_tok = _tokens(query)
    scored: list[GlossaryHit] = []
    for blob, row, source in docs:
        cosine = float(q_vec @ _hash_vec(blob))
        overlap = len(q_tok & _tokens(blob))
        surface = 1.0 if any(
            (row.get(lang) or "").casefold() in query.casefold()
            for lang in ("ro", "ru", "en")
            if row.get(lang) and len(row[lang]) >= 4
        ) else 0.0
        score = cosine + 0.35 * overlap + 0.8 * surface
        if score <= 0:
            continue
        scored.append(
            GlossaryHit(
                ro=row.get("ro") or "",
                ru=row.get("ru") or "",
                en=row.get("en") or "",
                score=score,
                source=source,
            )
        )
    scored.sort(key=lambda h: h.score, reverse=True)
    uniq: list[GlossaryHit] = []
    seen: set[str] = set()
    for hit in scored:
        key = hit.en.casefold()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(hit)
        if len(uniq) >= k:
            break
    return uniq


def llm_glossary_for(transcript: str, *, k: int = 24) -> str:
    """Hospital-ops always in, plus retrieved ICD/Harvard rows for this text."""
    data = load_glossary()
    lines = [
        "ro | ru | en",
        "Use a glossary row ONLY if the transcript supports it. Do not add unused terms.",
    ]
    for row in data.get("aligned", []):
        if row.get("source") == "hospital-ops":
            lines.append(f"{row['ro']} | {row['ru']} | {row['en']}")
    hits = retrieve_terms(transcript, k=k)
    for hit in hits:
        if hit.source == "hospital-ops":
            continue
        lines.append(f"{hit.ro} | {hit.ru} | {hit.en}")
    return "\n".join(lines)
