"""Combine language specialists per utterance, then per span (ROVER-style voting).

Each utterance is transcribed by several systems: a Romanian specialist (SpeD-RoASR), a
Russian one (GigaAM-v3) and a multilingual one (Parakeet-TDT v3) for English. A specialist
fed the other language does not refuse; it writes a fluent-looking transliteration
("Пациентул" for "Pacientul"). What gives it away is the lexicon: those words are not
Russian words. So every hypothesis is tagged with the language its script and vocabulary
fit, and scored by how much of it is real vocabulary of that language (wordfreq Zipf
frequencies, bundled offline), scaled by how much of the utterance it covers.

1. Per utterance, the best-scoring hypothesis wins (the home language wins near-ties).
2. Per span: a run of two or more winner words that are not words of the winner's language
   is replaced by another system's words over the same time, when those are real words of
   their own language and in their own script. That catches a Russian aside inside a
   Romanian sentence.

References: ROVER (Fiscus, NIST 1997); monolingual decodes chosen per span, Weiner et al.
2021 (arXiv:2109.00921).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from wordfreq import zipf_frequency

from .glossary import load_glossary

LANGS = ("ro", "ru", "en")
VALID_ZIPF = 2.5  # a word at least this frequent counts as vocabulary of the language
HOME_BIAS = 0.03
MIN_RUN = 2


@dataclass(frozen=True)
class Word:
    start: float
    end: float
    text: str


def _clean(word: str) -> str:
    return "".join(c for c in word.casefold() if c.isalpha() or c == "-").strip("-")


def script(word: str) -> str | None:
    letters = [c for c in word if c.isalpha()]
    if not letters:
        return None
    cyr = sum("Ѐ" <= c <= "ӿ" for c in letters)
    return "cyr" if cyr == len(letters) else "lat" if cyr == 0 else "mixed"


@lru_cache(maxsize=1)
def _glossary_words() -> dict[str, frozenset[str]]:
    out: dict[str, set[str]] = {lang: set() for lang in LANGS}
    for row in load_glossary().get("aligned", []):
        for lang in LANGS:
            out[lang].update(_clean(w) for w in (row.get(lang) or "").split() if len(w) >= 4)
    return {k: frozenset(v) for k, v in out.items()}


@lru_cache(maxsize=65536)
def zipf(word: str, lang: str) -> float:
    w = _clean(word)
    if not w:
        return 0.0
    if w in _glossary_words()[lang]:
        return 4.5  # a medical term is vocabulary even when the general word list never saw it
    return zipf_frequency(w, lang)


def valid(word: str, lang: str) -> bool:
    wanted = "cyr" if lang == "ru" else "lat"
    return script(word) == wanted and zipf(word, lang) >= VALID_ZIPF


def language_of(words: list[Word]) -> str:
    """Cyrillic text is Russian; Latin text is Romanian or English, whichever vocabulary fits."""
    scripts = [script(w.text) for w in words]
    if scripts.count("cyr") > len(words) / 2:
        return "ru"
    ro = sum(zipf(w.text, "ro") for w in words)
    en = sum(zipf(w.text, "en") for w in words)
    return "en" if en > ro * 1.15 else "ro"


def fit(words: list[Word], lang: str) -> float:
    """Mean share of real vocabulary, each word weighted by how common it is (0..1)."""
    if not words:
        return 0.0
    wanted = "cyr" if lang == "ru" else "lat"
    return sum(min(zipf(w.text, lang), 5.0) / 5.0 for w in words if script(w.text) == wanted) / len(words)


def choose(hyps: dict[str, list[Word]], home: str = "ro") -> tuple[str, str, float]:
    """(system, language, score) of the best hypothesis for one utterance."""
    most = max((len(w) for w in hyps.values()), default=0) or 1
    best = ("", home, -1.0)
    for name, words in hyps.items():
        if not words:
            continue
        lang = language_of(words)
        score = fit(words, lang) * min(1.0, len(words) / (0.8 * most)) + (HOME_BIAS if lang == home else 0.0)
        if score > best[2]:
            best = (name, lang, score)
    return best


def merge_spans(base: list[Word], base_lang: str, others: dict[str, list[Word]]) -> tuple[list[Word], list[str]]:
    """Replace runs of non-words in the winner with real words another system heard there."""
    words, switched = list(base), []
    i = 0
    while i < len(words):
        if valid(words[i].text, base_lang):
            i += 1
            continue
        j = i
        while j < len(words) and not valid(words[j].text, base_lang):
            j += 1
        if j - i >= MIN_RUN:
            t0, t1 = words[i].start, words[j - 1].end
            for other in others.values():
                if not other:
                    continue
                lang = language_of(other)
                if lang == base_lang:
                    continue
                inside = [w for w in other if w.end > t0 and w.start < t1]
                if inside and all(valid(w.text, lang) for w in inside):
                    words = words[:i] + inside + words[j:]
                    j = i + len(inside)
                    switched.append(lang)
                    break
        i = j
    return words, switched


def combine(hyps: dict[str, list[Word]], home: str = "ro") -> dict:
    """One utterance: {text, language, system, score, switched}."""
    system, lang, score = choose(hyps, home)
    if not system:
        return {"text": "", "language": None, "system": None, "score": 0.0, "switched": []}
    words, switched = merge_spans(hyps[system], lang, {k: v for k, v in hyps.items() if k != system})
    language = "+".join([lang] + sorted(set(switched))) if switched else lang
    return {"text": " ".join(w.text for w in words), "language": language, "system": system,
            "score": round(score, 3), "switched": switched}
