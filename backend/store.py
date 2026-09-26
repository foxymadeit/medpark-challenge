"""SQLite storage for Liminal: accounts, sessions, the job queue, and JSON
documents (meetings, people, templates and the rest of the frontend's model).

One file, WAL mode, a single process. Every read-modify-write that changes a
status runs inside `tx()`, a BEGIN IMMEDIATE transaction, so the send
scheduler, stop-send and a duplicate Send can never interleave.
"""

import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path

DATA = Path(os.getenv("LIMINAL_DATA", Path(__file__).resolve().parent / "data"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL COLLATE NOCASE, username TEXT, name TEXT NOT NULL,
  role TEXT NOT NULL, password_hash TEXT NOT NULL, staff_profile_id TEXT,
  active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, created_by TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, created_at REAL NOT NULL, last_seen REAL NOT NULL);
CREATE TABLE IF NOT EXISTS login_failures (key TEXT NOT NULL, at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS login_failures_key ON login_failures(key, at);
CREATE TABLE IF NOT EXISTS docs (
  kind TEXT NOT NULL, id TEXT NOT NULL, data TEXT NOT NULL, updated_at REAL NOT NULL, PRIMARY KEY (kind, id));
CREATE TABLE IF NOT EXISTS audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, user_id TEXT, method TEXT NOT NULL, route TEXT NOT NULL,
  meeting_id TEXT, status INTEGER NOT NULL, address TEXT);
CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit BEGIN SELECT RAISE(ABORT, 'the audit trail is append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit BEGIN SELECT RAISE(ABORT, 'the audit trail is append-only'); END;
CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT, meeting_id TEXT NOT NULL, state TEXT NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL, updated_at REAL NOT NULL);
"""

_local = threading.local()
_lock = threading.RLock()  # ponytail: one lock for all writers; fine for one hospital server


def db() -> sqlite3.Connection:
    con = getattr(_local, "con", None)
    if con is None or getattr(_local, "path", None) != DATA:
        DATA.mkdir(parents=True, exist_ok=True)
        os.chmod(DATA, 0o700)
        con = sqlite3.connect(DATA / "liminal.db", timeout=30, isolation_level=None, check_same_thread=False)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA foreign_keys=ON")
        con.executescript(SCHEMA)
        os.chmod(DATA / "liminal.db", 0o600)
        _local.con, _local.path = con, DATA
    return con


@contextmanager
def tx():
    """An exclusive write transaction; nested calls join the outer one."""
    con = db()
    with _lock:
        if con.in_transaction:
            yield con
            return
        con.execute("BEGIN IMMEDIATE")
        try:
            yield con
            con.execute("COMMIT")
        except BaseException:
            con.execute("ROLLBACK")
            raise


def get(kind: str, id: str) -> dict | None:
    row = db().execute("SELECT data FROM docs WHERE kind=? AND id=?", (kind, id)).fetchone()
    return json.loads(row["data"]) if row else None


def put(kind: str, doc: dict) -> dict:
    with tx() as con:
        con.execute("INSERT INTO docs(kind,id,data,updated_at) VALUES(?,?,?,?) "
                    "ON CONFLICT(kind,id) DO UPDATE SET data=excluded.data, updated_at=excluded.updated_at",
                    (kind, doc["id"], json.dumps(doc, ensure_ascii=False), time.time()))
    return doc


def all_docs(kind: str) -> list[dict]:
    return [json.loads(r["data"]) for r in db().execute("SELECT data FROM docs WHERE kind=? ORDER BY rowid", (kind,))]


def update(kind: str, id: str, change) -> dict | None:
    """Read, change and write one document atomically. `change(doc)` mutates
    the dict in place (or raises to abort); returns the stored document."""
    with tx():
        doc = get(kind, id)
        if doc is None:
            return None
        change(doc)
        return put(kind, doc)


def reset_for_tests(path: Path) -> None:
    global DATA
    con = getattr(_local, "con", None)
    if con is not None:
        con.close()
        _local.con = None
    DATA = Path(path)
