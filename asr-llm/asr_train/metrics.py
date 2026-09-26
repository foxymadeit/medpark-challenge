"""CER/WER with the same normalisation as asr_llm.

Copied, not imported: importing asr_llm switches Hugging Face offline for the whole
process, which would block dataset and model downloads. tests/test_train_metrics.py
keeps the two copies in step.
"""

from __future__ import annotations

import re


def fold(text: str) -> str:
    """Same as asr_llm.clean._fold."""
    text = re.sub(r"[^\w\s]", " ", text.casefold().strip(), flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def edit_distance(ref: list, hyp: list) -> int:
    """Same as asr_llm.score.edit_distance (two-row Levenshtein)."""
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i]
        for j, h in enumerate(hyp, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h)))
        prev = cur
    return prev[-1]


def score(refs: list[str], hyps: list[str | None]) -> dict:
    """Corpus CER/WER: errors summed over all pairs, divided by total reference length."""
    ce = cn = we = wn = 0
    for r, h in zip(refs, hyps):
        r, h = fold(r), fold(h or "")
        ce += edit_distance(list(r), list(h))
        cn += len(r)
        we += edit_distance(r.split(), h.split())
        wn += len(r.split())
    return {"cer": round(ce / max(cn, 1), 4), "wer": round(we / max(wn, 1), 4), "n": len(refs)}
