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
_READS = ("/recording", "/transcript", "/documents/")


class AuditTrail(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        path = request.url.path
        if path.startswith("/api/") and (request.method not in ("GET", "HEAD", "OPTIONS") or any(r in path for r in _READS)):
            route = getattr(request.scope.get("route"), "path", path)
            with store.tx() as c:
                c.execute("INSERT INTO audit(at,method,route,meeting_id,status,address) VALUES(?,?,?,?,?,?)",
                          (now_iso(), request.method, route, request.path_params.get("meeting_id"),
                           response.status_code, _client(request)))
        return response


def audit_rows(limit: int = 500) -> list[dict]:
    rows = store.db().execute("SELECT * FROM audit ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [{"at": r["at"], "method": r["method"], "route": r["route"],
             "meetingId": r["meeting_id"], "status": r["status"], "address": r["address"]} for r in rows]
