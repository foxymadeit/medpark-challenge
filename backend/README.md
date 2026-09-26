# Liminal backend

The local server behind the Liminal web app. It implements every endpoint in
`frontend/API_CONTRACT.md` (branch `frontend-secure-mom`), runs the pipeline
on uploaded or recorded audio, and mails the minutes to the distribution list
for the meeting type. Nothing leaves the machine: the process refuses every
non-loopback connection, and every port is bound to 127.0.0.1.

```
upload / record ─► queue (SQLite) ─► transcription ┐
                                    diarization    ┴─► minutes (mom) ─► review or 60 s window ─► EmailService ─► local SMTP (Mailpit)
```

## Run it (laptop demo)

```bash
cd backend
uv sync
docker compose up -d                 # Mailpit: SMTP on 127.0.0.1:1025, inbox at http://127.0.0.1:8025
cp .env.example .env                 # then set LIMINAL_ADMIN_PASSWORD and the three stage commands
uv run uvicorn main:app --host 127.0.0.1 --port 8000
```

Serve the built web app from the same origin with
`LIMINAL_FRONTEND_DIST=../frontend/dist`, or run Vite with
`API_PROXY_TARGET=http://127.0.0.1:8000`. On first start the administrator is
created from `LIMINAL_ADMIN_EMAIL` and `LIMINAL_ADMIN_PASSWORD`; without a
password a random one is written once to `data/initial-admin-password.txt`
(mode 0600).

On the Linux reference server, `docker compose --profile server up -d` adds
the backend and Ollama on an internal network with no route out.

## Pipeline stages

Each stage is a command run without a shell; `{audio}`, `{work}`,
`{session}`, `{type}`, `{date}` and `{start}` are filled in per argument.

| Variable | Default | Tool |
|---|---|---|
| `LIMINAL_ASR_CMD` | `python -m asr_llm.cli {audio} --skip-llm --out {work}/asr.json` | transcription, branch `samoilov-asr-llm` |
| `LIMINAL_DIARIZE_CMD` | `diarizer file {audio} --out {work}/diarization --plain` | speakers, branch `Coflazo-Branch` (`diarization/`) |
| `LIMINAL_MINUTES_CMD` | `mom report {work}/transcript.json --session {session} --type {type} --date {date} --start {start} --out {work}/minutes` | minutes, branch `Coflazo-Branch` (`minutes/`) |

`LIMINAL_<STAGE>_CWD` sets a stage's working folder; point each command at
its own virtual environment's Python. Transcription and diarization run side
by side; the backend unwraps the recogniser's JSON into
`{work}/transcript.json` for the minutes step. If diarization fails the
minutes still come out, without speaker owners. Stage output goes to
`data/meetings/<id>/logs/`, owner-only; no transcript text is logged.

A job that was running when the server stopped goes back to the queue on the
next start.

## Sending

- **Routing**: `routing.json` maps `medical`, `executive` and `administrative`
  to their distribution lists (`MOM_RECIPIENTS_<TYPE>` is the fallback).
  Callers never choose recipients.
- **Auto mode** (default): when processing ends with nothing left to confirm,
  the meeting waits `LIMINAL_SEND_WINDOW_S` (60 s) as `sending_soon`. Anyone
  can stop it, which turns it into a manual review.
- **Needs confirmation**: items the minutes checks could not confirm hold the
  meeting for a person. Editing the item, or
  `POST /api/meetings/{id}/confirmations/{factId}` with `{"action": "keep" | "remove"}`,
  settles it.
- **Delivery**: EmailService sends one mail to the list and a copy to each
  participant with an email, with the RO, RU and EN PDFs attached. A failed
  delivery keeps the minutes, sets `deliveryState: failed` with a reference,
  and never reports the meeting as sent. Repeated Send requests change nothing.
- **n8n** is optional: set `LIMINAL_N8N_WEBHOOK` to put a workflow in front;
  if it does not answer, the backend mails directly.

## Endpoints beyond the contract

- `GET /api/meetings/{id}/documents/{lang}.{pdf|docx}`: the minutes files
  (`lang` is `ro`, `ru` or `en`).
- `POST /api/meetings/{id}/confirmations/{factId}`: settle a flagged item.
- Meetings carry `processingStages`, `needsConfirmation`, `documents`,
  `deliveredVia` and `sendWindowSeconds` in addition to the contract fields.

## Security

| Area | What the server does |
|---|---|
| Network | `offline.block_outbound()` refuses every non-loopback connection in-process; compose publishes ports on 127.0.0.1 only; the service network is `internal` |
| Accounts | scrypt password hashes, generic login errors, 5 failures per account and address (20 per address) in 15 minutes |
| Sessions | random token in an HttpOnly, SameSite=Strict cookie (`Secure` with `LIMINAL_SECURE_COOKIES=1`), only its SHA-256 stored, 30 min idle, 12 h absolute |
| CSRF | state-changing `/api` requests need an Origin or Referer from this server or `LIMINAL_ALLOWED_ORIGINS` |
| Access | meetings visible to their creator and administrators; System and admin routes need the admin role |
| Uploads | streamed to a random name, type checked by its bytes, decoded by ffprobe (files only, no protocols), 500 MB and 3 h limits, stored 0600 |
| Files | documents are served only from the meeting's own minutes folder |
| Headers | CSP `default-src 'self'`, no framing, `nosniff`, `no-store` on the API |

`scripts/offline_check.sh` runs the network-blocked tests, checks that
compose binds loopback only and that the internal network has no route out,
and lists anything listening beyond loopback.

---

## Email service (Roman)

The email part sends meeting minutes for the configured meeting type. It
receives a structured `minutes` payload and sends it through SMTP.

## Workflow

1. The upstream pipeline sends a `minutes` object to `POST /email/send`.
2. The backend selects the configured recipient list for that meeting type.
3. It sends one email to the meeting distribution list and separate copies to unique participant addresses.
4. In local development, Mailpit captures the outgoing messages instead of delivering them externally.

## Requirements

- Python 3.14+
- `uv`
- Docker (for Mailpit)

## Configuration

Create or update `.env` in the backend directory:

```dotenv
SMTP_HOST=localhost
SMTP_PORT=1025
SMTP_FROM=mom-bot@hospital.local
SMTP_ALLOWED_HOSTS=localhost,127.0.0.1,::1,mailpit
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_STARTTLS=false

MOM_RECIPIENTS_MEDICAL=medical-board@hospital.local,admin-board@hospital.local
MOM_RECIPIENTS_EXECUTIVE=executive-board@hospital.local
MOM_RECIPIENTS_ADMINISTRATIVE=admin-board@hospital.local
```

Notes:

- `SMTP_HOST` must be loopback and included in `SMTP_ALLOWED_HOSTS`.
- The app blocks non-loopback outbound socket connections to keep local testing safe.
- The recipient lists are fixed per meeting type; callers do not choose the distribution list themselves.

## Run locally

From the backend directory:

```powershell
uv sync
docker compose up -d
uv run fastapi dev main.py
```

The API is available at:

- http://127.0.0.1:8000
- Swagger UI: http://127.0.0.1:8000/docs
- Mailpit UI: http://localhost:8025

## Example request

```json
{
  "minutes": {
    "title": "Cardiology Board",
    "meeting_type": "medical",
    "language": "ro",
    "summary": "Approve ICU protocol",
    "attendees": ["Dr. Popescu"],
    "decisions": ["Approve ICU protocol"],
    "action_items": [
      {
        "text": "Review the protocol",
        "owner": "Dr. Popescu",
        "deadline": "2026-10-05",
        "source_quote": "I will review it by October 5."
      }
    ]
  },
  "participant_emails": ["doctor@hospital.local", "nurse@hospital.local"]
}
```

## API behavior

The endpoint `POST /email/send` returns:

- `200` when all recipients accept the email
- `207` when only some recipients are refused
- `502` when delivery fails or all recipients are refused
- `503` when the meeting type has no configured recipients
- `422` when the payload is invalid

## Tests

Run the unit and API tests with:

```bash
uv run python -m pytest
```

The email tests use mocked SMTP; `tests/test_mail_roundtrip.py` sends a real
message with three PDFs to an in-process SMTP server on loopback.
`tests/test_liminal.py` runs the whole API with fake pipeline stages
(`tests/fake_stages/`): auth, CSRF, uploads, the queue and its restart
recovery, auto send, stop-send, confirmations, failed delivery and the
network guard.
