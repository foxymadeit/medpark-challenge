"""The /api routes the Liminal web app calls (frontend/API_CONTRACT.md).

There are no accounts: every page on the hospital network can use every
route, and every meeting is visible to all (security.py says what limits
access instead). The server owns statuses, the distribution list, speaker
identities and delivery; the browser only asks.
"""

import copy
import json
import os
import re
import shutil
import threading
import urllib.error
import uuid
from datetime import date
from pathlib import Path

from fastapi import APIRouter, File, Header, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

import audio
import corrections
import delivery
import jobs
import names
import security
import sentences
import store
from security import NETWORK, now_iso

router = APIRouter(prefix="/api")
TYPES = ("medical", "executive", "administrative")
LIST_NAMES = {"medical": "Medical board", "executive": "Executive board", "administrative": "Administrative board"}
EDITABLE_BEFORE_PROCESSING = ("title", "startedAt", "endedAt", "durationSeconds", "speakerTimeline",
                              "participants", "agendaTopics", "templateId", "sendMode")
CLIENT_STATUSES = ("draft", "recording", "stopped", "uploaded")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ---------------------------------------------------------------- models
class CreateMeeting(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    type: str
    inputMode: str
    participants: list[dict] = Field(default_factory=list, max_length=100)
    templateId: str | None = None
    agendaTopics: list[dict] = Field(default_factory=list, max_length=50)


class MinutesPatch(BaseModel):
    summary: str | None = Field(default=None, max_length=10000)
    decisions: list[dict] | None = Field(default=None, max_length=200)


class ActionPatch(BaseModel):
    task: str | None = Field(default=None, max_length=2000)
    ownerParticipantId: str | None = None
    deadline: str | None = None
    completed: bool | None = None


class TranscriptLine(BaseModel):
    text: str = Field(max_length=4000)


class Confirmation(BaseModel):
    action: str   # "keep" or "remove"
    text: str | None = Field(default=None, max_length=4000)   # kept as rewritten by a person


class ParticipantName(BaseModel):
    name: str = Field(max_length=400)   # names.clean_name trims it and allows 1 to 80 characters


class Merge(BaseModel):
    into: str = Field(min_length=1, max_length=64)


# ---------------------------------------------------------------- helpers
def _participant(p: dict, i: int) -> dict:
    name = str(p.get("name", "")).strip()[:120]
    if not name:
        raise HTTPException(422, "Every participant needs a name.")
    out = {"id": str(p.get("id") or uuid.uuid4())[:64], "name": name, "staffId": str(p.get("staffId") or p.get("id") or "")[:64] or None}
    for key in ("email", "role", "department"):
        if p.get(key):
            out[key] = str(p[key])[:254]
    for key in ("speakerId", "speakerSlot", "speakingSeconds", "enrolled", "enrollmentKind", "detected"):
        if key in p:
            out[key] = p[key]
    out.setdefault("speakerSlot", i)
    return out


def _snapshot(p: dict, meeting_type: str) -> dict:
    return {"staffId": p.get("staffId") or p["id"], "nameAtMeeting": p["name"], "emailAtMeeting": p.get("email", ""),
            "roleTitleAtMeeting": p.get("role", ""), "departmentAtMeeting": p.get("department", meeting_type),
            **({"speakerId": p["speakerId"]} if p.get("speakerId") else {})}


def _distribution(meeting_type: str) -> list[str]:
    lst = store.get("lists", meeting_type)
    return delivery.recipients(meeting_type) if (lst is None or lst.get("active", True)) else []


def meeting_for(meeting_id: str) -> dict:
    m = store.get("meetings", meeting_id)
    if m is None:
        raise HTTPException(404, "Meeting not found.")
    return m


def _live(m: dict) -> dict:
    """While processing: queuePosition is how many meetings are ahead. First in
    line reads as running (starting), never as waiting for another meeting."""
    if m.get("status") != "processing" or m.get("processingState") not in ("queued", "running"):
        return m
    ahead = jobs.queue_position(m["id"])
    if ahead is None:
        return m
    return {**m, "queuePosition": ahead, **({"processingState": "running"} if ahead == 0 else {})}


def _update(meeting_id: str, change) -> dict:
    meeting_for(meeting_id)
    return store.update("meetings", meeting_id, change)


def _restart_window(m: dict) -> None:
    if m["status"] == "sending_soon":
        m["sendScheduledAt"] = delivery._iso(delivery.datetime.now(delivery.timezone.utc)
                                             + delivery.timedelta(seconds=delivery.WINDOW_S))


def _resolve(m: dict, fact_id: str) -> None:
    m["needsConfirmation"] = [c for c in m.get("needsConfirmation") or [] if c["id"] != fact_id]


def _locked(m: dict) -> None:
    if m["status"] in ("sending", "sent"):
        raise HTTPException(409, "The minutes have already been sent.")


# ---------------------------------------------------------------- meetings
@router.get("/meetings")
def list_meetings():
    return [_live(m) for m in sorted(store.all_docs("meetings"), key=lambda m: m["createdAt"], reverse=True)]


@router.post("/meetings", status_code=201)
def create_meeting(body: CreateMeeting):
    if body.type not in TYPES or body.inputMode not in ("record", "upload"):
        raise HTTPException(422, "Unknown meeting type or input mode.")
    participants = [_participant(p, i) for i, p in enumerate(body.participants)]
    m = {"id": str(uuid.uuid4()), "title": body.title.strip(), "type": body.type, "status": "draft",
         "createdAt": now_iso(), "createdBy": NETWORK["id"], "inputMode": body.inputMode,
         "participants": participants, "participantSnapshots": [_snapshot(p, body.type) for p in participants],
         "distributionList": _distribution(body.type), "agendaTopics": body.agendaTopics,
         "sendMode": "auto" if delivery.AUTO_AVAILABLE else "manual", "reviewState": "not_ready",
         "sendWindowSeconds": delivery.WINDOW_S}
    if body.templateId:
        m["templateId"] = body.templateId
    return store.put("meetings", m)


@router.get("/meetings/{meeting_id}")
def get_meeting(meeting_id: str):
    return _live(meeting_for(meeting_id))


@router.patch("/meetings/{meeting_id}")
def patch_meeting(meeting_id: str, changes: dict):
    def change(m):
        for key, value in changes.items():
            if key == "status":
                if value not in CLIENT_STATUSES or m["status"] not in CLIENT_STATUSES:
                    raise HTTPException(409, "That status is set by the server.")
                m["status"] = value
            elif key == "title":
                _locked(m)   # the moderator may retitle finished minutes until they are sent
                title = str(value).strip()
                if not 0 < len(title) <= 120:
                    raise HTTPException(422, "A title has 1 to 120 characters.")
                m["title"] = title
                _restart_window(m)
            elif key == "sendMode":
                if value not in ("manual", "auto") or (value == "auto" and not delivery.AUTO_AVAILABLE):
                    raise HTTPException(422, "Unknown send mode.")
                m["sendMode"] = value
            elif key == "participants":
                m["participants"] = [_participant(p, i) for i, p in enumerate(value or [])]
                m["participantSnapshots"] = [_snapshot(p, m["type"]) for p in m["participants"]]
            elif key in EDITABLE_BEFORE_PROCESSING:
                if m["status"] not in CLIENT_STATUSES:
                    continue   # measurements and timelines from the pipeline win after processing
                if key == "durationSeconds" and m.get("audioMeasured"):
                    continue
                m[key] = value
            # everything else (ids, statuses, minutes, delivery) is server-owned and ignored
    return _update(meeting_id, change)


def _store_audio(meeting_id: str, upload: UploadFile, *, measure: bool) -> dict:
    m = meeting_for(meeting_id)
    if m["status"] not in CLIENT_STATUSES + ("failed",):
        raise HTTPException(409, "This meeting already has its minutes.")
    saved = audio.save(upload, jobs.work_dir(meeting_id), measure=measure)
    name = Path(upload.filename or "recording").name[:120]

    def change(x):
        x.update(audioBytes=saved["bytes"], audioFilename=name, audioKind=saved["kind"])
        if measure:
            x.update(durationSeconds=saved["seconds"], audioMeasured=True, status="uploaded")
    return store.update("meetings", meeting_id, change)


@router.post("/meetings/{meeting_id}/recording", status_code=204)
def save_recording(meeting_id: str, audio_file: UploadFile = File(alias="audio")):
    _store_audio(meeting_id, audio_file, measure=False)   # checkpoints: measured when processing starts
    return Response(status_code=204)


@router.post("/meetings/{meeting_id}/upload", status_code=204)
def upload(meeting_id: str, audio_file: UploadFile = File(alias="audio")):
    _store_audio(meeting_id, audio_file, measure=True)
    return Response(status_code=204)


@router.get("/meetings/{meeting_id}/recording")
def get_recording(meeting_id: str):
    meeting_for(meeting_id)
    path = next(jobs.work_dir(meeting_id).glob("audio.*"), None)
    if path is None:
        raise HTTPException(404, "No recording yet.")
    return FileResponse(path, media_type="application/octet-stream", filename=f"recording{path.suffix}")


@router.post("/meetings/{meeting_id}/process")
def process(meeting_id: str):
    m = meeting_for(meeting_id)
    path = next(jobs.work_dir(meeting_id).glob("audio.*"), None)
    if path is None:
        raise HTTPException(409, "Record or upload the meeting first.")
    if m["status"] in ("processing", "sending_soon", "sending", "sent"):
        return m
    seconds = m.get("durationSeconds") if m.get("audioMeasured") else audio.duration(path)
    if seconds > audio.MAX_SECONDS:
        raise HTTPException(422, "The recording is longer than 3 hours.")

    def change(x):
        x.update(status="processing", processingState="queued", progress=0, reviewState="not_ready",
                 sendScheduledAt=None, durationSeconds=round(seconds, 2), audioMeasured=True, failureReference=None)
    m = store.update("meetings", meeting_id, change)
    jobs.enqueue(meeting_id)
    return m


@router.get("/meetings/{meeting_id}/processing")
def processing(meeting_id: str):
    return _live(meeting_for(meeting_id))


@router.get("/meetings/{meeting_id}/minutes")
def minutes(meeting_id: str):
    return meeting_for(meeting_id)


@router.patch("/meetings/{meeting_id}/minutes")
def patch_minutes(meeting_id: str, body: MinutesPatch, request: Request):
    def change(m):
        _locked(m)
        if body.summary is not None:
            corrections.record(meeting_id, "summary", "summary", m.get("summary"), body.summary.strip())
            m["summary"] = body.summary.strip()
        if body.decisions is not None:
            before = {d["id"]: d.get("text") for d in m.get("decisions") or []}
            old = set(before)
            decisions = []
            for d in body.decisions:
                text = str(d.get("text", "")).strip()
                if text:
                    decisions.append({"id": str(d.get("id") or f"D{uuid.uuid4().hex[:6]}")[:64], "text": text[:2000]})
            for d in decisions:
                _resolve(m, d["id"])
                if d["id"] in before:
                    corrections.record(meeting_id, d["id"], "text", before[d["id"]], d["text"])
            for gone in old - {d["id"] for d in decisions}:
                _resolve(m, gone)
            m["decisions"] = decisions
        _restart_window(m)

    m = meeting_for(meeting_id)   # rewritten sentences also go into the documents
    edits = {}
    if body.summary is not None and body.summary.strip() and body.summary.strip() != (m.get("summary") or ""):
        edits["S1"] = _text(body.summary, 10000)
    before = {d["id"]: d.get("text") for d in m.get("decisions") or []}
    for d in body.decisions or []:
        text = str(d.get("text", "")).strip()
        if d.get("id") in before and text and text != before[d["id"]]:
            edits[str(d["id"])] = _text(text)
    if not edits:
        return _update(meeting_id, change)
    return _edit_everywhere(meeting_id, change, _sentences(meeting_id, edits), check=_locked, request=request)


@router.patch("/meetings/{meeting_id}/actions/{action_id}")
def patch_action(meeting_id: str, action_id: str, body: ActionPatch, request: Request):
    fields = body.model_dump(exclude_unset=True)

    def change(m):
        if m["status"] in ("sending", "sent") and set(fields) - {"completed"}:
            raise HTTPException(409, "The minutes have already been sent.")
        a = next((x for x in m.get("actionItems") or [] if x["id"] == action_id), None)
        if a is None:
            raise HTTPException(404, "Action not found.")
        was = dict(a)
        if "task" in fields:
            if not (fields["task"] or "").strip():
                raise HTTPException(422, "An action needs its text.")
            a["task"] = fields["task"].strip()
        if "ownerParticipantId" in fields:
            owner = fields["ownerParticipantId"]
            person = next((p for p in m["participants"] if p["id"] == owner), None)
            if owner is not None and person is None:
                raise HTTPException(422, "The owner must be a participant.")
            a["ownerParticipantId"] = owner
            a["ownerStaffId"] = person.get("staffId") if person else None
        if "deadline" in fields:
            d = fields["deadline"]
            if d is not None and (not _DATE.match(d) or not _valid_date(d)):
                raise HTTPException(422, "A deadline is a date like 2026-10-05.")
            a["deadline"] = d
        if "completed" in fields:
            a["completed"] = bool(fields["completed"])
        for field in ("task", "ownerParticipantId", "deadline"):
            if field in fields:
                corrections.record(meeting_id, action_id, field, was.get(field), a.get(field))
        if set(fields) - {"completed"}:
            _resolve(m, action_id)
            _restart_window(m)

    task = (fields.get("task") or "").strip()
    current = next((a for a in meeting_for(meeting_id).get("actionItems") or [] if a["id"] == action_id), None)
    if task and current and task != current.get("task"):   # the rewritten task also goes into the documents
        return _edit_everywhere(meeting_id, change, _sentences(meeting_id, {action_id: _text(task)}),
                                check=_locked, request=request)
    return _update(meeting_id, change)


def _valid_date(d: str) -> bool:
    try:
        date.fromisoformat(d)
        return True
    except ValueError:
        return False


@router.post("/meetings/{meeting_id}/confirmations/{fact_id}")
def confirm(meeting_id: str, fact_id: str, body: Confirmation, request: Request):
    """Settle one item the checks could not confirm: keep it as written, keep
    it as a person rewrote it (body.text), or take it out."""
    if body.action not in ("keep", "remove"):
        raise HTTPException(422, "Use keep or remove.")
    if body.text is not None:
        if body.action != "keep" or fact_id == "meeting-type":
            raise HTTPException(422, "Only an item that is kept can be rewritten.")
        return _keep_rewritten(meeting_id, fact_id, _text(body.text), request)
    retype = fact_id == "meeting-type" and body.action == "remove"   # not this type: the one it sounded like
    new_type, documents = _render_as_detected(meeting_id) if retype else (None, None)
    old = set()

    def change(m):
        _locked(m)
        item = next((c for c in m.get("needsConfirmation") or [] if c["id"] == fact_id), None)
        if item is None:
            raise HTTPException(404, "Nothing to confirm with that id.")
        if retype:
            if item["detectedType"] != new_type:
                raise HTTPException(409, "The meeting changed meanwhile. Try again.")
            old.update(name for files in (m.get("documents") or {}).values() for name in files.values())
            m.update(type=new_type, distributionList=_distribution(new_type), documents=documents)
        elif body.action == "remove":
            m["decisions"] = [d for d in m.get("decisions") or [] if d["id"] != fact_id]
            m["actionItems"] = [a for a in m.get("actionItems") or [] if a["id"] != fact_id]
        _resolve(m, fact_id)
    m = _update(meeting_id, change)
    kept = {name for files in (documents or {}).values() for name in files.values()}
    for name in old - kept:   # the previous type's files; names come from our own documents map
        (jobs.minutes_folder(jobs.work_dir(meeting_id)) / Path(name).name).unlink(missing_ok=True)
    return m


def _keep_rewritten(meeting_id: str, fact_id: str, text: str, request: Request) -> dict:
    """A rewritten item counts as confirmed: its sentence changes in the app,
    and in the documents it leaves "needs confirmation" for its own topic."""
    m = meeting_for(meeting_id)
    item = next((c for c in m.get("needsConfirmation") or [] if c["id"] == fact_id), None)
    if item is None:
        raise HTTPException(404, "Nothing to confirm with that id.")
    action = next((a for a in m.get("actionItems") or [] if a["id"] == fact_id), None) or {}
    owner = next((p for p in m["participants"] if p["id"] == action.get("ownerParticipantId")), None)
    date = names.mom("schemas").format_date
    keep = {"kind": item.get("kind"), "topic": sentences.topic_of(jobs.minutes_folder(jobs.work_dir(meeting_id)), fact_id),
            "extra": {lang: {"owner": names.display(owner, lang) if owner else "",
                             "deadline": date(action["deadline"], lang) if action.get("deadline") else ""}
                      for lang in names.PARTICIPANT}}

    def change(x):
        _locked(x)
        was = next((c for c in x.get("needsConfirmation") or [] if c["id"] == fact_id), None)
        if was is None:
            raise HTTPException(404, "Nothing to confirm with that id.")
        for d in x.get("decisions") or []:
            if d["id"] == fact_id:
                d["text"] = text
        for a in x.get("actionItems") or []:
            if a["id"] == fact_id:
                a["task"] = text
        corrections.record(meeting_id, fact_id, "text", was.get("text"), text)
        _resolve(x, fact_id)
    return _edit_everywhere(meeting_id, change, _sentences(meeting_id, {fact_id: text}, keep),
                            check=_locked, request=request)


def _render_as_detected(meeting_id: str) -> tuple[str, dict]:
    """Rebuild the PDFs and DOCX files as the detected type before anything
    changes, outside the database lock (it takes seconds). If it fails, the
    meeting keeps its type and documents."""
    m = meeting_for(meeting_id)
    _locked(m)
    item = next((c for c in m.get("needsConfirmation") or [] if c["id"] == "meeting-type"), None)
    if item is None:
        raise HTTPException(404, "Nothing to confirm with that id.")
    try:
        documents = jobs.rerender(meeting_id, item["detectedType"])
    except jobs.StageFailed:
        raise HTTPException(503, "The documents could not be rebuilt for the new meeting type. Nothing was changed.")
    if documents is None:
        raise HTTPException(409, "These minutes cannot be rebuilt for another meeting type. Process the recording again.")
    return item["detectedType"], documents


@router.patch("/meetings/{meeting_id}/participants")
def patch_participants(meeting_id: str, body: dict):
    def change(m):
        _locked(m)
        m["participants"] = [_participant(p, i) for i, p in enumerate(body.get("participants") or [])]
        m["participantSnapshots"] = [_snapshot(p, m["type"]) for p in m["participants"]]
        ids = {p["id"] for p in m["participants"]}
        for a in m.get("actionItems") or []:
            if a.get("ownerParticipantId") not in ids:
                a["ownerParticipantId"] = None
                a["ownerStaffId"] = None
        _restart_window(m)
    return _update(meeting_id, change)


# ---------------------------------------------------------------- naming people in finished minutes
_NAMING = threading.Lock()   # ponytail: one rename or merge at a time server-wide; per meeting if moderators queue up


def _person(m: dict, participant_id: str) -> dict:
    p = next((x for x in m.get("participants") or [] if x["id"] == participant_id), None)
    if p is None:
        raise HTTPException(404, "Participant not found.")
    return p


def _edit_everywhere(meeting_id: str, edit_app, edit_state, check=None, request: Request | None = None) -> dict:
    """Change the app's meeting with edit_app(m) and the minutes' render state
    with edit_state(state, m), then build the PDFs and DOCX again (no model),
    so what is emailed carries the change. Until the minutes are sent.
    check(m) (default: edit_app on a copy) refuses bad input before a file
    changes. edit_state returns False when a sentence could not be translated;
    the audit row then says so."""
    with _NAMING:
        m = meeting_for(meeting_id)
        _locked(m)
        (check or edit_app)(copy.deepcopy(m))
        documents = None
        state_file = next(jobs.minutes_folder(jobs.work_dir(meeting_id)).glob("*.render.json"), None)
        if state_file is not None:
            before = state_file.read_text(encoding="utf-8")
            try:
                state = json.loads(before)
                if edit_state(state, m) is False and request is not None:
                    request.state.audit_status = security.UNTRANSLATED
                jobs._write_json(state_file, state)
                documents = jobs.rerender(meeting_id, m["type"])
            except (jobs.StageFailed, ValueError):
                state_file.write_text(before, encoding="utf-8")
                raise HTTPException(503, "The documents could not be rebuilt with the change. Nothing was changed.")

        def change(x):
            _locked(x)
            edit_app(x)
            x["participantSnapshots"] = [_snapshot(p, x["type"]) for p in x["participants"]]
            if documents:
                x["documents"] = documents
            _restart_window(x)
        return _update(meeting_id, change)


def _sentences(meeting_id: str, edits: dict, keep: dict | None = None):
    """edit_state for rewritten sentences: {fact or block ID: text}."""
    def edit(state: dict, m: dict) -> bool:
        langs = list(state.get("bodies") or {})
        src = m.get("minutesLanguage") if m.get("minutesLanguage") in langs else (langs[0] if langs else "ro")
        folder, complete = jobs.minutes_folder(jobs.work_dir(meeting_id)), True
        for item_id, text in edits.items():
            by_lang, ok = sentences.texts(text, src, langs, ask=complete)
            complete = complete and ok
            sentences.set_sentence(state, item_id, sentences.waiting_id(folder, item_id), by_lang, keep)
        return complete
    return edit


def _text(raw, limit: int = sentences.MAX_TEXT) -> str:
    try:
        return sentences.clean(raw, limit)
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.patch("/meetings/{meeting_id}/participants/{participant_id}")
def rename_participant(meeting_id: str, participant_id: str, body: ParticipantName):
    """Give a participant a name: "Participantul 4" becomes "Ana Rusu" in the app,
    the email and every document."""
    try:
        name = names.clean_name(body.name)
    except ValueError as e:
        raise HTTPException(422, str(e))

    def edit_app(m):
        p = _person(m, participant_id)
        if any(q is not p and q["name"].casefold() == name.casefold() for q in m["participants"]):
            raise HTTPException(422, "Another participant already has that name. Merge the two instead.")
        names.retext(m, p, name)
        p["name"] = name

    return _edit_everywhere(meeting_id, edit_app,
                            lambda state, m: names.rename_state(state, _person(m, participant_id), name))


@router.post("/meetings/{meeting_id}/participants/{participant_id}/merge")
def merge_participant(meeting_id: str, participant_id: str, body: Merge):
    """Two participants are one person: this one's lines, actions and mentions
    become the other's (body.into), and this one leaves the list."""
    def edit_app(m):
        gone, into = _person(m, participant_id), _person(m, body.into)
        if gone is into:
            raise HTTPException(422, "Choose another participant to merge into.")
        names.retext(m, gone, names.display(into, m.get("minutesLanguage") or "ro"))
        if gone.get("speakerId") and not into.get("speakerId"):
            into["speakerId"] = gone["speakerId"]   # the voice was this person all along
        elif gone.get("speakerId"):
            for line in (m.get("transcript") or []) + (m.get("speakerTimeline") or []):
                if line.get("speakerId") == gone["speakerId"]:
                    line["speakerId"] = into["speakerId"]
        if "speakingSeconds" in gone or "speakingSeconds" in into:
            into["speakingSeconds"] = (into.get("speakingSeconds") or 0) + (gone.get("speakingSeconds") or 0)
        for a in m.get("actionItems") or []:
            if a.get("ownerParticipantId") == gone["id"]:
                a.update(ownerParticipantId=into["id"], ownerStaffId=into.get("staffId"))
        m["participants"] = [p for p in m["participants"] if p is not gone]

    return _edit_everywhere(meeting_id, edit_app, lambda state, m: names.merge_state(
        state, _person(m, participant_id), _person(m, body.into)))


@router.post("/meetings/{meeting_id}/feedback", status_code=204)
def feedback(meeting_id: str, body: dict):
    meeting_for(meeting_id)
    item = {k: str(body.get(k, ""))[:4000] for k in ("field", "before", "after")}
    item.update(id=str(uuid.uuid4()), meetingId=meeting_id, createdAt=now_iso(), createdBy=NETWORK["id"])
    if isinstance(body.get("sourceTimestamp"), (int, float)):
        item["sourceTimestamp"] = body["sourceTimestamp"]
    store.put("feedback", item)
    return Response(status_code=204)


@router.post("/meetings/{meeting_id}/review")
def review(meeting_id: str):
    def change(m):
        if m["status"] != "ready":
            raise HTTPException(409, "The minutes are not ready for review.")
        issues = delivery.problems(m, manual=False)
        if issues or not m.get("participants"):
            raise HTTPException(409, "; ".join(issues) or "Add the participants first.")
        m["reviewState"] = "reviewed"
    return _update(meeting_id, change)


@router.get("/meetings/{meeting_id}/transcript")
def transcript(meeting_id: str):
    return meeting_for(meeting_id).get("transcript") or []


@router.patch("/meetings/{meeting_id}/transcript/{index}")
def patch_transcript_line(meeting_id: str, index: int, body: TranscriptLine):
    """A moderator corrects what one transcript line says; the speaker and times stay."""
    text = _text(body.text, 4000)

    def change(m):
        _locked(m)
        lines = m.get("transcript") or []
        if not 0 <= index < len(lines):
            raise HTTPException(404, "Transcript line not found.")
        corrections.record(meeting_id, f"L{index}", "text", lines[index].get("text"), text)
        lines[index]["text"] = text
        _restart_window(m)

    return _update(meeting_id, change)


@router.post("/meetings/{meeting_id}/send")
def send(meeting_id: str, request: Request, idempotency_key: str | None = Header(default=None, max_length=128)):
    meeting_for(meeting_id)
    try:
        m, started = delivery.begin(meeting_id, manual=True, key=idempotency_key)
    except delivery.NotSendable as e:
        raise HTTPException(409, str(e))
    if started:
        delivery.deliver_async(meeting_id)
    else:   # already sending or sent (often by the server itself): not this person's send
        request.state.audit_status = security.ALREADY
    return m


@router.post("/meetings/{meeting_id}/send-window")
def send_window(meeting_id: str):
    """Reopen the 60-second stop window, e.g. once a person has settled the flagged items."""
    meeting_for(meeting_id)
    try:
        return delivery.open_window(meeting_id)
    except delivery.NotSendable as e:
        raise HTTPException(409, str(e))


@router.post("/meetings/{meeting_id}/stop-send")
def stop_send(meeting_id: str):
    meeting_for(meeting_id)
    return delivery.stop(meeting_id)


@router.get("/meetings/{meeting_id}/documents/{name}")
def document(meeting_id: str, name: str):
    """name is `ro.pdf`, `ru.docx` and so on; files come only from the meeting's own minutes folder."""
    m = meeting_for(meeting_id)
    match = re.fullmatch(r"(ro|ru|en)\.(pdf|docx)", name)
    filename = (m.get("documents") or {}).get(match.group(1), {}).get(match.group(2)) if match else None
    if not filename:
        raise HTTPException(404, "No such document.")
    folder = jobs.minutes_folder(jobs.work_dir(meeting_id)).resolve()
    path = (folder / filename).resolve()
    if path.parent != folder or not path.is_file():
        raise HTTPException(404, "No such document.")
    media = "application/pdf" if match.group(2) == "pdf" else \
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return FileResponse(path, media_type=media, filename=filename)


@router.get("/action-items")
def action_items():
    return [{"meetingId": m["id"], "actionItem": a} for m in list_meetings() for a in m.get("actionItems") or []]


# ---------------------------------------------------------------- people and voices
@router.get("/people")
def people():
    return [p for p in store.all_docs("people") if p.get("active", True)]


@router.post("/people", status_code=201)
def add_person(body: dict):
    name = str(body.get("name", "")).strip()[:120]
    if not name:
        raise HTTPException(422, "A person needs a name.")
    person = {"id": str(uuid.uuid4()), "name": name, "active": True, "createdAt": now_iso(), "createdBy": NETWORK["id"]}
    if body.get("email"):
        person["email"] = str(body["email"]).strip()[:254]
    return store.put("people", person)


@router.post("/people/{person_id}/voice-enrollment", status_code=204)
def enroll(person_id: str, audio_file: UploadFile = File(alias="audio")):
    person = store.get("people", person_id)
    if person is None:
        raise HTTPException(404, "Person not found.")
    # enrolling again replaces the voiceprint; the audit trail keeps when and from which address
    if person["name"].startswith("-"):   # the name is a command argument for the enroll tool
        raise HTTPException(422, "A name cannot start with a dash.")
    folder = store.DATA / "voices" / person_id
    saved = audio.save(audio_file, folder, measure=True)
    profile = {"id": f"voice-{person_id}", "staffId": person_id, "status": "prototype", "createdAt": now_iso(),
               "consentRecordedBy": NETWORK["id"]}
    cmd = os.getenv("LIMINAL_ENROLL_CMD")   # e.g. diarizer enroll {name} --file {audio} --consent --plain
    if cmd:
        try:
            jobs._run_args("enroll", [part.format(name=person["name"], audio=str(saved["path"]))
                                      for part in jobs.shlex.split(cmd)], None, folder)
            profile["status"] = "verified"
        except jobs.StageFailed:
            pass
    store.put("voices", profile)
    return Response(status_code=204)


@router.get("/voice-profiles")
def voice_profiles():
    return store.all_docs("voices")


@router.get("/speaker-clusters")
def speaker_clusters():
    return store.all_docs("clusters")


@router.post("/speaker-clusters/{cluster_id}/identify")
def identify(cluster_id: str, body: dict):
    cluster = store.get("clusters", cluster_id)
    person = store.get("people", str(body.get("staffId", "")))
    if cluster is None or person is None:
        raise HTTPException(404, "Voice or person not found.")
    meeting_for(cluster["meetingId"])
    ready = any(v["staffId"] == person["id"] for v in store.all_docs("voices"))
    cluster.update(identifiedStaffId=person["id"],
                   status="voice_profile_ready" if ready else "identified_without_voice_profile")
    store.put("clusters", cluster)

    def change(m):   # the voice's participant becomes that person; owners follow the participant id
        for p in m["participants"]:
            if p.get("speakerId") == cluster["speakerId"]:
                p.update(name=person["name"], staffId=person["id"], **({"email": person["email"]} if person.get("email") else {}))
        m["participantSnapshots"] = [_snapshot(p, m["type"]) for p in m["participants"]]
    store.update("meetings", cluster["meetingId"], change)
    return cluster


# ---------------------------------------------------------------- templates
@router.get("/templates")
def templates():
    return [t for t in store.all_docs("templates") if t.get("active", True)]


@router.get("/templates/{template_id}")
def template(template_id: str):
    t = store.get("templates", template_id)
    if t is None:
        raise HTTPException(404, "Template not found.")
    return t


def _template(body: dict, existing: dict | None) -> dict:
    name = str(body.get("name", "")).strip()[:120]
    if not name or body.get("meetingType") not in TYPES:
        raise HTTPException(422, "A template needs a name and a meeting type.")
    ids = [str(i) for i in body.get("participantStaffIds") or []]
    if len(set(ids)) != len(ids) or any(store.get("people", i) is None for i in ids):
        raise HTTPException(422, "Unknown or repeated participant.")
    t = existing or {"id": str(uuid.uuid4()), "createdBy": NETWORK["id"], "createdAt": now_iso(), "active": True}
    t.update(name=name, meetingType=body["meetingType"], participantStaffIds=ids,
             agendaTopics=body.get("agendaTopics") or [], updatedAt=now_iso())
    for key in ("defaultTitle", "recurrence", "active"):
        if key in body:
            t[key] = body[key]
    return store.put("templates", t)


@router.post("/templates", status_code=201)
def create_template(body: dict):
    return _template(body, None)


@router.patch("/templates/{template_id}")
def update_template(template_id: str, body: dict):
    existing = store.get("templates", template_id)
    if existing is None:
        raise HTTPException(404, "Template not found.")
    return _template({**existing, **body}, existing)


@router.post("/templates/{template_id}/deactivate")
def deactivate_template(template_id: str):
    existing = store.get("templates", template_id)
    if existing is None:
        raise HTTPException(404, "Template not found.")
    return store.put("templates", {**existing, "active": False, "updatedAt": now_iso()})


# ---------------------------------------------------------------- system
def _probe(url: str) -> bool:
    """Does a server answer there? Any HTTP reply below 500 counts: llama-server
    has no /api/version and answers 404, which still means it is running."""
    try:
        with delivery._OPENER.open(url, timeout=2) as r:
            return r.status < 500
    except urllib.error.HTTPError as e:
        return e.code < 500
    except OSError:
        return False


def _tool(stage: str) -> bool:
    exe = jobs._command(stage, _dummy())[0][0]
    return bool(shutil.which(exe))


@router.get("/system")
def system():
    free = shutil.disk_usage(store.DATA).free
    try:
        delivery.mailer()   # constructing it validates the SMTP settings
        mail_ok = True
    except ValueError:
        mail_ok = False
    llm = _probe((os.getenv("MOM_LLM_URL") or "http://127.0.0.1:11434").rstrip("/") + "/api/version")
    # one row per service, stable ids; the language model is part of the minutes writer
    services = [
        {"id": "asr", "name": "Speech recognition", "available": _tool("asr"),
         "description": "Turns the recording into text on this server"},
        {"id": "speakers", "name": "Speaker detection", "available": _tool("diarize"),
         "description": "Tells the voices in the recording apart"},
        {"id": "minutes", "name": "Minutes writer", "available": _tool("minutes") and llm,
         "description": "Writes the minutes with the local language model"
                        + ("" if llm else "; the language model is not answering")},
        {"id": "automation", "name": "Routing", "available": all(delivery.routing().values()),
         "description": "Picks the distribution list by meeting type" + (" through n8n" if delivery.n8n_available() else "")},
        {"id": "mail", "name": "Mail", "available": mail_ok, "description": "Sends the minutes through the local mail server"},
        {"id": "storage", "name": "Storage", "available": free > 2 * 1024**3, "description": f"{free // 1024**3} GB free"},
    ]
    return {"local": True, "lastCheckedAt": now_iso(), "host": os.uname().nodename, "services": services,
            "capabilities": {"autoModeAvailable": delivery.AUTO_AVAILABLE}}


def _dummy() -> dict:
    return {k: "x" for k in ("audio", "work", "session", "type", "date", "start", "render")}


@router.get("/routing")
def routing():
    """Per meeting type, the list's display name and how many receive it; never the addresses."""
    return {t: {"name": LIST_NAMES[t], "recipients": len(_distribution(t))} for t in TYPES}


@router.get("/capabilities")
def capabilities():
    return {"autoModeAvailable": delivery.AUTO_AVAILABLE}


# ---------------------------------------------------------------- admin
@router.get("/admin/audit")
def audit(limit: int = Query(500, ge=1, le=500), before: int | None = Query(None, ge=1)):
    """The append-only audit trail, newest first; page with ?before=<id of the last row>."""
    return security.audit_rows(limit, before)


class Approval(BaseModel):
    heard: str = Field(min_length=1, max_length=120)
    corrected: str = Field(min_length=1, max_length=120)
    lang: str = Field(pattern="^(ro|ru|en)$")


@router.get("/admin/glossary-candidates")
def glossary_candidates():
    """Words people corrected in the minutes, most frequent first."""
    return corrections.candidates()


@router.post("/admin/glossary-candidates/approve")
def approve_candidate(body: Approval):
    return corrections.approve(body.heard.strip(), body.corrected.strip(), body.lang)


@router.get("/admin")
def admin():
    staff = [{"id": p["id"], "name": p["name"], "email": p.get("email", ""), "active": p.get("active", True),
              "createdAt": p.get("createdAt", ""), "createdBy": p.get("createdBy", "")} for p in store.all_docs("people")]
    return {"staffProfiles": staff, "staffRoles": store.all_docs("roles"),
            "distributionLists": store.all_docs("lists")}


@router.post("/admin/people", status_code=201)
def create_staff(body: dict):
    person = add_person(body)
    return {"id": person["id"], "name": person["name"], "email": person.get("email", ""), "active": True,
            "createdAt": person["createdAt"], "createdBy": NETWORK["id"]}


@router.patch("/admin/people/{person_id}")
def patch_staff(person_id: str, body: dict):
    def change(p):
        if "name" in body:
            name = str(body["name"]).strip()[:120]
            if not name:
                raise HTTPException(422, "A person needs a name.")
            p["name"] = name
        if "email" in body:
            p["email"] = str(body["email"]).strip()[:254]
        if "active" in body:
            p["active"] = bool(body["active"])
    p = store.update("people", person_id, change)
    if p is None:
        raise HTTPException(404, "Person not found.")
    return {"id": p["id"], "name": p["name"], "email": p.get("email", ""), "active": p.get("active", True),
            "createdAt": p.get("createdAt", ""), "createdBy": p.get("createdBy", "")}


@router.post("/admin/people/{person_id}/roles", status_code=201)
def assign_role(person_id: str, body: dict):
    if store.get("people", person_id) is None:
        raise HTTPException(404, "Person not found.")
    title, valid_from = str(body.get("title", "")).strip()[:120], str(body.get("validFrom", ""))
    if not title or not _DATE.match(valid_from[:10]):
        raise HTTPException(422, "A role needs a title and a start date.")
    with store.tx():
        for r in store.all_docs("roles"):
            if r["staffId"] == person_id and r.get("validTo") is None:
                store.put("roles", {**r, "validTo": valid_from})
        role = store.put("roles", {"id": str(uuid.uuid4()), "staffId": person_id, "title": title,
                                   "department": str(body.get("department", ""))[:120], "validFrom": valid_from,
                                   "validTo": None, "createdBy": NETWORK["id"]})
        store.update("people", person_id, lambda p: p.update(role=title))
    return role


@router.patch("/admin/lists/{list_id}")
def patch_list(list_id: str, body: dict):
    lst = store.update("lists", list_id, lambda x: x.update(active=bool(body.get("active", x.get("active", True)))))
    if lst is None:
        raise HTTPException(404, "List not found.")
    return lst


def seed() -> None:
    """Distribution lists come from the server's configuration, one per meeting type."""
    for t in TYPES:
        if store.get("lists", t) is None:
            store.put("lists", {"id": t, "name": f"{t}-board", "email": ", ".join(delivery.recipients(t)), "active": True})
