"""A person rewrites one sentence of the minutes before they are sent.

The sentence is stored with its item in the app (what the email says) and
replaced in the minutes' render state (what the PDFs and DOCX say): as
written in the minutes language, and as the local minutes model translates
it in the other two. If the model does not answer within TIMEOUT_S, the
other languages carry the sentence as written. Sentences go into the LaTeX
bodies through the minutes' own escape, and every body is parsed again.

Blocks are found by fact ID (\\decision{D1}, \\action{A1}, \\noted{N1},
\\summary{S1}); an item still waiting for a person sits in the body as
\\needsconfirmation{C<n>}, numbered as minutes/mom/write.py plan() does.
Kept after an edit, it becomes its own block again under its topic.
"""

import json
import logging
import os
import unicodedata
from pathlib import Path

import names

log = logging.getLogger("liminal.sentences")
LANGUAGE = {"ro": "Romanian", "ru": "Russian", "en": "English"}
TIMEOUT_S = float(os.getenv("LIMINAL_TRANSLATE_TIMEOUT_S", "30"))
MAX_TEXT = 2000
TEXT_BLOCKS = ("summary", "noted", "presented", "decision", "action", "needsconfirmation")
OWN_BLOCK = {"decision": "decision", "action": "action", "note": "noted"}   # a kept item's own command
_ENDS_TOPIC = ("topic", "needsconfirmation", "nextmeeting")


def clean(raw, limit: int = MAX_TEXT) -> str:
    """A sentence as typed -> as stored (line breaks become spaces). Raises ValueError."""
    text = str(raw or "").strip()
    if any(unicodedata.category(c).startswith("C") and c not in "\n\r\t" for c in text):
        raise ValueError("A sentence cannot hold control characters.")
    text = " ".join(text.split())
    if not 0 < len(text) <= limit:
        raise ValueError(f"A sentence has 1 to {limit} characters.")
    return text


def translate(text: str, src: str, dst: str) -> str | None:
    """The sentence in `dst` from the local minutes model (loopback only,
    minutes/mom/llm.py), or None when it does not answer in time."""
    llm = names.mom("llm")
    llm.TIMEOUT = TIMEOUT_S   # this process asks the model for single sentences only
    try:
        model = llm.LocalLLM(os.getenv("MOM_LLM_MODEL", llm.DEFAULT_MODEL), os.getenv("MOM_LLM_URL", llm.DEFAULT_URL))
        out = model.chat(f"Translate the user's sentence from {LANGUAGE[src]} to {LANGUAGE[dst]}. It is one line "
                         "of hospital meeting minutes. Keep names, numbers, dates and medical terms exact. "
                         "Reply with the translation only.", text, max_tokens=600, think=False)
    except Exception as e:   # unreachable, slow or odd: the sentence stays as written
        log.warning("no translation to %s (%s)", dst, type(e).__name__)
        return None
    out = " ".join(str(out).split()).strip()
    return out[:MAX_TEXT] or None


def texts(text: str, src: str, langs, ask: bool = True) -> tuple[dict, bool]:
    """{lang: sentence} for every body, and whether every language got a translation."""
    out, complete = {}, True
    for lang in langs:
        if lang == src:
            out[lang] = text
            continue
        translated = translate(text, src, lang) if ask and complete else None
        complete = complete and translated is not None   # a model that did not answer is not asked again
        out[lang] = translated or text
    return out, complete


def _facts(minutes_dir: Path) -> list[dict]:
    facts_file = next(minutes_dir.glob("*.facts.json"), None)
    return json.loads(facts_file.read_text(encoding="utf-8")).get("facts", []) if facts_file else []


def topic_of(minutes_dir: Path, fact_id: str) -> str | None:
    return next((f.get("topic") for f in _facts(minutes_dir) if f.get("id") == fact_id), None)


def waiting_id(minutes_dir: Path, fact_id: str) -> str | None:
    """The C-ID an item waiting for a person has in the bodies (write.py plan())."""
    kept = [f for f in _facts(minutes_dir) if f.get("status") in ("ok", "confirm")]
    topics = {f["id"] for f in kept if f.get("kind") == "topic"}
    waiting = [f["id"] for f in kept
               if f["status"] == "confirm" or (f.get("kind") != "topic" and f.get("topic") not in topics)]
    return f"C{waiting.index(fact_id) + 1}" if fact_id in waiting else None


def set_sentence(state: dict, fact_id: str, waiting: str | None, by_lang: dict, keep: dict | None = None) -> None:
    """Put the sentence into each body. `keep` ({"kind", "topic", "extra": lang -> {owner, deadline}})
    turns a waiting item into its own block under its topic."""
    lx = names.latexcheck()
    bodies = {}
    for lang, body in (state.get("bodies") or {}).items():
        blocks = lx.parse(body)
        at = next((i for i, b in enumerate(blocks) if b.fact_id == fact_id and b.kind in TEXT_BLOCKS), None)
        if at is None and waiting:
            at = next((i for i, b in enumerate(blocks) if b.fact_id == waiting and b.kind == "needsconfirmation"), None)
        if at is None:   # not in the documents (a decision added in the app): the email still has it
            bodies[lang] = body
            continue
        text = lx.escape(by_lang.get(lang, by_lang.get(next(iter(by_lang)))))
        b = blocks[at]
        if keep and b.kind == "needsconfirmation" and keep.get("kind") in OWN_BLOCK:
            del blocks[at]
            kind = OWN_BLOCK[keep["kind"]]
            extra = {k: lx.escape(v) for k, v in (keep.get("extra") or {}).get(lang, {}).items()}
            args = {"id": fact_id, "owner": extra.get("owner", ""), "deadline": extra.get("deadline", ""),
                    "text": text, "vote": ""}
            blocks.insert(_place(blocks, keep.get("topic"), at), lx.Block(kind, {k: args[k] for k in lx.COMMANDS[kind]}))
        else:
            blocks[at] = lx.Block(b.kind, {**b.args, "text": text})
        bodies[lang] = lx.serialise(blocks)
        lx.parse(bodies[lang])   # raises BodyError (a ValueError) if the result is not a clean body
    state["bodies"] = bodies


def _place(blocks, topic: str | None, fallback: int) -> int:
    """Where a kept item goes: the end of its topic, else before the items waiting for a person."""
    start = next((i for i, b in enumerate(blocks) if b.kind == "topic" and b.fact_id == topic), None)
    if start is None:
        return next((i for i, b in enumerate(blocks) if b.kind == "needsconfirmation"), fallback)
    end = start + 1
    while end < len(blocks) and blocks[end].kind not in _ENDS_TOPIC:
        end += 1
    return end
