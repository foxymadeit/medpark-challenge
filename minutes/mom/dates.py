"""Deadline phrases -> ISO dates, in Romanian, Russian and English.

Only what can be pinned to one day resolves: a weekday, tomorrow, "in N
days/weeks", the end of the week or month, or an explicit date. "Next week"
or "as soon as possible" stay unresolved: real minutes leave a deadline out
rather than guess one (research/rules.md, R6).
"""

import calendar
import datetime as dt
import re

WEEKDAYS = {  # stems, so every case form matches: vineri, пятницу/пятницы/пятница, Friday
    0: ("luni", "понедельн", "monday"), 1: ("marți", "marti", "вторник", "tuesday"),
    2: ("miercuri", "сред", "wednesday"), 3: ("joi", "четверг", "thursday"),
    4: ("vineri", "пятниц", "friday"), 5: ("sâmbăt", "sambat", "суббот", "saturday"),
    6: ("duminic", "воскресень", "sunday"),
}
MONTHS = {
    1: ("ianuarie", "январ", "january"), 2: ("februarie", "феврал", "february"), 3: ("martie", "март", "march"),
    4: ("aprilie", "апрел", "april"), 5: ("mai", "мая", "май", "may"), 6: ("iunie", "июн", "june"),
    7: ("iulie", "июл", "july"), 8: ("august", "август", "august"), 9: ("septembrie", "сентябр", "september"),
    10: ("octombrie", "октябр", "october"), 11: ("noiembrie", "ноябр", "november"), 12: ("decembrie", "декабр", "december"),
}
NUMBERS = {  # small counts said as words
    "una": 1, "unu": 1, "o": 1, "două": 2, "doua": 2, "doi": 2, "trei": 3, "patru": 4, "cinci": 5, "șase": 6, "sase": 6,
    "șapte": 7, "sapte": 7, "opt": 8, "nouă": 9, "zece": 10, "paisprezece": 14,
    "один": 1, "одну": 1, "одна": 1, "два": 2, "две": 2, "три": 3, "четыре": 4, "пять": 5, "шесть": 6, "семь": 7,
    "десять": 10, "четырнадцать": 14,
    "one": 1, "a": 1, "an": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "ten": 10, "fourteen": 14,
}
VAGUE = ("viitoare", "следующ", "next week", "curând", "curand", "asap", "possible", "posibil", "скорее", "soon")


def resolve(phrase: str, meeting_date: str) -> str:
    p = " " + (phrase or "").lower().strip() + " "
    if not p.strip():
        return ""
    explicit = _explicit(p, meeting_date)
    if explicit:
        return explicit
    if not meeting_date or any(v in p for v in VAGUE):
        return ""
    base = dt.date.fromisoformat(meeting_date)
    if re.search(r"\b(azi|astăzi|astazi|today|tonight)\b|сегодня", p):
        return base.isoformat()
    if re.search(r"\b(mâine|maine|tomorrow)\b|завтра", p) and "послезавтра" not in p:
        return (base + dt.timedelta(days=1)).isoformat()
    if re.search(r"\bpoimâine\b|\bpoimaine\b|послезавтра|day after tomorrow", p):
        return (base + dt.timedelta(days=2)).isoformat()
    if re.search(r"sfârșitul lunii|sfarsitul lunii|конца месяца|end of the month|end of month", p):
        return base.replace(day=calendar.monthrange(base.year, base.month)[1]).isoformat()
    if re.search(r"sfârșitul săptămânii|sfarsitul saptamanii|конца недели|end of the week|end of week", p):
        return (base + dt.timedelta(days=(4 - base.weekday()) % 7)).isoformat()
    m = re.search(r"(?:în(?: termen de)?|in|peste|через|в течение|within)\s+(\w+)\s+(zile|zi|дн|день|дня|days?|săptămân|saptaman|недел|weeks?)", p)
    if m:
        n = int(m.group(1)) if m.group(1).isdigit() else NUMBERS.get(m.group(1))
        if n:
            weeks = m.group(2).startswith(("săpt", "sapt", "недел", "week"))
            return (base + dt.timedelta(days=n * (7 if weeks else 1))).isoformat()
    for wd, stems in WEEKDAYS.items():
        if any(re.search(r"(?<!\w)" + re.escape(s), p) for s in stems):
            ahead = (wd - base.weekday()) % 7 or 7   # the same weekday means next week's
            return (base + dt.timedelta(days=ahead)).isoformat()
    return ""


def _explicit(p: str, meeting_date: str) -> str:
    year_default = int(meeting_date[:4]) if meeting_date else None
    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", p)
    if m:
        return _iso(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.search(r"\b(\d{1,2})[./](\d{1,2})[./](\d{4}|\d{2})\b", p)
    if m:
        y = int(m.group(3)) + (2000 if len(m.group(3)) == 2 else 0)
        return _iso(y, int(m.group(2)), int(m.group(1)))
    for month, stems in MONTHS.items():
        for s in stems:
            if len(s) < 4 and s not in ("mai", "мая", "май", "may"):
                continue
            m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:de\s+)?" + re.escape(s) + r"\w*(?:\s+(\d{4}))?", p) or \
                re.search(re.escape(s) + r"\w*\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?", p)
            if m:
                year = int(m.group(2)) if m.group(2) else year_default
                return _iso(year, month, int(m.group(1))) if year else ""
    return ""


def _iso(y, m, d) -> str:
    try:
        return dt.date(y, m, d).isoformat()
    except (TypeError, ValueError):
        return ""
