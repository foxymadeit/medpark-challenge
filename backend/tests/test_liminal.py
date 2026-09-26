"""The Liminal API end to end, with fake pipeline stages and the network blocked
(main.py installs the outbound guard on import)."""

import io
import json
import os
import socket
import sys
import time
import wave
from pathlib import Path
from unittest.mock import patch

import pytest

os.environ["LIMINAL_START_WORKERS"] = "0"
os.environ["LIMINAL_ADMIN_EMAIL"] = "admin@medpark.local"
os.environ["LIMINAL_ADMIN_PASSWORD"] = "correct horse battery"

from fastapi.testclient import TestClient  # noqa: E402

import api  # noqa: E402
import delivery  # noqa: E402
import jobs  # noqa: E402
import main  # noqa: E402
import security  # noqa: E402
import store  # noqa: E402
from services.EmailService import EmailDeliveryResult  # noqa: E402

FAKE = Path(__file__).parent / "fake_stages"
ORIGIN = {"Origin": "http://testserver"}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    store.reset_for_tests(tmp_path / "data")
    for stage in ("asr", "diarize"):
        monkeypatch.setenv(f"LIMINAL_{stage.upper()}_CMD", f"{sys.executable} {FAKE / stage}.py {{audio}} {{work}}")
    monkeypatch.setenv("LIMINAL_MINUTES_CMD", f"{sys.executable} {FAKE}/minutes.py {{work}}/transcript.json "
                                              "--session {session} --type {type} --out {work}/minutes")
    with TestClient(main.app, headers=ORIGIN) as c:
        yield c


def login(c, email="admin@medpark.local", password="correct horse battery"):
    r = c.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


def wav_bytes(seconds=2.0) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(16000)
        w.writeframes(b"\x00\x00" * int(16000 * seconds))
    return buf.getvalue()


def new_meeting(c, **extra) -> dict:
    r = c.post("/api/meetings", json={"title": "Consiliul medical", "type": "medical", "inputMode": "upload", **extra})
    assert r.status_code == 201, r.text
    return r.json()


def upload(c, mid):
    r = c.post(f"/api/meetings/{mid}/upload", files={"audio": ("meeting.wav", wav_bytes(), "audio/wav")})
    assert r.status_code == 204, r.text


def run_queue():
    while (job := jobs.claim()) is not None:
        jobs.process(job)


def processed(c, **extra) -> dict:
    login(c)
    m = new_meeting(c, **extra)
    upload(c, m["id"])
    assert c.post(f"/api/meetings/{m['id']}/process").json()["processingState"] == "queued"
    run_queue()
    return c.get(f"/api/meetings/{m['id']}").json()


# ---------------------------------------------------------------- auth and requests
def test_login_is_generic_rate_limited_and_the_cookie_is_strict(client):
    r = client.post("/api/auth/login", json={"email": "admin@medpark.local", "password": "wrong"})
    assert r.status_code == 401 and "incorrect" in r.json()["detail"]
    assert client.post("/api/auth/login", json={"email": "nobody@x", "password": "wrong"}).json() == r.json()
    for _ in range(4):
        client.post("/api/auth/login", json={"email": "admin@medpark.local", "password": "wrong"})
    assert client.post("/api/auth/login", json={"email": "admin@medpark.local",
                                               "password": "correct horse battery"}).status_code == 429
    security_row = store.db().execute("SELECT password_hash FROM users").fetchone()[0]
    assert security_row.startswith("scrypt$") and "battery" not in security_row


def test_session_cookie_flags_me_and_logout(client):
    r = client.post("/api/auth/login", json={"email": "admin@medpark.local", "password": "correct horse battery"})
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    assert client.get("/api/auth/me").json()["role"] == "admin"
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_every_route_needs_a_session(client):
    for path in ("/api/meetings", "/api/people", "/api/templates", "/api/system", "/api/admin", "/api/action-items"):
        assert client.get(path).status_code == 401, path


def test_state_changes_from_another_origin_are_refused(client):
    login(client)
    assert client.post("/api/meetings", json={}, headers={"Origin": "http://evil.example"}).status_code == 403
    bare = TestClient(main.app)
    bare.cookies = client.cookies
    assert bare.post("/api/meetings", json={"title": "x", "type": "medical", "inputMode": "upload"}).status_code == 403


def test_staff_cannot_open_system_or_admin(client):
    security.create_user("nurse@medpark.local", "Nurse", "staff", "long enough password")
    login(client, "nurse@medpark.local", "long enough password")
    assert client.get("/api/system").status_code == 403
    assert client.get("/api/admin").status_code == 403
    assert client.post("/api/admin/users", json={"username": "x", "email": "x@x", "role": "admin"}).status_code == 403


def test_meetings_are_private_to_their_creator(client):
    login(client)
    m = new_meeting(client)
    security.create_user("nurse@medpark.local", "Nurse", "staff", "long enough password")
    login(client, "nurse@medpark.local", "long enough password")
    assert client.get(f"/api/meetings/{m['id']}").status_code == 404
    assert client.get("/api/meetings").json() == []


# ---------------------------------------------------------------- uploads
def test_upload_checks_bytes_not_names(client):
    login(client)
    m = new_meeting(client)
    url = f"/api/meetings/{m['id']}/upload"
    assert client.post(url, files={"audio": ("a.wav", b"<?xml evil", "audio/wav")}).status_code == 415
    assert client.post(url, files={"audio": ("a.wav", b"", "audio/wav")}).status_code == 422
    assert client.post(url, files={"audio": ("../../etc/passwd.wav", wav_bytes(), "text/plain")}).status_code == 204
    got = client.get(f"/api/meetings/{m['id']}").json()
    assert got["durationSeconds"] == 2.0 and got["status"] == "uploaded" and got["audioFilename"] == "passwd.wav"
    stored = jobs.work_dir(m["id"]) / "audio.wav"
    assert stored.is_file() and oct(stored.stat().st_mode & 0o777) == "0o600"


def test_the_server_owns_statuses(client):
    login(client)
    m = new_meeting(client)
    r = client.patch(f"/api/meetings/{m['id']}", json={"status": "sent", "distributionList": ["x@evil.example"]})
    assert r.status_code == 409
    r = client.patch(f"/api/meetings/{m['id']}", json={"distributionList": ["x@evil.example"], "title": "New"})
    assert r.json()["distributionList"] == delivery.recipients("medical") and r.json()["title"] == "New"
    assert "x@evil.example" not in r.json()["distributionList"]


# ---------------------------------------------------------------- processing
def test_full_flow_auto_mode_schedules_then_sends_once(client):
    m = processed(client)
    assert m["processingState"] == "complete" and m["progress"] == 100
    assert [d["text"] for d in m["decisions"]] == ["Se aprobă protocolul ATI."]
    owner = next(p for p in m["participants"] if p["id"] == m["actionItems"][0]["ownerParticipantId"])
    assert owner["speakerId"] == "Speaker 3" and owner["name"] == "Participant 3"
    assert m["actionItems"][0]["deadline"] == "2026-10-02" and m["actionItems"][0]["sourceTimestampSeconds"] == 12.0
    assert {s["speakerId"] for s in m["transcript"]} == {"Speaker 1", "Speaker 2", "Speaker 3"}
    assert m["status"] == "sending_soon" and m["sendWindowSeconds"] == 60
    assert set(m["documents"]) == {"ro", "ru", "en"}

    sent = []
    with patch.object(delivery.EmailService, "send_mom_email",
                      side_effect=lambda minutes, **kw: sent.append((minutes, kw)) or EmailDeliveryResult(("a",), ())), \
            patch.object(delivery, "deliver_async", delivery.deliver):
        store.update("meetings", m["id"], lambda x: x.update(sendScheduledAt="2000-01-01T00:00:00Z"))
        delivery.Scheduler().tick()
        again = client.post(f"/api/meetings/{m['id']}/send", headers={"Idempotency-Key": f"minutes-{m['id']}"})
    final = client.get(f"/api/meetings/{m['id']}").json()
    assert final["status"] == "sent" and final["deliveredVia"] == "smtp" and again.status_code == 200
    assert len(sent) == 1
    minutes, kw = sent[0]
    assert minutes.meeting_type == "medical" and [a[0] for a in kw["attachments"]] == [
        "MoM_2026-09-26_medical_en.pdf", "MoM_2026-09-26_medical_ro.pdf", "MoM_2026-09-26_medical_ru.pdf"]


def test_items_to_confirm_stop_auto_send_until_a_person_settles_them(client, monkeypatch):
    monkeypatch.setenv("FAKE_CONFIRM", "1")
    m = processed(client)
    assert m["status"] == "ready" and m["reviewState"] == "needs_review" and len(m["needsConfirmation"]) == 1
    assert client.post(f"/api/meetings/{m['id']}/send").status_code == 409
    assert client.post(f"/api/meetings/{m['id']}/review").status_code == 409
    r = client.post(f"/api/meetings/{m['id']}/confirmations/A2", json={"action": "remove"})
    assert r.json()["needsConfirmation"] == [] and [a["id"] for a in r.json()["actionItems"]] == ["A1"]
    assert client.post(f"/api/meetings/{m['id']}/review").json()["reviewState"] == "reviewed"
    with patch.object(delivery, "deliver_async", lambda mid: None):
        assert client.post(f"/api/meetings/{m['id']}/send").json()["status"] == "sending"


def test_stop_send_wins_over_the_scheduler(client):
    m = processed(client)
    assert client.post(f"/api/meetings/{m['id']}/stop-send").json()["status"] == "ready"
    store.update("meetings", m["id"], lambda x: x.update(sendScheduledAt="2000-01-01T00:00:00Z"))
    with patch.object(delivery, "deliver_async") as fire:
        delivery.Scheduler().tick()
    fire.assert_not_called()
    got = client.get(f"/api/meetings/{m['id']}").json()
    assert got["status"] == "ready" and got["sendMode"] == "manual" and got["deliveryState"] == "stopped"


def test_a_failed_delivery_is_never_reported_as_sent(client):
    m = processed(client)
    with patch.object(delivery.EmailService, "send_mom_email", side_effect=OSError("smtp down")):
        delivery.begin(m["id"], manual=False)
        delivery.deliver(m["id"])
    got = client.get(f"/api/meetings/{m['id']}").json()
    assert got["status"] == "ready" and got["deliveryState"] == "failed" and got["failureReference"]


def test_a_failed_stage_marks_the_meeting_failed_with_a_reference(client, monkeypatch):
    monkeypatch.setenv("LIMINAL_ASR_CMD", f"{sys.executable} -c raise SystemExit(3)")
    m = processed(client)
    assert m["status"] == "failed" and m["processingState"] == "failed" and len(m["failureReference"]) == 8


def test_running_jobs_go_back_to_the_queue_after_a_restart(client):
    login(client)
    m = new_meeting(client)
    upload(client, m["id"])
    client.post(f"/api/meetings/{m['id']}/process")
    assert jobs.claim()["meeting_id"] == m["id"]
    assert jobs.claim() is None          # it is running now
    assert jobs.recover() == 1           # the server restarts
    run_queue()
    assert client.get(f"/api/meetings/{m['id']}").json()["processingState"] == "complete"


def test_documents_are_served_only_from_the_meeting_folder(client):
    m = processed(client)
    r = client.get(f"/api/meetings/{m['id']}/documents/ro.pdf")
    assert r.status_code == 200 and r.content.startswith(b"%PDF") and r.headers["content-type"] == "application/pdf"
    for bad in ("..%2Fliminal.db", "de.pdf", "ro.exe"):
        assert client.get(f"/api/meetings/{m['id']}/documents/{bad}").status_code == 404


def test_editing_after_sending_is_refused_but_completion_still_works(client):
    m = processed(client)
    store.update("meetings", m["id"], lambda x: x.update(status="sent"))
    url = f"/api/meetings/{m['id']}/actions/A1"
    assert client.patch(url, json={"task": "changed"}).status_code == 409
    assert client.patch(url, json={"completed": True}).json()["actionItems"][0]["completed"] is True
    assert client.patch(f"/api/meetings/{m['id']}/minutes", json={"summary": "x"}).status_code == 409


def test_naming_a_voice_renames_its_participant_and_keeps_the_owner(client):
    m = processed(client)
    person = client.post("/api/people", json={"name": "Elena Ciobanu", "email": "elena@medpark.local"}).json()
    cluster = next(c for c in client.get("/api/speaker-clusters").json() if c["speakerId"] == "Speaker 3")
    client.post(f"/api/speaker-clusters/{cluster['id']}/identify", json={"staffId": person["id"]})
    got = client.get(f"/api/meetings/{m['id']}").json()
    owner = next(p for p in got["participants"] if p["id"] == got["actionItems"][0]["ownerParticipantId"])
    assert owner["name"] == "Elena Ciobanu" and owner["email"] == "elena@medpark.local"


# ---------------------------------------------------------------- offline
def test_nothing_leaves_the_machine(client):
    with pytest.raises(OSError, match="network disabled"):
        socket.create_connection(("93.184.216.34", 80), timeout=1)
    monkey = {"LIMINAL_N8N_WEBHOOK": "http://93.184.216.34/webhook/x"}
    with patch.dict(os.environ, monkey), patch.object(delivery, "N8N_WEBHOOK", monkey["LIMINAL_N8N_WEBHOOK"]):
        assert delivery._via_n8n({"x": 1}) is False   # refused by the guard, so the backend mails directly


def test_system_reports_each_service(client):
    login(client)
    s = client.get("/api/system").json()
    assert s["local"] is True and {x["id"] for x in s["services"]} >= {"asr", "speakers", "mail", "automation", "storage"}
    assert s["capabilities"] == {"autoModeAvailable": True}


def test_security_headers(client):
    r = client.get("/api/auth/me")
    assert r.headers["x-frame-options"] == "DENY" and "default-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["cache-control"] == "no-store"


def test_only_an_admin_writes_templates(client):
    login(client)
    person = client.post("/api/people", json={"name": "Elena Ciobanu"}).json()
    body = {"name": "Consiliu", "meetingType": "medical", "participantStaffIds": [person["id"]]}
    t = client.post("/api/templates", json=body)
    assert t.status_code == 201
    security.create_user("nurse@medpark.local", "Nurse", "staff", "long enough password")
    login(client, "nurse@medpark.local", "long enough password")
    assert client.post("/api/templates", json=body).status_code == 403
    assert client.patch(f"/api/templates/{t.json()['id']}", json={"participantStaffIds": []}).status_code == 403
    assert client.post(f"/api/templates/{t.json()['id']}/deactivate").status_code == 403
    login(client)
    gone = client.post(f"/api/templates/{t.json()['id']}/deactivate")
    assert gone.status_code == 200 and gone.json()["active"] is False
    assert client.get("/api/templates").json() == []


def test_staff_enroll_a_voice_once_and_only_an_admin_replaces_it(client):
    login(client)
    person = client.post("/api/people", json={"name": "Elena Ciobanu"}).json()
    security.create_user("nurse@medpark.local", "Nurse", "staff", "long enough password")
    login(client, "nurse@medpark.local", "long enough password")
    enroll = lambda: client.post(f"/api/people/{person['id']}/voice-enrollment",
                                 files={"audio": ("voice.wav", wav_bytes(), "audio/wav")})
    assert enroll().status_code == 204
    assert enroll().status_code == 403
    login(client)
    assert enroll().status_code == 204


def test_a_meeting_that_sounds_like_another_type_waits_for_a_person(client, monkeypatch):
    monkeypatch.setenv("FAKE_DETECTED", "executive")
    m = processed(client)
    assert m["status"] == "ready" and m["detectedType"] == "executive"
    item = next(c for c in m["needsConfirmation"] if c["id"] == "meeting-type")
    assert item["detectedType"] == "executive"
    r = client.post(f"/api/meetings/{m['id']}/confirmations/meeting-type", json={"action": "remove"})
    assert r.status_code == 200
    after = r.json()
    assert after["type"] == "executive" and after["distributionList"] == api._distribution("executive")
    assert all(c["id"] != "meeting-type" for c in after["needsConfirmation"])


def test_a_matching_type_changes_nothing(client, monkeypatch):
    monkeypatch.setenv("FAKE_DETECTED", "medical")
    m = processed(client)
    assert m["status"] == "sending_soon" and not m["needsConfirmation"]
