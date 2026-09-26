"""Learning from the edits people make to the minutes, on site, without retraining.

Every edit is kept as a `corrections` document: which meeting, item and field,
the value before and after, who and when. Nothing else. Word swaps inside
those edits ("pneumania" -> "pneumonia") become glossary candidates; an
administrator approves one and it lands in LIMINAL_DATA/site_glossary.json,
which the term corrector and the minutes writer read through
LIMINAL_SITE_GLOSSARY (see README).
"""

import difflib
import hashlib
import json
import os
import re
import uuid

import store
from security import now_iso

_WORD = re.compile(r"[^\W\d_]+(?:-[^\W\d_]+)*", re.UNICODE)
_CYRILLIC = re.compile(r"[Ѐ-ӿ]")
MAX_WORDS = 3
MIN_LETTERS = 4
SIMILAR = 0.6   # a respelling, not a reworded phrase ("aprobat" -> "respins" is 0.14)


def record(meeting_id: str, item: str, field: str, before, after, user: dict) -> None:
    """Keep one edit; unchanged values are not an edit."""
    if before == after:
        return
    store.put("corrections", {"id": uuid.uuid4().hex, "meetingId": meeting_id, "item": item, "field": field,
                              "before": before, "after": after, "by": user["id"], "at": now_iso()})


def term_pairs(before: str, after: str) -> list[tuple[str, str]]:
    """Replaced spans of 1 to 3 words, every word at least 4 letters on both
    sides, that differ by more than case and still look alike (a spelling fix,
    not a new phrase). Punctuation is not a word."""
    a, b = _WORD.findall(before or ""), _WORD.findall(after or "")
    ops = difflib.SequenceMatcher(None, [w.casefold() for w in a], [w.casefold() for w in b], autojunk=False)
    pairs = []
    for tag, i1, i2, j1, j2 in ops.get_opcodes():
        heard, fixed = a[i1:i2], b[j1:j2]
        if (tag == "replace" and len(heard) <= MAX_WORDS and len(fixed) <= MAX_WORDS
                and all(len(w) >= MIN_LETTERS for w in heard + fixed)
                and difflib.SequenceMatcher(None, " ".join(heard).casefold(),
                                            " ".join(fixed).casefold()).ratio() >= SIMILAR):
            pairs.append((" ".join(heard), " ".join(fixed)))
    return pairs


def _key(heard: str, corrected: str) -> str:
    return hashlib.sha256(f"{heard.casefold()}\n{corrected.casefold()}".encode()).hexdigest()[:32]


def candidates() -> list[dict]:
    """(heard -> corrected) pairs across every text edit, most frequent first."""
    found: dict[str, dict] = {}
    for c in store.all_docs("corrections"):
        if not isinstance(c.get("before"), str) or not isinstance(c.get("after"), str):
            continue
        for heard, fixed in term_pairs(c["before"], c["after"]):
            k = _key(heard, fixed)
            row = found.setdefault(k, {"heard": heard, "corrected": fixed, "count": 0, "meetingIds": [],
                                       "lang": "ru" if _CYRILLIC.search(fixed) else "ro"})
            row.update(heard=heard, corrected=fixed, count=row["count"] + 1)   # the latest spelling wins
            if c["meetingId"] not in row["meetingIds"] and len(row["meetingIds"]) < 5:
                row["meetingIds"].append(c["meetingId"])
    for k, row in found.items():
        row["approved"] = store.get("glossary-approved", k) is not None
    return sorted(found.values(), key=lambda r: -r["count"])


def approve(heard: str, corrected: str, lang: str, user: dict) -> dict:
    """Append one row to the site glossary (same shape as the medical one), once."""
    path = store.DATA / "site_glossary.json"
    with store.tx():
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {
            "meta": {"site": "Terms approved by this site's administrators from corrections to the minutes."},
            "aligned": []}
        row = {"source": "site", lang: corrected, "heard": heard}
        if row not in data["aligned"]:
            data["aligned"].append(row)
            tmp = path.with_suffix(".tmp")
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
        store.put("glossary-approved", {"id": _key(heard, corrected), "heard": heard, "corrected": corrected,
                                        "lang": lang, "by": user["id"], "at": now_iso()})
    return row
