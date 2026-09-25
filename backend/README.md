# Backend Email Service

This backend emails structured Minutes of Meeting (MoM) produced by the local ASR/LLM pipeline. It does not run transcription or summarization itself.

## Workflow at a Glance

1. The ASR/LLM pipeline creates a `minutes` object containing the meeting type, summary, decisions, attendees, and action items.
2. A caller sends that object to `POST /email/send`.
3. The backend selects the distribution list configured for that meeting type. Recipients are not supplied by the caller.
4. The email service creates plain-text and HTML versions and sends them through SMTP.
5. In local development, Mailpit captures the email so it can be checked without delivering it to real people.

The API follows the team's loopback-only offline safeguard: connections to non-loopback network addresses are blocked. This allows Mailpit on `localhost`, but also blocks a separately hosted SMTP server.

## Requirements

- Python 3.14 or newer
- `uv`
- Docker, for the Mailpit smoke test

## Setup and Configuration

Run these commands from this `backend` directory. Copy the example only if `.env` does not already exist:

```powershell
Copy-Item .env.example .env
uv sync
```

Edit `.env` with your local settings. It is ignored by Git; share safe defaults by editing `.env.example`, never by committing `.env`. Shell environment variables override `.env`, and settings are read when the API starts. Use a clean terminal if old shell variables might override the file, and restart the API after changing settings.

Mailpit configuration and dummy distribution lists:

```dotenv
SMTP_HOST=localhost
SMTP_PORT=1025
SMTP_FROM=mom-bot@hospital.local
SMTP_ALLOWED_HOSTS=localhost,127.0.0.1,::1
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_STARTTLS=false

MOM_RECIPIENTS_MEDICAL=medical-board@hospital.local,admin-board@hospital.local
MOM_RECIPIENTS_EXECUTIVE=executive-board@hospital.local
MOM_RECIPIENTS_ADMINISTRATIVE=admin-board@hospital.local
```

`SMTP_HOST` must be a loopback host and listed in `SMTP_ALLOWED_HOSTS`. The socket guard blocks non-loopback addresses even if added to that list. To use an SMTP server on another internal machine, replace this policy with a narrowly scoped internal-network rule; do not allow a public mail host.

## Run Mailpit and the API

From this `backend` directory, start Mailpit with Compose:

```powershell
docker compose up -d
```

The Compose service pins the Mailpit image and publishes SMTP and web UI ports only on `127.0.0.1`. Open `http://localhost:8025` to view captured messages. To follow Mailpit logs, run `docker compose logs -f mailpit`; to stop it, run `docker compose down`.

If the older container named `mailpit` is still using ports 1025 and 8025, stop it before starting Compose:

```powershell
docker stop mailpit
docker compose up -d
```

Compose will not stop or remove that existing container automatically. In another terminal, from `backend`, start the API:

```powershell
uv run fastapi dev main.py
```

The API runs at `http://127.0.0.1:8000`. Swagger UI is at `http://127.0.0.1:8000/docs`; ReDoc is at `http://127.0.0.1:8000/redoc`.

## Send a Test MoM

In Swagger, expand `POST /email/send`, choose **Try it out**, paste a request body, and execute it. The body must contain the pipeline's `minutes` object, for example:

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
  }
}
```

The endpoint returns `sent` when all recipients are accepted, HTTP 207 with `partial` when some are refused, HTTP 502 when delivery fails or all are refused, and HTTP 503 when the meeting type has no configured recipients. Refresh Mailpit to inspect the captured message.

## Tests

Run unit and API tests. These use a mocked SMTP server, so they do not require Docker:

```powershell
uv run python -m unittest discover -s tests -p "test_*.py" -v
```

For a live local delivery test, start Mailpit and the API first. In another PowerShell terminal, run the smoke script with exactly the same dummy medical recipients configured in the API's `.env`:

```powershell
.\test_mailpit_smoke.ps1 -ExpectedRecipients @(
		"medical-board@hospital.local",
		"admin-board@hospital.local"
)
```

The script submits uniquely named dummy minutes and verifies the API response, Mailpit recipient list, and text and HTML bodies. It uses no external mail service or patient data.
