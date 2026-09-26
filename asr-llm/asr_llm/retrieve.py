from __future__ import annotations

import re
import zlib
from dataclasses import dataclass
from functools import lru_cache

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
        # crc32, not hash(): str hashes change per process, which made retrieval non-reproducible.
        vec[zlib.crc32(gram.encode()) % _DIM] += 1.0
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
    definition: str = ""


@lru_cache(maxsize=1)
def _index() -> tuple[list[tuple[dict, str, set[str]]], np.ndarray]:
    """Glossary rows with their hash vectors, built once per process."""
    data = load_glossary()
    docs: list[tuple[dict, str, set[str]]] = []
    blobs: list[str] = []
    for row in data.get("aligned", []):
        blob = " ".join(row.get(lang) or "" for lang in ("ro", "ru", "en"))
        docs.append((row, row.get("source") or "aligned", _tokens(blob)))
        blobs.append(blob)
    for term in data.get("english_extra") or []:
        docs.append(({"ro": term, "ru": term, "en": term}, "english_extra", _tokens(term)))
        blobs.append(term)
    matrix = np.stack([_hash_vec(b) for b in blobs]) if blobs else np.zeros((0, _DIM), dtype=np.float32)
    return docs, matrix


def retrieve_terms(query: str, *, k: int = 24) -> list[GlossaryHit]:
    """Pick glossary rows that look like the transcript. No learned weights.

    This is retrieval, not training — it cannot overfit a neural net because
    there is no neural net. It can still fetch an unused term; the LLM prompt
    must say not to invent facts from the list.
    """
    docs, matrix = _index()
    if not docs:
        return []
    q_vec = _hash_vec(query)
    q_tok = _tokens(query)
    q_fold = query.casefold()
    cosines = matrix @ q_vec
    scored: list[GlossaryHit] = []
    for (row, source, tokens), cosine in zip(docs, cosines):
        overlap = len(q_tok & tokens)
        surface = 1.0 if any(
            (row.get(lang) or "").casefold() in q_fold
            for lang in ("ro", "ru", "en")
            if row.get(lang) and len(row[lang]) >= 4
        ) else 0.0
        score = float(cosine) + 0.35 * overlap + 0.8 * surface
        if score <= 0:
            continue
        scored.append(
            GlossaryHit(
                ro=row.get("ro") or "",
                ru=row.get("ru") or "",
                en=row.get("en") or "",
                score=score,
                source=source,
                definition=row.get("def_en") or "",
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
    hits = [hit for hit in retrieve_terms(transcript, k=k) if hit.source != "hospital-ops"]
    for rank, hit in enumerate(hits):
        # The best few carry a short definition so a model can tell which medical sense fits.
        meaning = f" — {hit.definition[:140]}" if hit.definition and rank < 5 else ""
        lines.append(f"{hit.ro} | {hit.ru} | {hit.en}{meaning}")
    return "\n".join(lines)
