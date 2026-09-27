"""Patients appear in the minutes as initials only (research/rules.md W5,
GDPR Art. 5(1)(c)). Names the model reported as patients are replaced
everywhere; a name right after a word like "pacienta" or "пациент" is
replaced even if the model missed it. Staff names are left alone."""

import re

_UP = "A-ZĂÂÎȘŞȚŢА-ЯЁ"
_NAME = rf"[{_UP}][\w'-]+"
_PATIENT_WORDS = (r"(?:pacient(?:a|ul|ei|ului|ă)?|bolnav(?:a|ul|ei|ului)?|"
                  r"пациент(?:ка|ки|ке|кой|а|у|ом|е)?|больн(?:ой|ая|ого|ому|ую)|patient)")
_AFTER_PATIENT = re.compile(rf"(?i:\b{_PATIENT_WORDS})\s+({_NAME}(?:\s+{_NAME}){{0,2}})")


def initials(name: str) -> str:
    parts = [p for p in re.split(r"\s+", name.strip()) if p and not p.endswith(".")]
    return "".join(p[0].upper() + "." for p in parts)


def anonymize_text(text: str, patients: list) -> str:
    for p in sorted(patients, key=lambda p: -len(p.get("name", ""))):
        name = p.get("name", "").strip()
        if not name:
            continue
        ini = p.get("initials") or initials(name)
        text = re.sub(re.escape(name), ini, text)
        surname = name.split()[-1]
        if len(surname) > 2:
            text = re.sub(rf"\b{re.escape(surname)}\b", ini, text)
    return _AFTER_PATIENT.sub(lambda m: m.group(0)[: m.start(1) - m.start(0)] + initials(m.group(1)), text)
