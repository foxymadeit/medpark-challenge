"""ASR ruler: CER/WER against a hand-corrected gold window, plus gold-free LID checks.

    python -m asr_llm.score transcript.json [--gold data/gold_0-180s.txt --window 180]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .clean import _fold
from .glossary import load_glossary
from .pipeline import load_transcript
from .schemas import SpeechSegment

ALLOWED = {"ro", "ru", "en"}


def edit_distance(ref: list, hyp: list) -> int:
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i]
        for j, h in enumerate(hyp, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h)))
        prev = cur
    return prev[-1]


def error_rate(ref: list, hyp: list) -> float:
    return edit_distance(ref, hyp) / max(1, len(ref))


def cyrillic_share(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    return sum("Ѐ" <= c <= "ӿ" for c in letters) / len(letters)


def script_mismatch(seg: SpeechSegment) -> bool:
    """`ro`/`en` written mostly in Cyrillic, or `ru` mostly in Latin. The `Ело фост` bug."""
    if seg.language not in ALLOWED:  # unknown or mixed ("ro+ru"): no single script to expect
        return False
    share = cyrillic_share(seg.text)
    return share < 0.5 if seg.language == "ru" else share > 0.5


def glossary_terms() -> set[str]:
    terms = set()
    for row in load_glossary().get("aligned", []):
        for lang in ("ro", "ru", "en"):
            value = _fold(row.get(lang) or "")
            if len(value) >= 3:
                terms.add(value)
    return terms


def report(segments: list[SpeechSegment], gold: str | None = None, window_s: float | None = None) -> dict:
    tagged = [s for s in segments if s.language]
    out = {
        "segments": len(segments),
        "tagged": len(tagged),
        "off_set_lid": sum(not set(s.language.split("+")) <= ALLOWED for s in tagged),
        "mixed": sum("+" in s.language for s in tagged),
        "script_mismatch": sum(script_mismatch(s) for s in tagged),
        "cyrillic_share": round(cyrillic_share(" ".join(s.text for s in segments)), 3),
    }
    if gold is not None:
        hyp_segments = [s for s in segments if window_s is None or s.start < window_s]
        ref = _fold(gold)
        hyp = _fold(" ".join(s.text for s in hyp_segments))
        out["cer"] = round(error_rate(list(ref), list(hyp)), 3)
        out["wer"] = round(error_rate(ref.split(), hyp.split()), 3)
        in_gold = {t for t in glossary_terms() if t in ref}
        out["terms_in_gold"] = len(in_gold)
        out["terms_hit"] = sum(t in hyp for t in in_gold)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("transcript", type=Path)
    parser.add_argument("--gold", type=Path, default=None)
    parser.add_argument("--window", type=float, default=None, help="Score only segments starting before this second.")
    args = parser.parse_args()
    segments = load_transcript(args.transcript).segments
    gold = args.gold.read_text(encoding="utf-8") if args.gold else None
    print(json.dumps(report(segments, gold, args.window), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
