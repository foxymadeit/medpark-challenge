"""Sending the minutes: the server owns the send window and the delivery.

Auto mode: when processing ends with nothing left to confirm, the meeting
waits LIMINAL_SEND_WINDOW_S (60 s) as `sending_soon`; anyone can stop it,
which turns it into a manual review. Manual mode: the reviewer presses Send.

Routing: routing.json (or the file in LIMINAL_ROUTING) maps each meeting
type to its distribution list; MOM_RECIPIENTS_<TYPE> is the fallback.
Delivery: EmailService sends the minutes with the PDFs through the local SMTP
server (Mailpit in the demo). An n8n workflow can sit in front by setting
LIMINAL_N8N_WEBHOOK; it is off by default, and if it does not answer the
backend sends the mail itself.
"""

import base64
import dataclasses
import json
import logging
import os
import secrets
import threading
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

import store
from schemas import ActionItem, Minutes
from security import now_iso
from pathlib import Path

from services.EmailService import EmailService, SMTPSettings

log = logging.getLogger("liminal.delivery")

WINDOW_S = int(os.getenv("LIMINAL_SEND_WINDOW_S", "60"))
N8N_WEBHOOK = os.getenv("LIMINAL_N8N_WEBHOOK", "")   # optional; empty means send directly
ROUTING = Path(os.getenv("LIMINAL_ROUTING", Path(__file__).resolve().parent / "routing.json"))
AUTO_AVAILABLE = os.getenv("LIMINAL_AUTO_MODE", "1") == "1"
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # never through a proxy


class NotSendable(ValueError):
    pass


def routing() -> dict[str, list[str]]:
    """Meeting type -> distribution list, from the routing file, else the environment."""
    try:
        table = json.loads(ROUTING.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        table = {}
    out = {}
    for t in ("medical", "executive", "administrative"):
        listed = table.get(t) or os.getenv(f"MOM_RECIPIENTS_{t.upper()}", "").split(",")
        out[t] = [a.strip() for a in listed if a and a.strip()]
    return out


def recipients(meeting_type: str) -> list[str]:
    return routing().get(meeting_type, [])


def mailer() -> EmailService:
    """Roman's EmailService, with the distribution lists from the routing table."""
    settings = dataclasses.replace(SMTPSettings.from_env(),
                                   recipients_by_meeting_type={t: tuple(v) for t, v in routing().items()})
    return EmailService(settings)


def problems(m: dict, *, manual: bool) -> list[str]:
    """What blocks sending. Owners and deadlines may stay empty: the minutes
    print "not set", which is honest; an owner that is not a participant is not."""
    out = []
    ids = {p["id"] for p in m.get("participants", [])}
    for a in m.get("actionItems") or []:
        if not a.get("task", "").strip():
            out.append(f"action {a['id']} has no text")
        if a.get("ownerParticipantId") and a["ownerParticipantId"] not in ids:
            out.append(f"action {a['id']} has an owner who is not a participant")
    if m.get("needsConfirmation"):
        out.append(f"{len(m['needsConfirmation'])} items need confirmation")
    if not m.get("distributionList"):
        out.append("no distribution list for this meeting type")
    if manual and m.get("reviewState") != "reviewed":
        out.append("the minutes have not been reviewed")
    return out


def after_processing(m: dict) -> None:
    """Called inside the transaction that stores the finished minutes."""
    m["sendWindowSeconds"] = WINDOW_S
    if m.get("sendMode") == "auto" and AUTO_AVAILABLE and not problems(m, manual=False):
        m.update(status="sending_soon", deliveryState="scheduled", reviewState="reviewed",
                 sendScheduledAt=_iso(datetime.now(timezone.utc) + timedelta(seconds=WINDOW_S)))
    else:
        m.update(status="ready", reviewState="needs_review", sendScheduledAt=None)


def stop(meeting_id: str) -> dict | None:
    def change(m):
        if m["status"] == "sending_soon":
            m.update(status="ready", sendMode="manual", reviewState="needs_review", deliveryState="stopped",
                     sendScheduledAt=None)
    return store.update("meetings", meeting_id, change)


def begin(meeting_id: str, *, manual: bool, key: str | None = None) -> tuple[dict, bool]:
    """Move a meeting to `sending` if it may be sent. Returns (meeting, started).
    A second request for a meeting already sending or sent changes nothing."""
    started = False

    def change(m):
        nonlocal started
        if m["status"] in ("sending", "sent"):
            return
        if m["status"] not in ("ready", "sending_soon"):
            raise NotSendable("the minutes are not ready")
        issues = problems(m, manual=manual)
        if issues:
            raise NotSendable("; ".join(issues))
        m.update(status="sending", deliveryState="sending", sendingStartedAt=now_iso(), sendScheduledAt=None,
                 failureReference=None, reviewState="reviewed")
        if key:
            m["idempotencyKey"] = key
        started = True
    return store.update("meetings", meeting_id, change), started


def payload(m: dict) -> dict:
    names = {p["id"]: p["name"] for p in m.get("participants", [])}
    minutes = Minutes(
        title=m["title"], meeting_type=m["type"], language="ro", summary=m.get("summary") or "",
        attendees=[p["name"] for p in m.get("participants", [])],
        decisions=[d["text"] for d in m.get("decisions") or []],
        action_items=[ActionItem(text=a["task"], owner=names.get(a.get("ownerParticipantId")), deadline=a.get("deadline"))
                      for a in m.get("actionItems") or []])
    docs = []
    folder = store.DATA / "meetings" / m["id"] / "minutes"
    for lang, files in sorted((m.get("documents") or {}).items()):
        if files.get("pdf") and (folder / files["pdf"]).is_file():
            docs.append({"fileName": files["pdf"], "mimeType": "application/pdf",
                         "data": base64.b64encode((folder / files["pdf"]).read_bytes()).decode()})
    return {"meetingId": m["id"], "minutes": minutes.model_dump(), "documents": docs,
            "participant_emails": [p["email"] for p in m.get("participants", []) if p.get("email")]}


def n8n_available() -> bool:
    if not N8N_WEBHOOK:
        return False
    base = N8N_WEBHOOK.split("/webhook")[0]
    try:
        with _OPENER.open(base + "/healthz", timeout=2) as r:
            return r.status == 200
    except (OSError, urllib.error.URLError):
        return False


def _via_n8n(body: dict) -> bool:
    if not N8N_WEBHOOK:
        return False
    req = urllib.request.Request(N8N_WEBHOOK, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with _OPENER.open(req, timeout=60) as r:
            return 200 <= r.status < 300
    except (OSError, urllib.error.URLError) as e:
        log.warning("n8n did not take the minutes (%s); sending directly", type(e).__name__)
        return False


def _via_smtp(body: dict) -> None:
    result = mailer().send_mom_email(
        Minutes(**body["minutes"]),
        attachments=[(d["fileName"], base64.b64decode(d["data"])) for d in body["documents"]],
        participant_emails=tuple(body["participant_emails"]))
    if not result.accepted:
        raise OSError("every recipient was refused")


def deliver(meeting_id: str) -> None:
    m = store.get("meetings", meeting_id)
    try:
        body = payload(m)
        via = "n8n" if _via_n8n(body) else None
        if via is None:
            _via_smtp(body)
            via = "smtp"
        store.update("meetings", meeting_id, lambda x: x.update(
            status="sent", deliveryState="sent", sentAt=now_iso(), deliveredVia=via))
    except Exception as e:   # the minutes stay; the meeting is never marked sent
        ref = secrets.token_hex(4).upper()
        log.error("meeting %s delivery failed [%s]: %s", meeting_id, ref, type(e).__name__)
        store.update("meetings", meeting_id, lambda x: x.update(
            status="ready", deliveryState="failed", deliveryFailedAt=now_iso(), failureReference=ref))


def deliver_async(meeting_id: str) -> None:
    threading.Thread(target=deliver, args=(meeting_id,), daemon=True, name=f"deliver-{meeting_id}").start()


def _iso(t: datetime) -> str:
    return t.isoformat(timespec="seconds").replace("+00:00", "Z")


class Scheduler(threading.Thread):
    """Sends auto-mode minutes when their window ends."""

    def __init__(self, poll_s: float = 1.0):
        super().__init__(daemon=True, name="liminal-scheduler")
        self.poll_s, self.stopping = poll_s, threading.Event()

    def tick(self) -> None:
        now = _iso(datetime.now(timezone.utc))
        for m in store.all_docs("meetings"):   # ponytail: full scan each second; index by status past ~10k meetings
            if m["status"] == "sending_soon" and (m.get("sendScheduledAt") or "") <= now:
                try:
                    _, started = begin(m["id"], manual=False)
                except NotSendable:
                    stop(m["id"])
                    continue
                if started:
                    deliver_async(m["id"])

    def run(self):
        while not self.stopping.is_set():
            try:
                self.tick()
            except Exception:
                log.exception("scheduler tick failed")
            self.stopping.wait(self.poll_s)
