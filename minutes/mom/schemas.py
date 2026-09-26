"""What flows through the pipeline: transcript lines, checked facts, meeting details."""

import datetime as dt
from dataclasses import asdict, dataclass, field

LANGS = ("ro", "ru", "en")
MEETING_TYPES = ("medical", "executive", "administrative")

# How each language names the meeting (Romanian hospital law 95/2006 names the
# consiliul medical and comitetul director; see research/corpus.md).
BODY_NAME = {
    "ro": {"medical": "Consiliului Medical", "executive": "Comitetului Executiv", "administrative": "Consiliului Administrativ"},
    "ru": {"medical": "Медицинского совета", "executive": "Исполнительного комитета", "administrative": "Административного совета"},
    "en": {"medical": "Medical Board", "executive": "Executive Committee", "administrative": "Administrative Board"},
}
_EN_MONTHS = "January February March April May June July August September October November December".split()


@dataclass(frozen=True)
class Line:
    id: str            # L0001, the unit every fact cites
    start: float       # seconds from the start of the recording
    end: float
    speaker: str       # diarizer label or name, "" if unknown
    text: str


@dataclass
class Fact:
    id: str                        # T1 topic, N1 noted/presented, D1 decision, A1 action, C1 needs confirmation
    kind: str                      # topic | note | decision | action
    text: str                      # in the meeting's own words (mixed languages allowed)
    evidence: list                 # line IDs, e.g. ["L0012", "L0013"]
    quote: str = ""                # verbatim span from those lines
    topic: str = ""                # T-id this fact belongs to
    who: str = ""                  # for notes: who presented or said it
    owner: str = ""                # for actions (and recommendations)
    deadline_phrase: str = ""      # as said: "până vineri"
    deadline: str = ""             # ISO date, only when it resolves
    vote: str = ""                 # as said: "pro 4, contra 0" / "unanimously"
    why: str = ""                  # the model's short reasoning, checked for line IDs, never printed
    status: str = "ok"             # ok | confirm | dropped
    problems: list = field(default_factory=list)


@dataclass
class Meeting:
    type: str = "medical"
    number: str = ""
    date: str = ""                 # ISO date of the meeting
    start: str = ""                # HH:MM
    end: str = ""
    place: str = ""
    chair: str = ""                # "Name, role"
    secretary: str = ""
    attendees: list = field(default_factory=list)   # [{"name": .., "role": ..}]
    apologies: list = field(default_factory=list)
    quorum: str = ""
    next_meeting: str = ""

    def title(self, lang: str) -> str:
        name = BODY_NAME[lang][self.type]
        date = format_date(self.date, lang)
        return {"ro": f"al ședinței {name} din {date}", "ru": f"заседания {name} от {date}",
                "en": f"of the {name}, {date}"}[lang]


def format_date(iso: str, lang: str) -> str:
    """ISO date -> how the minutes write it: 28.09.2026 (RO, RU), 28 September 2026 (EN)."""
    if not iso:
        return ""
    d = dt.date.fromisoformat(iso)
    return f"{d.day} {_EN_MONTHS[d.month - 1]} {d.year}" if lang == "en" else d.strftime("%d.%m.%Y")


def to_dict(obj) -> dict:
    return asdict(obj)
