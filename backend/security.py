"""Request checks and the audit trail.

Liminal has no accounts. Access is limited by where it runs: every port is
bound to 127.0.0.1 on the server or to the hospital network, and the services
share an internal Docker network with no route out. Every request acts as the
one built-in actor, NETWORK, and the audit trail records each change and each
read of a recording, transcript or document with the time and the network
address it came from.

- CSRF: every state-changing /api request must carry an Origin (or Referer)
  from this server or LIMINAL_ALLOWED_ORIGINS, so a page on another site
  cannot post to the API from a browser on the hospital network.
"""

import os
from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

import store

NETWORK = {"id": "network", "name": "Hospital network", "role": "admin"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _client(request: Request) -> str:
    return request.client.host if request.client else "unknown"


class OriginCheck(BaseHTTPMiddleware):
    """Refuse state-changing API requests that did not come from our own pages."""

    async def dispatch(self, request, call_next):
        if request.method not in ("GET", "HEAD", "OPTIONS") and request.url.path.startswith("/api/"):
            source = request.headers.get("origin") or request.headers.get("referer") or ""
            host = urlparse(source).netloc
            allowed = {request.headers.get("host", "")} | {
                urlparse(o.strip()).netloc for o in os.getenv("LIMINAL_ALLOWED_ORIGINS", "").split(",") if o.strip()}
            if not host or host not in allowed:
                return JSONResponse({"detail": "Request refused: unknown origin."}, status_code=403)
        return await call_next(request)


# ---------------------------------------------------------------- audit trail
# Every change, and every read of a recording, transcript or document: time,
# network address, route, meeting and result, never the content. Append-only (triggers in store.py).
# The server's own automatic sends are rows of their own (method AUTO, address "server").
_READS = ("/recording", "/transcript", "/documents/")
AUTO = "AUTO"
ALREADY = 208   # recorded (not answered) when a Send finds the minutes already on their way
_M = "/api/meetings/{meeting_id}"
ACTIONS = {
    ("POST", "/api/meetings"): "Created a meeting", ("PATCH", _M): "Changed the meeting details",
    ("POST", f"{_M}/recording"): "Saved part of a recording", ("GET", f"{_M}/recording"): "Listened to a recording",
    ("POST", f"{_M}/upload"): "Uploaded a recording", ("POST", f"{_M}/process"): "Started processing",
    ("PATCH", f"{_M}/minutes"): "Edited the minutes", ("PATCH", f"{_M}/actions/{{action_id}}"): "Edited an action item",
    ("POST", f"{_M}/confirmations/{{fact_id}}"): "Settled an item to confirm",
    ("PATCH", f"{_M}/participants"): "Changed the participants", ("POST", f"{_M}/feedback"): "Sent feedback",
    ("PATCH", f"{_M}/participants/{{participant_id}}"): "Named a participant",
    ("POST", f"{_M}/participants/{{participant_id}}/merge"): "Merged two participants into one",
    ("POST", f"{_M}/review"): "Marked the minutes as reviewed", ("GET", f"{_M}/transcript"): "Read a transcript",
    ("POST", f"{_M}/send"): "Sent the minutes", (AUTO, f"{_M}/send"): "Sent the minutes automatically",
    ("POST", f"{_M}/stop-send"): "Stopped an automatic send", ("GET", f"{_M}/documents/{{name}}"): "Opened a document",
    ("POST", "/api/people"): "Added a person", ("POST", "/api/people/{person_id}/voice-enrollment"): "Recorded a voice sample",
    ("POST", "/api/speaker-clusters/{cluster_id}/identify"): "Named a voice",
    ("POST", "/api/templates"): "Created a template", ("PATCH", "/api/templates/{template_id}"): "Changed a template",
    ("POST", "/api/templates/{template_id}/deactivate"): "Switched off a template",
    ("POST", "/api/admin/glossary-candidates/approve"): "Approved a glossary word",
    ("POST", "/api/admin/people"): "Added a staff member", ("PATCH", "/api/admin/people/{person_id}"): "Changed a staff member",
    ("POST", "/api/admin/people/{person_id}/roles"): "Assigned a role",
    ("PATCH", "/api/admin/lists/{list_id}"): "Changed a distribution list", ("POST", "/api/email/send"): "Sent an email",
}


class AuditTrail(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        path = request.url.path
        if path.startswith("/api/") and (request.method not in ("GET", "HEAD", "OPTIONS") or any(r in path for r in _READS)):
            route = getattr(request.scope.get("route"), "path", path)
            status = getattr(request.state, "audit_status", response.status_code)
            with store.tx() as c:
                c.execute("INSERT INTO audit(at,method,route,meeting_id,status,address) VALUES(?,?,?,?,?,?)",
                          (now_iso(), request.method, route, request.path_params.get("meeting_id"),
                           status, _client(request)))
        return response


def audit_server(route: str, meeting_id: str | None, status: int) -> None:
    """A row for something the server did by itself, such as an automatic send."""
    with store.tx() as c:
        c.execute("INSERT INTO audit(at,method,route,meeting_id,status,address) VALUES(?,?,?,?,?,?)",
                  (now_iso(), AUTO, route, meeting_id, status, "server"))


def audit_action(method: str, route: str, status: int) -> str:
    if status == ALREADY and route.endswith("/send"):
        return "Asked to send; the minutes were already on their way"
    label = ACTIONS.get((method, route), "Other request")
    return f"{label} (refused)" if status >= 400 else label


def audit_rows(limit: int = 500, before: int | None = None) -> list[dict]:
    """Newest first; `before` is the id of the last row of the previous page.
    Rows are known by network address; the server's own sends also say who."""
    rows = store.db().execute("SELECT * FROM audit WHERE id < ? ORDER BY id DESC LIMIT ?",
                              (before or 2**63 - 1, limit)).fetchall()
    return [{"id": r["id"], "at": r["at"], **({"user": "Automatic send"} if r["method"] == AUTO else {}),
             "action": audit_action(r["method"], r["route"], r["status"]), "method": r["method"], "route": r["route"],
             "meetingId": r["meeting_id"], "status": r["status"], "address": r["address"]} for r in rows]
