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


def report(
    segments: list[SpeechSegment], gold: str | None = None, window_s: float | None = None, start_s: float = 0.0
) -> dict:
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
        # Midpoint, not start: engines cut at different places, and a segment starting at 93.99 s is mostly inside 94–181.
        mid = lambda s: (s.start + s.end) / 2  # noqa: E731
        hyp_segments = [s for s in segments if mid(s) >= start_s and (window_s is None or mid(s) < window_s)]
        ref = _fold(gold)
        hyp = _fold(" ".join(s.text for s in hyp_segments))
        out["cer"] = round(error_rate(list(ref), list(hyp)), 3)
        out["wer"] = round(error_rate(ref.split(), hyp.split()), 3)
        in_gold = {t for t in glossary_terms() if t in ref}
        out["terms_in_gold"] = len(in_gold)
        out["terms_hit"] = sum(t in hyp for t in in_gold)
    return out


def changes(base: list[SpeechSegment], other: list[SpeechSegment]) -> dict:
    """What a fusion run did relative to the acoustic pick, utterance by utterance."""
    moved: dict[str, int] = {}
    for a, b in zip(base, other):
        if a.text != b.text:
            key = f"{a.language}->{b.language}"
            moved[key] = moved.get(key, 0) + 1
    return {"changed": sum(moved.values()), "by_direction": moved}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("transcript", type=Path)
    parser.add_argument("--gold", type=Path, default=None)
    parser.add_argument("--window", type=float, default=None, help="Score only segments starting before this second.")
    parser.add_argument("--start", type=float, default=0.0, help="...and at or after this second.")
    parser.add_argument("--baseline", type=Path, default=None, help="Acoustic transcript to diff a fusion run against.")
    args = parser.parse_args()
    segments = load_transcript(args.transcript).segments
    gold = None
    if args.gold:  # "#" lines are notes and timestamps, not speech
        lines = args.gold.read_text(encoding="utf-8").splitlines()
        gold = "\n".join(line for line in lines if not line.lstrip().startswith("#"))
    out = report(segments, gold, args.window, args.start)
    if args.baseline:
        out["vs_baseline"] = changes(load_transcript(args.baseline).segments, segments)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
