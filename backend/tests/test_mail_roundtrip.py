"""Real SMTP over loopback: the minutes reach the distribution list with every PDF
attached. A tiny in-process SMTP server stands in for Mailpit."""

import email
import json
import shutil
import socketserver
import subprocess
import threading
from email import policy
from pathlib import Path

import pytest

import delivery
from schemas import Minutes


class _Sink(socketserver.StreamRequestHandler):
    messages: list = []

    def handle(self):
        send = lambda line: self.wfile.write(line.encode() + b"\r\n")  # noqa: E731
        send("220 sink")
        rcpt, data = [], None
        while line := self.rfile.readline():
            cmd = line.decode().strip()
            if data is not None:
                if cmd == ".":
                    self.messages.append((rcpt, b"".join(data)))
                    rcpt, data = [], None
                    send("250 queued")
                else:
                    data.append(line[1:] if line.startswith(b"..") else line)
            elif cmd.upper().startswith(("EHLO", "HELO")):
                send("250 sink")
            elif cmd.upper().startswith("RCPT"):
                rcpt.append(cmd.split(":", 1)[1].strip(" <>"))
                send("250 ok")
            elif cmd.upper() == "DATA":
                data = []
                send("354 go")
            elif cmd.upper() == "QUIT":
                send("221 bye")
                return
            else:
                send("250 ok")


def test_minutes_arrive_with_all_pdfs(monkeypatch, tmp_path):
    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), _Sink)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    _Sink.messages = []
    routing = tmp_path / "routing.json"
    routing.write_text('{"medical": ["medical-board@hospital.local"]}')
    monkeypatch.setattr(delivery, "ROUTING", routing)
    monkeypatch.setenv("SMTP_HOST", "127.0.0.1")
    monkeypatch.setenv("SMTP_PORT", str(server.server_address[1]))
    monkeypatch.setenv("SMTP_ALLOWED_HOSTS", "127.0.0.1")
    body = {"minutes": Minutes(title="Consiliul medical", meeting_type="medical", date="2026-09-26", summary="S",
                               decisions=["D"]).model_dump(),
            "documents": [{"fileName": f"MoM_{lang}.pdf", "data": "JVBERi0xLjc="} for lang in ("ro", "ru", "en")],
            "participant_emails": []}
    try:
        delivery._via_smtp(body)
    finally:
        server.shutdown()
    [(to, raw)] = _Sink.messages
    msg = email.message_from_bytes(raw, policy=policy.default)
    assert to == ["medical-board@hospital.local"]
    assert msg["Subject"] == "Proces-verbal al ședinței Consiliului Medical din 26 septembrie 2026"
    text = msg.get_body(preferencelist=("plain",)).get_content()
    assert text.startswith("Stimați membri ai Consiliului Medical,") and "2. Procesul-verbal în limba rusă" in text
    files = [(p.get_filename(), p.get_content_type()) for p in msg.iter_attachments()]
    assert files == [("MoM_ro.pdf", "application/pdf"), ("MoM_ru.pdf", "application/pdf"), ("MoM_en.pdf", "application/pdf")]


WORKFLOW = Path(__file__).resolve().parents[1] / "n8n" / "liminal-routing.json"


def _prepare(body: dict) -> dict:
    """Run the n8n "Prepare the email" code node on a webhook body, in node."""
    code = next(n for n in json.loads(WORKFLOW.read_text())["nodes"] if n["name"] == "Prepare the email")
    script = (f"const $input = {{ first: () => ({{ json: {{ body: {json.dumps(body)} }} }}) }};\n"
              f"const out = (() => {{\n{code['parameters']['jsCode']}\n}})();\n"
              "process.stdout.write(JSON.stringify(out[0].json));")
    run = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


def test_n8n_keeps_its_secret_check_and_routing():
    flow = json.loads(WORKFLOW.read_text())
    hook = next(n for n in flow["nodes"] if n["type"] == "n8n-nodes-base.webhook")
    assert hook["parameters"]["authentication"] == "headerAuth" and hook["credentials"]["httpHeaderAuth"]
    switch = next(n for n in flow["nodes"] if n["type"] == "n8n-nodes-base.switch")
    assert "['medical', 'executive', 'administrative']" in switch["parameters"]["output"]
    routes = [r[0]["node"] for r in flow["connections"]["Route by meeting type"]["main"]]
    assert routes == ["Email the Medical board", "Email the Executive board", "Email the Administrative board"]


@pytest.mark.skipif(shutil.which("node") is None, reason="needs node to run the n8n code node")
def test_n8n_sends_the_backends_romanian_email_on_one_subject_line(monkeypatch, tmp_path):
    monkeypatch.setattr(delivery.store, "DATA", tmp_path)
    m = {"id": "m1", "title": "Weekly\r\nBcc: spy@evil.example", "type": "executive", "createdAt": "2026-09-26T08:00:00Z",
         "participants": [], "distributionList": ["exec@hospital.local"]}
    body = delivery.payload(m)
    body["email"]["subject"] += "\r\nBcc: spy@evil.example"   # n8n must not trust it either
    out = _prepare(body)
    assert out["subject"] == "Proces-verbal al ședinței Comitetului Executiv din 26 septembrie 2026 Bcc: spy@evil.example"
    assert out["text"] == body["email"]["text"] and out["text"].startswith("Stimați membri ai Comitetului Executiv,")
    assert out["to"] == "exec@hospital.local" and out["meetingType"] == "executive"
    with pytest.raises(AssertionError):   # no composed email: n8n refuses, and the backend mails directly
        _prepare({**body, "email": {}})
