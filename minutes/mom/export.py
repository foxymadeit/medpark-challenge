"""The minutes as the web app's Meeting object (frontend/src/types/meeting.ts on
the frontend branch), so the app can show our output without a translation
layer. Unknown values stay null, as the API contract asks; no patient names."""

import datetime as dt

from . import latexcheck
from .anonymize import anonymize_text
from .write import owner_display, unproven

DOC = {"ro": "Proces-verbal", "ru": "Протокол", "en": "Minutes"}


def participants(lines, lang: str, patients=()) -> tuple:
    """-> (participants, speaker label -> participant id), in order of first speech."""
    talk, order = {}, []
    for l in lines:
        if l.speaker and l.speaker not in talk:
            order.append(l.speaker)
            talk[l.speaker] = 0.0
        if l.speaker:
            talk[l.speaker] += max(0.0, l.end - l.start)
    ids = {w: f"participant-{i}" for i, w in enumerate(order, 1)}
    people = [{"id": ids[w], "name": anonymize_text(owner_display(w, lang), list(patients)), "speakerId": ids[w],
               "speakerSlot": i, "speakingSeconds": round(talk[w])} for i, w in enumerate(order)]
    return people, ids


def meeting_json(meeting, facts, lines, body: str, lang: str, patients=()) -> dict:
    """meeting: schemas.Meeting; facts: verified Facts; body: the checked LaTeX body in `lang`."""
    blocks = latexcheck.parse(body)
    written = {b.fact_id: {k: latexcheck.unescape(v) for k, v in b.args.items()} for b in blocks if b.fact_id}
    people, ids = participants(lines, lang, patients)
    start = {l.id: l.start for l in lines}
    kept = [f for f in facts if f.status == "ok"]

    actions = []
    for f in kept:
        if f.kind != "action":
            continue
        if f.owner and f.owner not in ids:
            # an owner named in the meeting ("Roman, programează…") but not a detected voice:
            # list them as a named participant so the app shows the name, as the PDF does
            ids[f.owner] = f"participant-named-{len(ids) + 1}"
            people.append({"id": ids[f.owner], "name": anonymize_text(f.owner, list(patients)),
                           "speakerSlot": len(people), "speakingSeconds": 0})
        first = next((start[e] for e in f.evidence if e in start), None)
        item = {"id": f.id, "task": written.get(f.id, {}).get("text", f.text),
                "ownerParticipantId": ids.get(f.owner), "deadline": f.deadline or None, "completed": False}
        if first is not None:
            item["sourceTimestampSeconds"] = round(first, 1)
        actions.append(item)

    return {
        "id": f"MoM_{meeting.date}_{meeting.type}",
        "title": f"{DOC[lang]} {meeting.title(lang)}",
        "type": meeting.type,
        "status": "ready",
        "createdAt": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "inputMode": "upload",
        "durationSeconds": round(lines[-1].end) if lines else 0,
        "participants": people,
        "distributionList": [],            # routing is the backend's, per meeting type
        "summary": next((latexcheck.unescape(b.args["text"]) for b in blocks if b.kind == "summary"), ""),
        "decisions": [{"id": f.id, "text": written.get(f.id, {}).get("text", f.text)} for f in kept if f.kind == "decision"],
        "actionItems": actions,
        "agendaTopics": [{"id": b.fact_id, "text": latexcheck.unescape(b.args["title"]), "order": i}
                         for i, b in enumerate((b for b in blocks if b.kind == "topic"), 1)],
        "transcript": [{"id": l.id, "speakerId": ids.get(l.speaker), "startSeconds": l.start, "endSeconds": l.end,
                        "text": anonymize_text(l.text, list(patients))} for l in lines],
        "processingState": "complete",
        "reviewFlags": [anonymize_text(f.text, list(patients)) for f in unproven(facts)],   # never in the documents
        "reviewState": "needs_review",     # a person reviews every set of minutes before it is sent
        "sendMode": "manual",
        "minutesLanguage": lang,           # the summary and items above are written in this language
    }
