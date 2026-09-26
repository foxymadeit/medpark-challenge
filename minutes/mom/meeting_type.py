"""Which kind of meeting this is, read from its first 3 minutes by the model
the minutes already use. On Kaggle (qwen3:8b, CPU) this was right on 8 of 8
meetings in 2 to 4 s; a zero-shot classifier (Laya) got 10 of 16 overall.
The type picks the distribution list, so the result is only a suggestion:
the backend holds the automatic send when it disagrees with the one chosen."""

from .schemas import MEETING_TYPES

CRITERIA = {"medical": "a medical board or clinical meeting: patients, diagnoses, treatments, wards, intensive care, surgery",
            "executive": "an executive or management meeting: strategy, budget, priorities, contracts, targets",
            "administrative": "an administrative meeting: rotas, staffing, procurement logistics, facilities, schedules, paperwork"}
SYSTEM = ("You classify hospital meeting transcripts. Answer with the meeting type only.\n"
          + "\n".join(f"- {k}: {v}" for k, v in CRITERIA.items()))
SCHEMA = {"type": "object", "properties": {"meeting_type": {"type": "string", "enum": list(CRITERIA)}},
          "required": ["meeting_type"]}
FIRST_SECONDS = 180


def detect(llm, lines, seconds: float = FIRST_SECONDS) -> str | None:
    early = [l for l in lines if l.start <= seconds] or lines
    text = "\n".join(f"{l.speaker or 'Speaker'}: {l.text}" for l in early)[:24000]
    try:
        answer = llm.chat_json(SYSTEM, "Transcript:\n" + text, SCHEMA, max_tokens=64).get("meeting_type")
    except Exception:   # a suggestion only: a slow or broken model must not stop the minutes
        return None
    return answer if answer in MEETING_TYPES else None
