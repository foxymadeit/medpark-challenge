"""Accounts, sessions and request checks.

- Passwords: scrypt (stdlib), per-user salt, constant-time compare.
- Sessions: random token in an HttpOnly, SameSite=Strict cookie; only its
  SHA-256 is stored. 30 minutes idle, 12 hours absolute.
- Login: generic failure message, at most 5 failures per address and account
  in 15 minutes and 20 per address.
- CSRF: every state-changing /api request must carry an Origin (or Referer)
  from this server or LIMINAL_ALLOWED_ORIGINS. With SameSite=Strict cookies
  this blocks cross-site form posts and fetches.
"""

import hashlib
import hmac
import os
import secrets
import time
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import Depends, HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

import store

COOKIE = "liminal_session"
IDLE_S = 30 * 60
ABSOLUTE_S = 12 * 3600
FAIL_WINDOW_S = 15 * 60
MAX_FAILS_ACCOUNT = 5
MAX_FAILS_ADDRESS = 20
_SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 64}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    key = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return f"scrypt${salt.hex()}${key.hex()}"


def check_password(password: str, stored: str) -> bool:
    try:
        _, salt, key = stored.split("$")
        got = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), **_SCRYPT)
        return hmac.compare_digest(got.hex(), key)
    except ValueError:
        return False


_DUMMY = hash_password(secrets.token_hex(8))  # same work for unknown accounts


def create_user(email: str, name: str, role: str, password: str, *, username: str = "",
                staff_profile_id: str | None = None, created_by: str = "system") -> dict:
    if role not in ("admin", "staff"):
        raise ValueError("role must be admin or staff")
    uid = str(uuid.uuid4())
    with store.tx() as con:
        con.execute("INSERT INTO users(id,email,username,name,role,password_hash,staff_profile_id,active,created_at,created_by) "
                    "VALUES(?,?,?,?,?,?,?,1,?,?)",
                    (uid, email.strip(), username or email.split("@")[0], name, role, hash_password(password),
                     staff_profile_id, now_iso(), created_by))
    return user_by_id(uid)


def user_by_id(uid: str) -> dict | None:
    row = store.db().execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    return dict(row) if row else None


def public_user(u: dict) -> dict:
    """AuthUser as the frontend reads it; never the hash."""
    initials = "".join(w[0] for w in u["name"].split()[:2]).upper()
    out = {"id": u["id"], "email": u["email"], "name": u["name"], "role": u["role"], "initials": initials}
    if u.get("staff_profile_id"):
        out["staffProfileId"] = u["staff_profile_id"]
    return out


def account(u: dict) -> dict:
    """UserAccount for the admin pages."""
    out = {"id": u["id"], "username": u["username"] or u["email"], "email": u["email"], "role": u["role"],
           "active": bool(u["active"]), "createdAt": u["created_at"], "createdBy": u["created_by"]}
    if u.get("staff_profile_id"):
        out["staffProfileId"] = u["staff_profile_id"]
    return out


def _client(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def login(request: Request, response: Response, email: str, password: str) -> dict:
    con = store.db()
    address, key = _client(request), f"{_client(request)}|{email.strip().casefold()}"
    since = time.time() - FAIL_WINDOW_S
    fails_key = con.execute("SELECT COUNT(*) FROM login_failures WHERE key=? AND at>?", (key, since)).fetchone()[0]
    fails_addr = con.execute("SELECT COUNT(*) FROM login_failures WHERE key LIKE ? AND at>?",
                             (f"{address}|%", since)).fetchone()[0]
    if fails_key >= MAX_FAILS_ACCOUNT or fails_addr >= MAX_FAILS_ADDRESS:
        raise HTTPException(429, "Too many attempts. Try again in 15 minutes.")
    row = con.execute("SELECT * FROM users WHERE email=?", (email.strip(),)).fetchone()
    ok = check_password(password, row["password_hash"] if row else _DUMMY) and row is not None and row["active"]
    if not ok:
        with store.tx() as c:
            c.execute("INSERT INTO login_failures(key,at) VALUES(?,?)", (key, time.time()))
            c.execute("DELETE FROM login_failures WHERE at<?", (since,))
        raise HTTPException(401, "Email or password is incorrect.")
    token = secrets.token_urlsafe(32)
    with store.tx() as c:
        c.execute("INSERT INTO sessions(token_hash,user_id,created_at,last_seen) VALUES(?,?,?,?)",
                  (_digest(token), row["id"], time.time(), time.time()))
        c.execute("DELETE FROM login_failures WHERE key=?", (key,))
    response.set_cookie(COOKIE, token, httponly=True, samesite="strict", path="/",
                        secure=os.getenv("LIMINAL_SECURE_COOKIES", "0") == "1", max_age=ABSOLUTE_S)
    return public_user(dict(row))


def logout(request: Request, response: Response) -> None:
    token = request.cookies.get(COOKIE)
    if token:
        with store.tx() as c:
            c.execute("DELETE FROM sessions WHERE token_hash=?", (_digest(token),))
    response.delete_cookie(COOKIE, path="/")


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def current_user(request: Request) -> dict:
    token = request.cookies.get(COOKIE)
    if not token:
        raise HTTPException(401, "Sign in first.")
    now = time.time()
    with store.tx() as c:
        s = c.execute("SELECT * FROM sessions WHERE token_hash=?", (_digest(token),)).fetchone()
        if not s or now - s["last_seen"] > IDLE_S or now - s["created_at"] > ABSOLUTE_S:
            if s:
                c.execute("DELETE FROM sessions WHERE token_hash=?", (s["token_hash"],))
            raise HTTPException(401, "Your session ended. Sign in again.")
        c.execute("UPDATE sessions SET last_seen=? WHERE token_hash=?", (now, s["token_hash"]))
    u = user_by_id(s["user_id"])
    if not u or not u["active"]:
        raise HTTPException(401, "Sign in first.")
    return u


def require_admin(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(403, "Only an administrator can do this.")
    return user


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


def ensure_admin() -> None:
    """First start: create the administrator from LIMINAL_ADMIN_EMAIL and
    LIMINAL_ADMIN_PASSWORD, or a random password written once to an
    owner-only file, never to a log."""
    if store.db().execute("SELECT 1 FROM users LIMIT 1").fetchone():
        return
    email = os.getenv("LIMINAL_ADMIN_EMAIL", "admin@medpark.local")
    password = os.getenv("LIMINAL_ADMIN_PASSWORD") or secrets.token_urlsafe(12)
    create_user(email, "Administrator", "admin", password, username="admin")
    if not os.getenv("LIMINAL_ADMIN_PASSWORD"):
        path = store.DATA / "initial-admin-password.txt"
        path.write_text(f"{email}\n{password}\n")
        os.chmod(path, 0o600)
