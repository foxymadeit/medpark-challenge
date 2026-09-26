# Backend Email Service

This backend sends meeting minutes as emails for the configured meeting type. It does not perform transcription or summarization; it receives a structured `minutes` payload and sends it through SMTP.

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

```powershell
uv run python -m unittest discover -s tests -p "test_*.py" -v
```

This suite uses mocked SMTP and does not require a live mail server.
