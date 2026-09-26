"""The Liminal API end to end, with fake pipeline stages and the network blocked
(main.py installs the outbound guard on import)."""

import io
import json
import os
import re
import socket
import sys
import time
import wave
from pathlib import Path
from unittest.mock import patch

import pytest

os.environ["LIMINAL_START_WORKERS"] = "0"

from fastapi.testclient import TestClient  # noqa: E402

import api  # noqa: E402
import delivery  # noqa: E402
import jobs  # noqa: E402
import main  # noqa: E402
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
    monkeypatch.setenv("LIMINAL_RENDER_CMD", f"{sys.executable} {FAKE}/render.py {{render}} --type {{type}}")
    with TestClient(main.app, headers=ORIGIN) as c:
        yield c


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
    m = new_meeting(c, **extra)
    upload(c, m["id"])
    assert c.post(f"/api/meetings/{m['id']}/process").json()["processingState"] == "queued"
    run_queue()
    return c.get(f"/api/meetings/{m['id']}").json()


# ---------------------------------------------------------------- open access and requests
def test_no_route_asks_anyone_to_sign_in(client):
    assert not client.cookies
    checked = 0
    for route in [*api.router.routes, *main.app.routes]:
        if not getattr(route, "path", "").startswith("/api/"):
            continue
        path = re.sub(r"{[^}]+}", "x", route.path)
        for method in route.methods - {"HEAD", "OPTIONS"}:
            r = client.request(method, path, json={})
            assert r.status_code not in (401, 403), (method, path, r.status_code)
            checked += 1
    assert checked > 30
    for gone in ("/api/auth/login", "/api/auth/logout", "/api/admin/users"):
        assert client.post(gone, json={}).status_code in (404, 405), gone


def test_meetings_are_served_with_no_cookie_and_visible_to_every_page(client):
    m = new_meeting(client)
    other = TestClient(main.app, headers=ORIGIN)   # another computer on the hospital network
    assert not other.cookies
    assert [x["id"] for x in other.get("/api/meetings").json()] == [m["id"]]
    assert other.get(f"/api/meetings/{m['id']}").json()["title"] == "Consiliul medical"
    assert m["createdBy"] == "network"


def test_state_changes_from_another_origin_are_refused(client):
    assert client.post("/api/meetings", json={}, headers={"Origin": "http://evil.example"}).status_code == 403
    bare = TestClient(main.app)
    assert bare.post("/api/meetings", json={"title": "x", "type": "medical", "inputMode": "upload"}).status_code == 403


def test_a_database_from_the_account_days_loses_its_passwords(tmp_path):
    import sqlite3
    old = tmp_path / "old"
    old.mkdir()
    con = sqlite3.connect(old / "liminal.db")
    con.executescript("CREATE TABLE users (id TEXT, password_hash TEXT); INSERT INTO users VALUES ('u', 'scrypt$x$y');"
                      "CREATE TABLE sessions (token_hash TEXT); CREATE TABLE login_failures (key TEXT);")
    con.close()
    (old / "initial-admin-password.txt").write_text("admin@medpark.local\nsecret\n")
    store.reset_for_tests(old)
    tables = {r[0] for r in store.db().execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert not tables & {"users", "sessions", "login_failures"}
    assert not (old / "initial-admin-password.txt").exists()


# ---------------------------------------------------------------- uploads
def test_upload_checks_bytes_not_names(client):
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
    assert owner["speakerId"] == "Speaker 3" and owner["name"] == "Participant 3" and owner["speakerNumber"] == 3
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
    s = client.get("/api/system").json()
    ids = [x["id"] for x in s["services"]]
    assert s["local"] is True and ids == ["asr", "speakers", "minutes", "automation", "mail", "storage"]
    assert all(x["name"] and x["description"] for x in s["services"])
    assert len({x["name"] for x in s["services"]}) == len(ids)   # no two rows read the same
    assert s["capabilities"] == {"autoModeAvailable": True}


def test_the_minutes_row_includes_the_language_model(client, monkeypatch):
    monkeypatch.setattr(api, "_tool", lambda stage: True)
    monkeypatch.setattr(api, "_probe", lambda url: True)
    row = next(x for x in client.get("/api/system").json()["services"] if x["id"] == "minutes")
    assert row["available"] is True
    monkeypatch.setattr(api, "_probe", lambda url: False)
    row = next(x for x in client.get("/api/system").json()["services"] if x["id"] == "minutes")
    assert row["available"] is False and "language model" in row["description"]


def test_any_answer_from_the_model_server_counts_as_running():
    import http.server
    import threading

    class NotHere(http.server.BaseHTTPRequestHandler):
        def do_GET(self):   # llama-server has no /api/version: a 404 still means it is up
            self.send_response(404)
            self.end_headers()

        def log_message(self, *a):
            pass
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), NotHere)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        assert api._probe(f"http://127.0.0.1:{server.server_address[1]}/api/version") is True
    finally:
        server.shutdown()
        server.server_close()
    assert api._probe(f"http://127.0.0.1:{server.server_address[1]}/api/version") is False


def test_security_headers(client):
    r = client.get("/api/meetings")
    assert r.headers["x-frame-options"] == "DENY" and "default-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["cache-control"] == "no-store"


def test_templates_are_written_and_deactivated_from_any_page(client):
    person = client.post("/api/people", json={"name": "Elena Ciobanu"}).json()
    body = {"name": "Consiliu", "meetingType": "medical", "participantStaffIds": [person["id"]]}
    t = client.post("/api/templates", json=body)
    assert t.status_code == 201 and t.json()["createdBy"] == "network"
    assert client.post("/api/templates", json={**body, "participantStaffIds": ["nobody"]}).status_code == 422
    changed = client.patch(f"/api/templates/{t.json()['id']}", json={"participantStaffIds": []})
    assert changed.status_code == 200 and changed.json()["participantStaffIds"] == []
    gone = client.post(f"/api/templates/{t.json()['id']}/deactivate")
    assert gone.status_code == 200 and gone.json()["active"] is False
    assert client.get("/api/templates").json() == []


def test_enrolling_a_voice_again_replaces_it(client):
    person = client.post("/api/people", json={"name": "Elena Ciobanu"}).json()
    enroll = lambda: client.post(f"/api/people/{person['id']}/voice-enrollment",
                                 files={"audio": ("voice.wav", wav_bytes(), "audio/wav")})
    assert enroll().status_code == 204
    assert enroll().status_code == 204
    assert [v["staffId"] for v in client.get("/api/voice-profiles").json()] == [person["id"]]


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
    # the documents follow the type: new names and titles, the medical files gone
    assert after["documents"] == {lang: {"pdf": f"MoM_2026-09-26_executive_{lang}.pdf",
                                         "docx": f"MoM_2026-09-26_executive_{lang}.docx"} for lang in ("ro", "ru", "en")}
    folder = jobs.work_dir(m["id"]) / "minutes"
    assert not list(folder.glob("MoM_*_medical_*")) and (folder / "MoM_2026-09-26_executive.render.json").is_file()
    assert client.get(f"/api/meetings/{m['id']}/documents/en.pdf").content == b"%PDF-1.7 fake executive en"


def test_if_the_documents_cannot_be_rebuilt_the_type_stays(client, monkeypatch):
    monkeypatch.setenv("FAKE_DETECTED", "executive")
    m = processed(client)
    monkeypatch.setenv("LIMINAL_RENDER_CMD", f"{sys.executable} -c raise SystemExit(2)")
    r = client.post(f"/api/meetings/{m['id']}/confirmations/meeting-type", json={"action": "remove"})
    assert r.status_code == 503
    got = client.get(f"/api/meetings/{m['id']}").json()
    assert got["type"] == "medical" and got["documents"] == m["documents"]
    assert any(c["id"] == "meeting-type" for c in got["needsConfirmation"])
    assert client.get(f"/api/meetings/{m['id']}/documents/en.pdf").status_code == 200


def test_keeping_the_chosen_type_renders_nothing(client, monkeypatch):
    monkeypatch.setenv("FAKE_DETECTED", "executive")
    m = processed(client)
    monkeypatch.setenv("LIMINAL_RENDER_CMD", f"{sys.executable} -c raise SystemExit(2)")
    r = client.post(f"/api/meetings/{m['id']}/confirmations/meeting-type", json={"action": "keep"})
    assert r.status_code == 200 and r.json()["type"] == "medical" and r.json()["documents"] == m["documents"]


def test_a_matching_type_changes_nothing(client, monkeypatch):
    monkeypatch.setenv("FAKE_DETECTED", "medical")
    m = processed(client)
    assert m["status"] == "sending_soon" and not m["needsConfirmation"]


def test_the_audit_trail_records_what_and_from_where_and_cannot_be_rewritten(client):
    m = processed(client)
    client.get(f"/api/meetings/{m['id']}/documents/ro.pdf")
    rows = client.get("/api/admin/audit").json()
    actions = [(r["method"], r["route"]) for r in rows]
    assert ("POST", "/api/meetings/{meeting_id}/upload") in actions
    assert ("GET", "/api/meetings/{meeting_id}/documents/{name}") in actions
    assert all(r["address"] and r["at"] for r in rows) and not any("userId" in r or "user" in r for r in rows)
    assert not any("Consiliul" in json.dumps(r) for r in rows)   # never the content
    with pytest.raises(Exception):
        with store.tx() as con:
            con.execute("DELETE FROM audit")


def test_audit_rows_carry_time_meeting_and_a_readable_action(client):
    m = processed(client)
    client.patch(f"/api/meetings/{m['id']}/minutes", json={"summary": "Suspect pneumania."})
    client.patch(f"/api/meetings/{m['id']}/minutes", json={"summary": "Suspect pneumonia."})
    client.post("/api/admin/glossary-candidates/approve", json={"heard": "pneumania", "corrected": "pneumonia", "lang": "ro"})
    rows = client.get("/api/admin/audit").json()
    up = next(r for r in rows if r["route"].endswith("/upload"))
    assert up["meetingId"] == m["id"] and up["action"] == "Uploaded a recording"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", up["at"])
    assert next(r for r in rows if r["route"].endswith("/approve"))["action"] == "Approved a glossary word"
    assert all(r["action"] and not r["action"].startswith("/") for r in rows)


def test_audit_pages_with_limit_and_before(client):
    processed(client)
    everything = client.get("/api/admin/audit").json()
    first = client.get("/api/admin/audit?limit=2").json()
    assert [r["id"] for r in first] == [r["id"] for r in everything[:2]]
    second = client.get(f"/api/admin/audit?limit=2&before={first[-1]['id']}").json()
    assert [r["id"] for r in second] == [r["id"] for r in everything[2:4]]
    assert client.get("/api/admin/audit?limit=0").status_code == 422


def test_an_automatic_send_is_audited_as_the_server_not_the_viewer(client):
    m = processed(client)
    with patch.object(delivery.EmailService, "send_mom_email", return_value=EmailDeliveryResult(("a",), ())), \
            patch.object(delivery, "deliver_async", delivery.deliver):
        store.update("meetings", m["id"], lambda x: x.update(sendScheduledAt="2000-01-01T00:00:00Z"))
        delivery.Scheduler().tick()
        client.post(f"/api/meetings/{m['id']}/send", headers={"Idempotency-Key": f"minutes-{m['id']}"})
    rows = [r for r in client.get("/api/admin/audit").json() if r["meetingId"] == m["id"] and "send" in r["route"]]
    auto = [r for r in rows if r.get("user") == "Automatic send"]
    assert len(auto) == 1 and auto[0]["address"] == "server" and auto[0]["action"] == "Sent the minutes automatically"
    viewer = next(r for r in rows if r["address"] != "server")
    assert "user" not in viewer
    assert viewer["action"] != "Sent the minutes" and "already" in viewer["action"]


# ---------------------------------------------------------------- learning from corrections
def test_an_edit_records_only_the_changed_field_and_when(client):
    m = processed(client)
    client.patch(f"/api/meetings/{m['id']}/actions/A1", json={"task": "Pacient cu pneumania, control mâine."})
    client.patch(f"/api/meetings/{m['id']}/actions/A1", json={"task": "Pacient cu pneumonia, control mâine."})
    client.patch(f"/api/meetings/{m['id']}/actions/A1", json={"completed": True})   # not a correction
    rows = store.all_docs("corrections")
    assert len(rows) == 2
    last = rows[-1]
    assert (last["meetingId"], last["item"], last["field"]) == (m["id"], "A1", "task")
    assert last["before"] == "Pacient cu pneumania, control mâine." and last["after"] == "Pacient cu pneumonia, control mâine."
    assert last["by"] == "network" and last["at"]
    assert set(last) == {"id", "meetingId", "item", "field", "before", "after", "by", "at"}


def test_term_fixes_are_word_swaps_not_punctuation_or_case():
    import corrections
    assert corrections.term_pairs("Pacient cu pneumania acută.", "Pacient cu pneumonia acută!") == [("pneumania", "pneumonia")]
    assert corrections.term_pairs("se face coronarografia azi", "se face Coronarografia azi") == []
    assert corrections.term_pairs("infarct miocradic ieri", "infarct miocardic ieri") == [("miocradic", "miocardic")]
    assert corrections.term_pairs("un pat", "o masă") == []                         # too short to be a term
    assert corrections.term_pairs("a b c d e f", "totul a fost rescris complet acum") == []   # a rewrite, not a term
    assert corrections.term_pairs("Protocolul aprobat.", "Protocolul respins.") == []   # a new word, not a respelling


def test_candidates_come_by_count(client):
    m = processed(client)
    url = f"/api/meetings/{m['id']}/minutes"
    for before, after in [("Pneumania confirmată.", "Pneumonia confirmată."),
                          ("Suspect pneumania.", "Suspect pneumonia."),
                          ("Se face coronarografie.", "Se face coronaroangiografie.")]:
        client.patch(url, json={"summary": before})
        client.patch(url, json={"summary": after})
    got = client.get("/api/admin/glossary-candidates").json()
    assert [(c["heard"], c["corrected"], c["count"]) for c in got][:2] == [
        ("pneumania", "pneumonia", 2), ("coronarografie", "coronaroangiografie", 1)]
    assert got[0]["meetingIds"] == [m["id"]] and got[0]["approved"] is False and got[0]["lang"] == "ro"


def test_approving_writes_the_site_glossary_once(client):
    m = processed(client)
    client.patch(f"/api/meetings/{m['id']}/minutes", json={"summary": "Suspect pneumania."})
    client.patch(f"/api/meetings/{m['id']}/minutes", json={"summary": "Suspect pneumonia."})
    body = {"heard": "pneumania", "corrected": "pneumonia", "lang": "ro"}
    assert client.post("/api/admin/glossary-candidates/approve", json=body).status_code == 200
    assert client.post("/api/admin/glossary-candidates/approve", json=body).status_code == 200
    site = store.DATA / "site_glossary.json"
    assert oct(site.stat().st_mode & 0o777) == "0o600"
    rows = json.loads(site.read_text(encoding="utf-8"))["aligned"]
    assert rows == [{"source": "site", "ro": "pneumonia", "heard": "pneumania"}]
    assert client.get("/api/admin/glossary-candidates").json()[0]["approved"] is True
    assert client.post("/api/admin/glossary-candidates/approve",
                       json={**body, "lang": "de"}).status_code == 422


# ---------------------------------------------------------------- routing, queue, summary
def test_routing_gives_each_list_its_name_and_count_not_its_addresses(client, tmp_path, monkeypatch):
    table = tmp_path / "routing.json"
    table.write_text(json.dumps({"medical": ["a@h.local", "b@h.local"], "executive": ["c@h.local"], "administrative": []}))
    monkeypatch.setattr(delivery, "ROUTING", table)
    got = client.get("/api/routing").json()
    assert got == {"medical": {"name": "Medical board", "recipients": 2},
                   "executive": {"name": "Executive board", "recipients": 1},
                   "administrative": {"name": "Administrative board", "recipients": 0}}
    assert "@" not in json.dumps(got)
    store.update("lists", "medical", lambda x: x.update(active=False))
    assert client.get("/api/routing").json()["medical"]["recipients"] == 0


def test_queue_position_is_exact_and_first_in_line_is_starting(client):
    first, second = new_meeting(client), new_meeting(client)
    for m in (first, second):
        upload(client, m["id"])
        client.post(f"/api/meetings/{m['id']}/process")
    a = client.get(f"/api/meetings/{first['id']}/processing").json()
    b = client.get(f"/api/meetings/{second['id']}/processing").json()
    assert (a["processingState"], a["queuePosition"]) == ("running", 0)   # nothing ahead: starting
    assert (b["processingState"], b["queuePosition"]) == ("queued", 1)
    jobs.claim()   # the worker takes the first; the second still waits behind it
    assert client.get(f"/api/meetings/{second['id']}").json()["queuePosition"] == 1
    listed = {x["id"]: x for x in client.get("/api/meetings").json()}
    assert listed[first["id"]]["processingState"] == "running"
    run_queue()
    done = client.get(f"/api/meetings/{second['id']}").json()
    assert done["processingState"] == "complete" and "queuePosition" not in done


def test_the_fallback_summary_counts_in_the_minutes_language():
    facts = [{"kind": "topic", "text": "Protocolul ATI", "status": "ok"}]
    one = facts + [{"kind": "decision", "status": "ok"}, {"kind": "action", "status": "ok"}]
    five = facts + [{"kind": "decision", "status": "ok"}] * 5 + [{"kind": "action", "status": "ok"}] * 2
    assert jobs._summary(one, "en") == "Topics: Protocolul ATI. 1 decision, 1 action."
    assert jobs._summary(five, "en") == "Topics: Protocolul ATI. 5 decisions, 2 actions."
    assert jobs._summary(one, "ro") == "Subiecte: Protocolul ATI. 1 decizie, 1 acțiune."
    assert jobs._summary(five, "ro") == "Subiecte: Protocolul ATI. 5 decizii, 2 acțiuni."
    twenty = facts + [{"kind": "decision", "status": "ok"}] * 21
    assert jobs._summary(twenty, "ro") == "Subiecte: Protocolul ATI. 21 de decizii, 0 acțiuni."
    assert jobs._summary(one, "ru") == "Темы: Protocolul ATI. 1 решение, 1 поручение."
    assert jobs._summary(five, "ru") == "Темы: Protocolul ATI. 5 решений, 2 поручения."


def test_processed_minutes_name_their_language_and_summarise_in_it(client):
    m = processed(client)   # the fake transcript is mostly Romanian and has no exported summary
    assert m["minutesLanguage"] == "ro" and m["summary"] == "Subiecte: Protocolul ATI. 1 decizie, 1 acțiune."


def test_settled_minutes_get_their_stop_window_on_the_server(client, monkeypatch):
    monkeypatch.setenv("FAKE_CONFIRM", "1")
    m = processed(client)
    assert client.post(f"/api/meetings/{m['id']}/send-window").status_code == 409   # an item still waits
    client.post(f"/api/meetings/{m['id']}/confirmations/A2", json={"action": "keep"})
    r = client.post(f"/api/meetings/{m['id']}/send-window")
    assert r.status_code == 200
    w = r.json()
    assert w["status"] == "sending_soon" and w["sendScheduledAt"] and w["reviewState"] == "reviewed"
    assert client.post(f"/api/meetings/{m['id']}/stop-send").json()["status"] == "ready"
