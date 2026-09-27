import json

from mom.export import meeting_json
from mom.schemas import Fact, Line, Meeting

LINES = [
    Line("L0001", 0.0, 40.0, "Speaker 1", "Pacienta Maria Lungu, patul 12, are nevoie de RMN."),
    Line("L0002", 40.0, 70.0, "Speaker 2", "Verific eu contractul până vineri."),
    Line("L0003", 70.0, 90.0, "Speaker 1", "Cineva trimite documentele."),
]
FACTS = [
    Fact("T1", "topic", "Contract RMN", ["L0001"]),
    Fact("D1", "decision", "Se aprobă RMN.", ["L0001"], topic="T1"),
    Fact("A1", "action", "Verifică contractul.", ["L0002"], topic="T1", owner="Speaker 2", deadline="2026-09-25"),
    Fact("A2", "action", "Trimite documentele.", ["L0003"], topic="T1"),
    Fact("A3", "action", "Sună furnizorul.", ["L0003"], topic="T1", owner="Speaker 9", status="confirm"),
]
BODY = r"""\summary{S1}{Consiliul a aprobat RMN și reînnoirea contractului.}
\begin{agenda}
\agendaitem{T1}{Contract RMN}
\end{agenda}
\topic{T1}{Contract RMN}
\decision{D1}{Se aprobă RMN pentru pacienta M.L.}{}
\action{A1}{Participantul 2}{25.09.2026}{Verifică contractul.}
\action{A2}{}{}{Trimite documentele.}
\needsconfirmation{C1}{Cine sună furnizorul.}"""

# Meeting in frontend/src/types/meeting.ts (frontend-secure-mom branch)
REQUIRED = {"id", "title", "type", "status", "createdAt", "inputMode", "participants", "distributionList", "sendMode"}
OPTIONAL = {"startedAt", "endedAt", "audioFilename", "durationSeconds", "audioBytes", "participantSnapshots", "progress",
            "summary", "decisions", "actionItems", "transcript", "speakerTimeline", "sendScheduledAt", "sentAt",
            "sendingStartedAt", "deliveryFailedAt", "processingState", "deliveryState", "failureReference",
            "processingStartedAt", "processingEndsAt", "sendWindowSeconds", "reviewFlags", "demoGenerated",
            "reviewState", "templateId", "agendaTopics"}


def build():
    return meeting_json(Meeting(type="medical", date="2026-09-24"), FACTS, LINES, BODY, "ro",
                        patients=[{"name": "Maria Lungu", "age": 67, "bed": 12}])


def test_keys_are_the_frontend_meeting_type():
    m = build()
    assert REQUIRED <= m.keys() and m.keys() <= REQUIRED | OPTIONAL
    assert set(m["participants"][0]) <= {"id", "name", "speakerId", "speakerSlot", "speakingSeconds"}
    assert all(set(a) <= {"id", "task", "ownerParticipantId", "deadline", "sourceTimestampSeconds", "completed"} for a in m["actionItems"])
    assert set(m["transcript"][0]) == {"id", "speakerId", "startSeconds", "endSeconds", "text"}
    assert m["status"] == "ready" and m["reviewState"] == "needs_review" and m["type"] == "medical"


def test_owners_and_deadlines_resolve_or_stay_null():
    m = build()
    a1, a2 = m["actionItems"]
    assert a1 == {"id": "A1", "task": "Verifică contractul.", "ownerParticipantId": "participant-2", "deadline": "2026-09-25",
                  "completed": False, "sourceTimestampSeconds": 40.0}
    assert a2["ownerParticipantId"] is None and a2["deadline"] is None
    assert [a["id"] for a in m["actionItems"]] == ["A1", "A2"]      # confirm items go to reviewFlags instead
    assert m["reviewFlags"] == ["Cine sună furnizorul."]
    assert m["participants"][1]["name"] == "Participantul 2" and m["participants"][0]["speakingSeconds"] == 60


def test_no_patient_name_and_serialisable():
    text = json.dumps(build(), ensure_ascii=False)
    assert "Lungu" not in text and "M.L." in text
    assert build()["summary"].startswith("Consiliul a aprobat")
