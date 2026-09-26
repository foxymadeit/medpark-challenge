"""The check between the model and the minutes. Code, not the model, decides
whether each proposed fact stands on the transcript lines it cites.

  dropped  - it cites lines that do not exist, or its quote is not in them
  confirm  - it stands, but a detail could not be checked (an owner not in the
             evidence, a number or a name that appears nowhere); a person decides
  ok       - every check passed

A "decision" with no decision act in its evidence becomes a note (rules R1, R2).
A deadline nobody said is removed; one that was said is re-resolved here from
its phrase, whatever date the model proposed (R6).
"""

import re
import unicodedata
from dataclasses import replace

from rapidfuzz import fuzz

from .dates import resolve

QUOTE_MIN = 92          # rapidfuzz partial_ratio for a quote to count as found
DEADLINE_MIN = 85

# Decision acts, folded (no diacritics, lower case). Built from the corpus
# formulas (research/formula-counts.json) plus how people agree out loud.
DECISION_ACTS = (
    "aprob", "de acord", "decid", "decis", "hotar", "accept", "stabil", "votam", "votat", "vot ", "respin",
    "unanim", "facem asa", "asa facem", "ramane asa", "bine facem",
    "утвержд", "одобр", "решил", "решаем", "решено", "принима", "принят", "соглас", "договорил", "голос",
    "постанов", "отклон", "единоглас", "так и сделаем", "делаем так",
    "approv", "agree", "decid", "resolv", "accept", "go ahead", "let s do", "lets do", "carried", "vote",
    "reject", "unanim", "confirmed", "sign off", "signed off",
)
# Short agreements that settle a decision when a chair or member says them;
# matched as whole words, since "ok" or "bine" inside other words means nothing.
AGREEMENT_WORDS = ("ok", "okay", "bine", "facem", "aprobat", "хорошо", "ладно", "делаем", "fine", "done", "sure")
HONORIFICS = {"dl", "dna", "dnei", "dlui", "dr", "domnul", "doamna", "prof", "mr", "mrs", "ms", "д", "р", "д-р", "господин", "госпожа"}
_WORD = re.compile(r"\w+", re.UNICODE)


def fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", (text or "").lower().replace("ё", "е").replace("й", "и"))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(_WORD.findall(text))


def verify(facts, lines, meeting_date: str = "", attendees=()) -> list:
    by_id = {l.id: l for l in lines}
    known = [fold(a) for a in attendees if a]
    return [_check(f, by_id, meeting_date, known) for f in facts]


def _check(f, by_id, meeting_date, known):
    problems = list(f.problems)
    cited = [by_id[i] for i in f.evidence if i in by_id]
    if not f.evidence or len(cited) != len(f.evidence):
        return replace(f, status="dropped", problems=problems + ["cites a line that does not exist"])
    evidence = fold(" ".join(l.text for l in cited))
    speakers = fold(" ".join(l.speaker for l in cited))

    q = fold(f.quote)
    if len(q) < 8 or fuzz.partial_ratio(q, evidence) < QUOTE_MIN:
        return replace(f, status="dropped", problems=problems + ["quote not found in the cited lines"])

    status, kind, owner, who = "ok", f.kind, f.owner, f.who
    words = set(evidence.split())
    if kind == "decision" and not any(act in evidence for act in DECISION_ACTS) and not words & set(AGREEMENT_WORDS):
        kind = "note"
        problems.append("no decision act in the evidence: kept as a note")

    if owner and not _person_in(owner, evidence, speakers):
        status = "confirm"
        problems.append(f"owner {owner!r} is not named or speaking in the cited lines")
    if kind == "action" and not owner:
        status = "confirm"
        problems.append("action without an owner")
    if who and not _person_in(who, evidence, speakers):
        who = ""

    phrase, deadline = f.deadline_phrase, ""
    if phrase and fuzz.partial_ratio(fold(phrase), evidence) < DEADLINE_MIN:
        problems.append(f"deadline {phrase!r} was not said in the cited lines: removed")
        phrase = ""
    if phrase:
        deadline = resolve(phrase, meeting_date)

    for n in re.findall(r"\d+(?:[.,]\d+)?", f.text):
        if n.replace(",", ".") not in evidence.replace(",", "."):
            status = "confirm"
            problems.append(f"number {n} is not in the evidence")
    for name in _names(f.text):
        folded = fold(name)
        if folded not in evidence and folded not in speakers and not any(folded in k for k in known):
            status = "confirm"
            problems.append(f"name {name!r} appears nowhere in the evidence")

    bad_why = [i for i in re.findall(r"L\d{4}", f.why) if i not in by_id]
    if bad_why:
        problems.append(f"reasoning cites missing lines {bad_why}")
    return replace(f, kind=kind, owner=owner, who=who, deadline_phrase=phrase, deadline=deadline,
                   status=status, problems=problems)


_LABEL = re.compile(r"(?:speaker|vorbitor(?:ul)?|спикер|участник|говорящий)\s*(\d+)")


def _person_in(person: str, evidence: str, speakers: str) -> bool:
    label = _LABEL.fullmatch(fold(person))
    if label:   # "Speaker 2" / "Vorbitorul 2": the very same diarizer label must speak a cited line
        return label.group(1) in {m.group(1) for m in _LABEL.finditer(speakers)}
    words = [w for w in fold(person).split() if w not in HONORIFICS and len(w) > 2]
    if not words:
        return False
    if any(w in speakers.split() for w in words) or words[-1] in evidence.split():
        return True
    long_words = [w for w in words if len(w) >= 4]          # a unit such as "serviciul achizitii"
    return bool(long_words) and all(w[:5] in evidence for w in long_words)


_HONORIFIC_BEFORE = re.compile(r"(?:\b(?:dr|dl|dna|prof|mr|mrs|ms|domnul|doamna)\.?|д-р\.?|г-н|г-жа)\s*$", re.I)


def _names(text: str) -> list:
    """Capitalised words that look like personal names. A sentence's first word
    is skipped unless an honorific (Dr., dl, dna, Prof., д-р) comes right before it."""
    out = []
    for m in re.finditer(r"\b([A-ZĂÂÎȘȚА-ЯЁ][a-zăâîșțа-яё]{2,})\b", text):
        before = text[:m.start()].rstrip()
        after_honorific = bool(_HONORIFIC_BEFORE.search(before))
        if not after_honorific and (not before or before.endswith((".", "!", "?", ":"))):
            continue
        out.append(m.group(1))
    return out


def report(facts) -> dict:
    counts = {"ok": 0, "confirm": 0, "dropped": 0}
    for f in facts:
        counts[f.status] += 1
    counts["checked"] = counts["ok"] + counts["confirm"]
    counts["total"] = len(facts)
    return counts
