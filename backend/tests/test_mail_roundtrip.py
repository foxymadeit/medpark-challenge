"""Real SMTP over loopback: the minutes reach the distribution list with every PDF
attached. A tiny in-process SMTP server stands in for Mailpit."""

import email
import socketserver
import threading
from email import policy

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
    body = {"minutes": Minutes(title="Consiliul medical", meeting_type="medical", summary="S", decisions=["D"]).model_dump(),
            "documents": [{"fileName": f"MoM_{lang}.pdf", "data": "JVBERi0xLjc="} for lang in ("ro", "ru", "en")],
            "participant_emails": []}
    try:
        delivery._via_smtp(body)
    finally:
        server.shutdown()
    [(to, raw)] = _Sink.messages
    msg = email.message_from_bytes(raw, policy=policy.default)
    assert to == ["medical-board@hospital.local"] and "Consiliul medical" in msg["Subject"]
    files = [(p.get_filename(), p.get_content_type()) for p in msg.iter_attachments()]
    assert files == [("MoM_ro.pdf", "application/pdf"), ("MoM_ru.pdf", "application/pdf"), ("MoM_en.pdf", "application/pdf")]
