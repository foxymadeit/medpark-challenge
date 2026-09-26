"""The /api routes the Liminal web app calls (frontend/API_CONTRACT.md).

Every route but login needs a session. Meetings are visible to the person
who created them and to administrators. The server owns statuses, the
distribution list, speaker identities and delivery; the browser only asks.
"""

import os
import re
import secrets
import shutil
import uuid
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, File, Header, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

import audio
import delivery
import jobs
import security
import store
from security import current_user, now_iso, require_admin

router = APIRouter(prefix="/api")
TYPES = ("medical", "executive", "administrative")
EDITABLE_BEFORE_PROCESSING = ("title", "startedAt", "endedAt", "durationSeconds", "speakerTimeline",
                              "participants", "agendaTopics", "templateId", "sendMode")
CLIENT_STATUSES = ("draft", "recording", "stopped", "uploaded")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ---------------------------------------------------------------- models
class Login(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=256)


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


class Confirmation(BaseModel):
    action: str   # "keep" or "remove"


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


def meeting_for(meeting_id: str, user: dict) -> dict:
    m = store.get("meetings", meeting_id)
    if m is None or (user["role"] != "admin" and m.get("createdBy") != user["id"]):
        raise HTTPException(404, "Meeting not found.")
    return m


def _update(meeting_id: str, user: dict, change) -> dict:
    meeting_for(meeting_id, user)
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


# ---------------------------------------------------------------- auth
@router.post("/auth/login")
def login(body: Login, request: Request, response: Response):
    return security.login(request, response, body.email, body.password)


@router.get("/auth/me")
def me(user: dict = Depends(current_user)):
    return security.public_user(user)


@router.post("/auth/logout", status_code=204)
def logout(request: Request, response: Response):
    security.logout(request, response)
    response.status_code = 204
    return response


# ---------------------------------------------------------------- meetings
@router.get("/meetings")
def list_meetings(user: dict = Depends(current_user)):
    ms = [m for m in store.all_docs("meetings") if user["role"] == "admin" or m.get("createdBy") == user["id"]]
    return sorted(ms, key=lambda m: m["createdAt"], reverse=True)


@router.post("/meetings", status_code=201)
def create_meeting(body: CreateMeeting, user: dict = Depends(current_user)):
    if body.type not in TYPES or body.inputMode not in ("record", "upload"):
        raise HTTPException(422, "Unknown meeting type or input mode.")
    participants = [_participant(p, i) for i, p in enumerate(body.participants)]
    m = {"id": str(uuid.uuid4()), "title": body.title.strip(), "type": body.type, "status": "draft",
         "createdAt": now_iso(), "createdBy": user["id"], "inputMode": body.inputMode,
         "participants": participants, "participantSnapshots": [_snapshot(p, body.type) for p in participants],
         "distributionList": _distribution(body.type), "agendaTopics": body.agendaTopics,
         "sendMode": "auto" if delivery.AUTO_AVAILABLE else "manual", "reviewState": "not_ready",
         "sendWindowSeconds": delivery.WINDOW_S}
    if body.templateId:
        m["templateId"] = body.templateId
    return store.put("meetings", m)


@router.get("/meetings/{meeting_id}")
def get_meeting(meeting_id: str, user: dict = Depends(current_user)):
    return meeting_for(meeting_id, user)


@router.patch("/meetings/{meeting_id}")
def patch_meeting(meeting_id: str, changes: dict, user: dict = Depends(current_user)):
    def change(m):
        for key, value in changes.items():
            if key == "status":
                if value not in CLIENT_STATUSES or m["status"] not in CLIENT_STATUSES:
                    raise HTTPException(409, "That status is set by the server.")
                m["status"] = value
            elif key == "title":
                title = str(value).strip()
                if not 0 < len(title) <= 120:
                    raise HTTPException(422, "A title has 1 to 120 characters.")
                m["title"] = title
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
    return _update(meeting_id, user, change)


def _store_audio(meeting_id: str, user: dict, upload: UploadFile, *, measure: bool) -> dict:
    m = meeting_for(meeting_id, user)
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
def save_recording(meeting_id: str, audio_file: UploadFile = File(alias="audio"), user: dict = Depends(current_user)):
    _store_audio(meeting_id, user, audio_file, measure=False)   # checkpoints: measured when processing starts
    return Response(status_code=204)


@router.post("/meetings/{meeting_id}/upload", status_code=204)
def upload(meeting_id: str, audio_file: UploadFile = File(alias="audio"), user: dict = Depends(current_user)):
    _store_audio(meeting_id, user, audio_file, measure=True)
    return Response(status_code=204)


@router.get("/meetings/{meeting_id}/recording")
def get_recording(meeting_id: str, user: dict = Depends(current_user)):
    meeting_for(meeting_id, user)
    path = next(jobs.work_dir(meeting_id).glob("audio.*"), None)
    if path is None:
        raise HTTPException(404, "No recording yet.")
    return FileResponse(path, media_type="application/octet-stream", filename=f"recording{path.suffix}")


@router.post("/meetings/{meeting_id}/process")
def process(meeting_id: str, user: dict = Depends(current_user)):
    m = meeting_for(meeting_id, user)
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
def processing(meeting_id: str, user: dict = Depends(current_user)):
    return meeting_for(meeting_id, user)


@router.get("/meetings/{meeting_id}/minutes")
def minutes(meeting_id: str, user: dict = Depends(current_user)):
    return meeting_for(meeting_id, user)


@router.patch("/meetings/{meeting_id}/minutes")
def patch_minutes(meeting_id: str, body: MinutesPatch, user: dict = Depends(current_user)):
    def change(m):
        _locked(m)
        if body.summary is not None:
            m["summary"] = body.summary.strip()
        if body.decisions is not None:
            old = {d["id"] for d in m.get("decisions") or []}
            decisions = []
            for d in body.decisions:
                text = str(d.get("text", "")).strip()
                if text:
                    decisions.append({"id": str(d.get("id") or f"D{uuid.uuid4().hex[:6]}")[:64], "text": text[:2000]})
            for d in decisions:
                _resolve(m, d["id"])
            for gone in old - {d["id"] for d in decisions}:
                _resolve(m, gone)
            m["decisions"] = decisions
        _restart_window(m)
    return _update(meeting_id, user, change)


@router.patch("/meetings/{meeting_id}/actions/{action_id}")
def patch_action(meeting_id: str, action_id: str, body: ActionPatch, user: dict = Depends(current_user)):
    fields = body.model_dump(exclude_unset=True)

    def change(m):
        if m["status"] in ("sending", "sent") and set(fields) - {"completed"}:
            raise HTTPException(409, "The minutes have already been sent.")
        a = next((x for x in m.get("actionItems") or [] if x["id"] == action_id), None)
        if a is None:
            raise HTTPException(404, "Action not found.")
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
        if set(fields) - {"completed"}:
            _resolve(m, action_id)
            _restart_window(m)
    return _update(meeting_id, user, change)


def _valid_date(d: str) -> bool:
    try:
        date.fromisoformat(d)
        return True
    except ValueError:
        return False


@router.post("/meetings/{meeting_id}/confirmations/{fact_id}")
def confirm(meeting_id: str, fact_id: str, body: Confirmation, user: dict = Depends(current_user)):
    """Settle one item the checks could not confirm: keep it as written, or take it out."""
    if body.action not in ("keep", "remove"):
        raise HTTPException(422, "Use keep or remove.")

    def change(m):
        _locked(m)
        item = next((c for c in m.get("needsConfirmation") or [] if c["id"] == fact_id), None)
        if item is None:
            raise HTTPException(404, "Nothing to confirm with that id.")
        if body.action == "remove":
            m["decisions"] = [d for d in m.get("decisions") or [] if d["id"] != fact_id]
            m["actionItems"] = [a for a in m.get("actionItems") or [] if a["id"] != fact_id]
        _resolve(m, fact_id)
    return _update(meeting_id, user, change)


@router.patch("/meetings/{meeting_id}/participants")
def patch_participants(meeting_id: str, body: dict, user: dict = Depends(current_user)):
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
    return _update(meeting_id, user, change)


@router.post("/meetings/{meeting_id}/feedback", status_code=204)
def feedback(meeting_id: str, body: dict, user: dict = Depends(current_user)):
    meeting_for(meeting_id, user)
    item = {k: str(body.get(k, ""))[:4000] for k in ("field", "before", "after")}
    item.update(id=str(uuid.uuid4()), meetingId=meeting_id, createdAt=now_iso(), createdBy=user["id"])
    if isinstance(body.get("sourceTimestamp"), (int, float)):
        item["sourceTimestamp"] = body["sourceTimestamp"]
    store.put("feedback", item)
    return Response(status_code=204)


@router.post("/meetings/{meeting_id}/review")
def review(meeting_id: str, user: dict = Depends(current_user)):
    def change(m):
        if m["status"] != "ready":
            raise HTTPException(409, "The minutes are not ready for review.")
        issues = delivery.problems(m, manual=False)
        if issues or not m.get("participants"):
            raise HTTPException(409, "; ".join(issues) or "Add the participants first.")
        m["reviewState"] = "reviewed"
    return _update(meeting_id, user, change)


@router.get("/meetings/{meeting_id}/transcript")
def transcript(meeting_id: str, user: dict = Depends(current_user)):
    return meeting_for(meeting_id, user).get("transcript") or []


@router.post("/meetings/{meeting_id}/send")
def send(meeting_id: str, idempotency_key: str | None = Header(default=None, max_length=128),
         user: dict = Depends(current_user)):
    meeting_for(meeting_id, user)
    try:
        m, started = delivery.begin(meeting_id, manual=True, key=idempotency_key)
    except delivery.NotSendable as e:
        raise HTTPException(409, str(e))
    if started:
        delivery.deliver_async(meeting_id)
    return m


@router.post("/meetings/{meeting_id}/stop-send")
def stop_send(meeting_id: str, user: dict = Depends(current_user)):
    meeting_for(meeting_id, user)
    return delivery.stop(meeting_id)


@router.get("/meetings/{meeting_id}/documents/{name}")
def document(meeting_id: str, name: str, user: dict = Depends(current_user)):
    """name is `ro.pdf`, `ru.docx` and so on; files come only from the meeting's own minutes folder."""
    m = meeting_for(meeting_id, user)
    match = re.fullmatch(r"(ro|ru|en)\.(pdf|docx)", name)
    filename = (m.get("documents") or {}).get(match.group(1), {}).get(match.group(2)) if match else None
    if not filename:
        raise HTTPException(404, "No such document.")
    folder = (jobs.work_dir(meeting_id) / "minutes").resolve()
    path = (folder / filename).resolve()
    if path.parent != folder or not path.is_file():
        raise HTTPException(404, "No such document.")
    media = "application/pdf" if match.group(2) == "pdf" else \
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return FileResponse(path, media_type=media, filename=filename)


@router.get("/action-items")
def action_items(user: dict = Depends(current_user)):
    return [{"meetingId": m["id"], "actionItem": a} for m in list_meetings(user) for a in m.get("actionItems") or []]


# ---------------------------------------------------------------- people and voices
@router.get("/people")
def people(user: dict = Depends(current_user)):
    return [p for p in store.all_docs("people") if p.get("active", True)]


@router.post("/people", status_code=201)
def add_person(body: dict, user: dict = Depends(current_user)):
    name = str(body.get("name", "")).strip()[:120]
    if not name:
        raise HTTPException(422, "A person needs a name.")
    person = {"id": str(uuid.uuid4()), "name": name, "active": True, "createdAt": now_iso(), "createdBy": user["id"]}
    if body.get("email"):
        person["email"] = str(body["email"]).strip()[:254]
    return store.put("people", person)


@router.post("/people/{person_id}/voice-enrollment", status_code=204)
def enroll(person_id: str, audio_file: UploadFile = File(alias="audio"), user: dict = Depends(current_user)):
    person = store.get("people", person_id)
    if person is None:
        raise HTTPException(404, "Person not found.")
    folder = store.DATA / "voices" / person_id
    saved = audio.save(audio_file, folder, measure=True)
    profile = {"id": f"voice-{person_id}", "staffId": person_id, "status": "prototype", "createdAt": now_iso(),
               "consentRecordedBy": user["id"]}
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
def voice_profiles(user: dict = Depends(current_user)):
    return store.all_docs("voices")


@router.get("/speaker-clusters")
def speaker_clusters(user: dict = Depends(current_user)):
    visible = {m["id"] for m in list_meetings(user)}
    return [c for c in store.all_docs("clusters") if c["meetingId"] in visible]


@router.post("/speaker-clusters/{cluster_id}/identify")
def identify(cluster_id: str, body: dict, user: dict = Depends(current_user)):
    cluster = store.get("clusters", cluster_id)
    person = store.get("people", str(body.get("staffId", "")))
    if cluster is None or person is None:
        raise HTTPException(404, "Voice or person not found.")
    meeting_for(cluster["meetingId"], user)
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
def templates(user: dict = Depends(current_user)):
    return store.all_docs("templates")


@router.get("/templates/{template_id}")
def template(template_id: str, user: dict = Depends(current_user)):
    t = store.get("templates", template_id)
    if t is None:
        raise HTTPException(404, "Template not found.")
    return t


def _template(body: dict, user: dict, existing: dict | None) -> dict:
    name = str(body.get("name", "")).strip()[:120]
    if not name or body.get("meetingType") not in TYPES:
        raise HTTPException(422, "A template needs a name and a meeting type.")
    ids = [str(i) for i in body.get("participantStaffIds") or []]
    if len(set(ids)) != len(ids) or any(store.get("people", i) is None for i in ids):
        raise HTTPException(422, "Unknown or repeated participant.")
    t = existing or {"id": str(uuid.uuid4()), "createdBy": user["id"], "createdAt": now_iso(), "active": True}
    t.update(name=name, meetingType=body["meetingType"], participantStaffIds=ids,
             agendaTopics=body.get("agendaTopics") or [], updatedAt=now_iso())
    for key in ("defaultTitle", "recurrence", "active"):
        if key in body:
            t[key] = body[key]
    return store.put("templates", t)


@router.post("/templates", status_code=201)
def create_template(body: dict, user: dict = Depends(current_user)):
    return _template(body, user, None)


@router.patch("/templates/{template_id}")
def update_template(template_id: str, body: dict, user: dict = Depends(current_user)):
    existing = store.get("templates", template_id)
    if existing is None:
        raise HTTPException(404, "Template not found.")
    return _template({**existing, **body}, user, existing)


# ---------------------------------------------------------------- system
def _probe(url: str) -> bool:
    try:
        with delivery._OPENER.open(url, timeout=2) as r:
            return r.status < 500
    except OSError:
        return False


def _tool(stage: str) -> bool:
    exe = jobs._command(stage, _dummy())[0][0]
    return bool(shutil.which(exe))


@router.get("/system")
def system(user: dict = Depends(require_admin)):
    free = shutil.disk_usage(store.DATA).free
    try:
        delivery.mailer()   # constructing it validates the SMTP settings
        mail_ok = True
    except ValueError:
        mail_ok = False
    services = [
        {"id": "asr", "available": _tool("asr"), "description": "Speech recognition"},
        {"id": "speakers", "available": _tool("diarize"), "description": "Speaker diarization"},
        {"id": "minutes", "available": _tool("minutes"), "description": "Minutes writer"},
        {"id": "automation", "available": all(delivery.routing().values()),
         "description": "Routing by meeting type" + (" through n8n" if delivery.n8n_available() else "")},
        {"id": "mail", "available": mail_ok, "description": "Local SMTP"},
        {"id": "storage", "available": free > 2 * 1024**3, "description": f"{free // 1024**3} GB free"},
        {"id": "llm", "available": _probe(os.getenv("MOM_LLM_URL", "http://127.0.0.1:11434") + "/api/version"),
         "description": "Local language model"},
    ]
    return {"local": True, "lastCheckedAt": now_iso(), "host": os.uname().nodename, "services": services,
            "capabilities": {"autoModeAvailable": delivery.AUTO_AVAILABLE}}


def _dummy() -> dict:
    return {k: "x" for k in ("audio", "work", "session", "type", "date", "start")}


@router.get("/capabilities")
def capabilities(user: dict = Depends(current_user)):
    return {"autoModeAvailable": delivery.AUTO_AVAILABLE}


# ---------------------------------------------------------------- admin
@router.get("/admin")
def admin(user: dict = Depends(require_admin)):
    accounts = [security.account(dict(r)) for r in store.db().execute("SELECT * FROM users ORDER BY created_at")]
    staff = [{"id": p["id"], "name": p["name"], "email": p.get("email", ""), "active": p.get("active", True),
              "createdAt": p.get("createdAt", ""), "createdBy": p.get("createdBy", "")} for p in store.all_docs("people")]
    return {"accounts": accounts, "staffProfiles": staff, "staffRoles": store.all_docs("roles"),
            "distributionLists": store.all_docs("lists")}


@router.post("/admin/users", status_code=201)
def create_account(body: dict, user: dict = Depends(require_admin)):
    email = str(body.get("email") or "").strip()
    username = str(body.get("username") or "").strip()[:64]
    if not username or "@" not in email or body.get("role") not in ("admin", "staff"):
        raise HTTPException(422, "An account needs a username, an email and a role.")
    password = secrets.token_urlsafe(12)
    try:
        u = security.create_user(email, username, body["role"], password, username=username,
                                 staff_profile_id=body.get("staffProfileId"), created_by=user["id"])
    except Exception as e:
        if "UNIQUE" in str(e):
            raise HTTPException(409, "An account with that email exists.")
        raise
    return {**security.account(u), "temporaryPassword": password}   # shown once, never stored in clear


@router.patch("/admin/users/{account_id}")
def patch_account(account_id: str, body: dict, user: dict = Depends(require_admin)):
    if security.user_by_id(account_id) is None:
        raise HTTPException(404, "Account not found.")
    if "active" in body:
        if account_id == user["id"] and not body["active"]:
            raise HTTPException(409, "You cannot switch off your own account.")
        with store.tx() as con:
            con.execute("UPDATE users SET active=? WHERE id=?", (1 if body["active"] else 0, account_id))
            if not body["active"]:
                con.execute("DELETE FROM sessions WHERE user_id=?", (account_id,))
    return security.account(security.user_by_id(account_id))


@router.post("/admin/people", status_code=201)
def create_staff(body: dict, user: dict = Depends(require_admin)):
    person = add_person(body, user)
    return {"id": person["id"], "name": person["name"], "email": person.get("email", ""), "active": True,
            "createdAt": person["createdAt"], "createdBy": user["id"]}


@router.patch("/admin/people/{person_id}")
def patch_staff(person_id: str, body: dict, user: dict = Depends(require_admin)):
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
def assign_role(person_id: str, body: dict, user: dict = Depends(require_admin)):
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
                                   "validTo": None, "createdBy": user["id"]})
        store.update("people", person_id, lambda p: p.update(role=title))
    return role


@router.patch("/admin/lists/{list_id}")
def patch_list(list_id: str, body: dict, user: dict = Depends(require_admin)):
    lst = store.update("lists", list_id, lambda x: x.update(active=bool(body.get("active", x.get("active", True)))))
    if lst is None:
        raise HTTPException(404, "List not found.")
    return lst


def seed() -> None:
    """Distribution lists come from the server's configuration, one per meeting type."""
    for t in TYPES:
        if store.get("lists", t) is None:
            store.put("lists", {"id": t, "name": f"{t}-board", "email": ", ".join(delivery.recipients(t)), "active": True})
