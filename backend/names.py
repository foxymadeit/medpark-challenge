"""Naming the people in finished minutes: the moderator gives a detected
speaker a real name, or merges two participants that are one person.

The minutes write an unnamed speaker as "Participantul 4" (ro), "Участник 4"
(ru) or "Participant 4" (en), minutes/mom/write.py; the transcript may still
say "Speaker 4". A name replaces every one of those forms, in the app's text
(what the email says) and in the render state's bodies and attendee lists
(what the PDFs and DOCX say). Names go into the LaTeX bodies through the
minutes' own escape, and every body is parsed again before it is saved.
"""

import re
import sys
import unicodedata
from pathlib import Path

PARTICIPANT = {"ro": "Participantul", "ru": "Участник", "en": "Participant"}   # minutes/mom/write.py
GENERIC = re.compile(r"^(?:participant(?:ul)?|speaker|vorbitor(?:ul)?|участник|спикер)\s*_?(\d+)$", re.I)
_LABEL = r"(?:participant\w*|участник\w*|speaker|vorbitor\w*|спикер\w*)"
MAX_NAME = 80


def latexcheck():
    """The minutes' body checker and escape: installed with the minutes
    (server image), or from the minutes folder next to the backend."""
    try:
        from mom import latexcheck as lx
    except ImportError:
        sys.path.append(str(Path(__file__).resolve().parent.parent / "minutes"))
        from mom import latexcheck as lx
    return lx


def clean_name(raw) -> str:
    """A name as a person typed it -> the name to store. Raises ValueError."""
    name = str(raw or "").strip()
    if any(unicodedata.category(c).startswith("C") for c in name):
        raise ValueError("A name cannot hold control characters.")
    name = " ".join(name.split())
    if not 0 < len(name) <= MAX_NAME:
        raise ValueError(f"A name has 1 to {MAX_NAME} characters.")
    if GENERIC.match(name):
        raise ValueError("Type the person's name, not a participant number.")
    return name


def number(p: dict) -> int | None:
    """The speaker number the minutes use for this participant, if any."""
    if p.get("speakerNumber") is not None:
        return int(p["speakerNumber"])
    found = GENERIC.match(str(p.get("name", "")).strip())
    return int(found.group(1)) if found else None


def named(p: dict) -> bool:
    return bool(str(p.get("name", "")).strip()) and not GENERIC.match(p["name"].strip())


def display(p: dict, lang: str) -> str:
    """How the minutes in `lang` write this participant."""
    n = number(p)
    return p["name"] if named(p) or n is None else f"{PARTICIPANT[lang]} {n}"


def mentions(p: dict, write=lambda s: s) -> re.Pattern | None:
    """Every way the text can name this participant, in any language.
    `write` turns the plain name into how it sits in the text (LaTeX escaped)."""
    forms = []
    n = number(p)
    if n is not None:
        forms.append(rf"{_LABEL}\s*_?0*{n}(?!\d)")
    if named(p):
        forms.append(re.escape(write(p["name"])) + r"(?!\w)")
    return re.compile(r"(?<!\w)(?:" + "|".join(forms) + ")", re.I) if forms else None


def retext(m: dict, p: dict, new: str) -> None:
    """The app's own text (summary, decisions, actions, items to confirm): p -> new."""
    pattern = mentions(p)
    if pattern is None:
        return
    swap = lambda text: pattern.sub(lambda _: new, text)   # noqa: E731  (a lambda: no backslash escapes in `new`)
    if m.get("summary"):
        m["summary"] = swap(m["summary"])
    for key, field in (("decisions", "text"), ("actionItems", "task"), ("needsConfirmation", "text")):
        for item in m.get(key) or []:
            if item.get(field):
                item[field] = swap(item[field])


def _bodies(state: dict, p: dict, new_by_lang) -> dict:
    lx = latexcheck()
    pattern = mentions(p, lx.escape)
    if pattern is None:
        return state.get("bodies") or {}
    bodies = {lang: pattern.sub(lambda _, lang=lang: lx.escape(new_by_lang(lang)), body)
              for lang, body in (state.get("bodies") or {}).items()}
    for body in bodies.values():
        lx.parse(body)   # raises BodyError (a ValueError) if the result is not a clean body
    return bodies


def rename_state(state: dict, p: dict, name: str) -> None:
    """The render state: p is called `name` in every body and attendee list."""
    state["bodies"] = _bodies(state, p, lambda lang: name)
    pattern = mentions(p)
    if pattern is None:
        return
    state["attendees"] = {lang: [{**a, "name": name} if pattern.fullmatch(a.get("name", "")) else a for a in people]
                          for lang, people in (state.get("attendees") or {}).items()}


def merge_state(state: dict, gone: dict, into: dict) -> None:
    """The render state: `gone` is written as `into` everywhere, and appears
    once in each attendee list, with the two talk times added up."""
    state["bodies"] = _bodies(state, gone, lambda lang: display(into, lang))
    theirs, ours = mentions(gone), mentions(into)
    if theirs is None:
        return
    attendees = {}
    for lang, people in (state.get("attendees") or {}).items():
        people = [dict(a) for a in people]
        target = next((a for a in people if ours and ours.fullmatch(a.get("name", ""))), None)
        out = []
        for a in people:
            if not theirs.fullmatch(a.get("name", "")):
                out.append(a)
            elif target is None:   # `into` never spoke: it takes the other's place in the list
                target = {**a, "name": display(into, lang)}
                out.append(target)
            else:
                target["role"] = _add_minutes(target.get("role", ""), a.get("role", ""))
        attendees[lang] = out
    state["attendees"] = attendees


def _add_minutes(a: str, b: str) -> str:
    """'2 min' + '3 min' -> '5 min'; a role without minutes stays as it is."""
    x, y = re.match(r"(\d+)\s*(.*)", a or ""), re.match(r"(\d+)\s*(.*)", b or "")
    if not y:
        return a
    if not x:
        return b
    return f"{int(x.group(1)) + int(y.group(1))} {x.group(2) or y.group(2)}".strip()
