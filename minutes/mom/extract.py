"""Transcript lines -> proposed facts, one model call per window.

Windows of about 10 minutes overlap by one minute so nothing is lost at a
boundary; the merge joins topics that continue across windows and drops
duplicates from the overlap. Every window uses the same system prompt, so
the model server reuses its cache for that prefix. On a GPU several windows
can run at once (MOM_PARALLEL).
"""

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from rapidfuzz import fuzz

from .schemas import Fact
from .verify import fold

PROMPT = (Path(__file__).resolve().parent.parent / "prompts" / "extract.md").read_text(encoding="utf-8")
WINDOW_S = float(os.environ.get("MOM_WINDOW_S", "600"))
OVERLAP_S = float(os.environ.get("MOM_OVERLAP_S", "60"))
MAX_LINES = int(os.environ.get("MOM_WINDOW_LINES", "220"))
PARALLEL = int(os.environ.get("MOM_PARALLEL", "1"))

_STR = {"type": "string"}
_IDS = {"type": "array", "items": _STR}
SCHEMA = {
    "type": "object",
    "properties": {
        "topics": {"type": "array", "items": {"type": "object", "properties": {
            "id": _STR, "title": _STR, "evidence": _IDS, "quote": _STR},
            "required": ["id", "title", "evidence", "quote"]}},
        "items": {"type": "array", "items": {"type": "object", "properties": {
            "id": _STR, "kind": {"type": "string", "enum": ["note", "decision", "action"]}, "topic": _STR,
            "text": _STR, "owner": _STR, "deadline_phrase": _STR, "vote": _STR,
            "evidence": _IDS, "quote": _STR, "why": _STR},
            "required": ["id", "kind", "topic", "text", "owner", "deadline_phrase", "vote", "evidence", "quote", "why"]}},
        "patients": {"type": "array", "items": {"type": "object", "properties": {
            "name": _STR, "age": _STR, "bed": _STR}, "required": ["name", "age", "bed"]}},
    },
    "required": ["topics", "items", "patients"],
}


def windows(lines) -> list:
    """Consecutive slices of about WINDOW_S seconds (or MAX_LINES lines), each
    starting OVERLAP_S before the previous one ended."""
    out, i = [], 0
    while i < len(lines):
        t0, j = lines[i].start, i
        while j < len(lines) and lines[j].start - t0 < WINDOW_S and j - i < MAX_LINES:
            j += 1
        j = max(j, i + 1)
        out.append(lines[i:j])
        if j >= len(lines):
            break
        k = j
        while k > i + 1 and lines[j - 1].start - lines[k - 1].start < OVERLAP_S and (j - k) < MAX_LINES // 5:
            k -= 1
        i = k if k > i else j
    return out


def format_lines(lines) -> str:
    return "\n".join(f"{l.id} [{l.speaker or '?'}] {l.text}" for l in lines)


def extract(llm, lines, meeting_type: str, think=None) -> tuple:
    """-> (facts, patients). Facts are proposals; verify.verify decides what stands."""
    parts = windows(lines)
    user = lambda w: f"Meeting type: {meeting_type}.\n\nLines:\n{format_lines(w)}"  # noqa: E731
    call = lambda w: llm.chat_json(PROMPT, user(w), SCHEMA, max_tokens=4096, think=think)  # noqa: E731
    if PARALLEL > 1 and len(parts) > 1:
        with ThreadPoolExecutor(PARALLEL) as pool:
            results = list(pool.map(call, parts))
    else:
        results = [call(w) for w in parts]
    return merge(results)


def merge(results) -> tuple:
    topics, facts, patients = [], [], []
    counters = {"T": 0, "N": 0, "D": 0, "A": 0}

    def next_id(prefix):
        counters[prefix] += 1
        return f"{prefix}{counters[prefix]}"

    for r in results:
        topic_map = {}
        for t in r.get("topics") or []:
            title = str(t.get("title", "")).strip()
            same = next((x for x in topics if fuzz.token_set_ratio(fold(x.text), fold(title)) >= 85), None)
            if same:
                topic_map[t.get("id")] = same.id
                continue
            fact = Fact(next_id("T"), "topic", title, list(t.get("evidence") or []), quote=str(t.get("quote", "")))
            topics.append(fact)
            topic_map[t.get("id")] = fact.id
        for it in r.get("items") or []:
            kind = it.get("kind") if it.get("kind") in ("note", "decision", "action") else "note"
            text = str(it.get("text", "")).strip()
            evidence = list(it.get("evidence") or [])
            if _duplicate(facts, kind, text, evidence):
                continue
            prefix = {"note": "N", "decision": "D", "action": "A"}[kind]
            facts.append(Fact(next_id(prefix), kind, text, evidence, quote=str(it.get("quote", "")),
                              topic=topic_map.get(it.get("topic"), topics[-1].id if topics else ""),
                              owner=str(it.get("owner", "")).strip(), deadline_phrase=str(it.get("deadline_phrase", "")).strip(),
                              vote=str(it.get("vote", "")).strip(), why=str(it.get("why", ""))))
        for p in r.get("patients") or []:
            if p.get("name") and all(fold(p["name"]) != fold(q["name"]) for q in patients):
                patients.append({k: str(p.get(k, "")) for k in ("name", "age", "bed")})
    return topics + facts, patients


def _duplicate(facts, kind, text, evidence) -> bool:
    for f in facts:
        if f.kind != kind:
            continue
        if set(evidence) & set(f.evidence) and fuzz.token_set_ratio(fold(text), fold(f.text)) >= 70:
            return True
        if fuzz.token_set_ratio(fold(text), fold(f.text)) >= 92:
            return True
    return False
