"""A local SMTP catcher for the end-to-end test (a stand-in for Mailpit).
Accepts every message on 127.0.0.1:1025 and writes it to MAIL_DIR as .eml.
Standard library only; Python 3.12+ has no smtpd module any more."""

import asyncio
import os
import time
from pathlib import Path

MAIL_DIR = Path(os.environ.get("MAIL_DIR", "/tmp/liminal-mail"))
PORT = int(os.environ.get("SMTP_PORT", "1025"))


async def session(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    def say(line: str) -> None:
        writer.write((line + "\r\n").encode())

    say("220 liminal-sink ready")
    await writer.drain()
    while line := await reader.readline():
        cmd = line.decode(errors="replace").strip().upper()
        if cmd.startswith(("EHLO", "HELO")):
            say("250-liminal-sink\r\n250 SIZE 104857600")
        elif cmd == "DATA":
            say("354 end with <CRLF>.<CRLF>")
            await writer.drain()
            body = bytearray()
            while (chunk := await reader.readline()) not in (b".\r\n", b""):
                body += chunk[1:] if chunk.startswith(b"..") else chunk
            MAIL_DIR.mkdir(parents=True, exist_ok=True)
            (MAIL_DIR / f"{time.time_ns()}.eml").write_bytes(bytes(body))
            say("250 queued")
        elif cmd == "QUIT":
            say("221 bye")
            await writer.drain()
            break
        else:  # MAIL FROM, RCPT TO, RSET, NOOP
            say("250 ok")
        await writer.drain()
    writer.close()


async def main() -> None:
    server = await asyncio.start_server(session, "127.0.0.1", PORT)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
