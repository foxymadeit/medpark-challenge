#!/bin/sh
# Starts the real Liminal backend (branch romans-branch) for the e2e test,
# with the backend's own fake pipeline stages and a local SMTP catcher.
#   E2E_BACKEND=/path/to/backend E2E_PYTHON=/path/to/venv/bin/python npm run e2e
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
FRONTEND=$(cd "$HERE/../.." && pwd)
B=${E2E_BACKEND:?set E2E_BACKEND to the backend folder}
PY=${E2E_PYTHON:-python3}
DATA=${E2E_DATA:-/tmp/liminal-e2e-data}
rm -rf "$DATA" "${MAIL_DIR:-/tmp/liminal-mail}"
FAKE="$B/tests/fake_stages"

export LIMINAL_DATA="$DATA"
export LIMINAL_ADMIN_EMAIL=admin@medpark.local
export LIMINAL_ADMIN_PASSWORD="correct horse battery"
export LIMINAL_FRONTEND_DIST="$FRONTEND/dist"
export LIMINAL_SEND_WINDOW_S=10 LIMINAL_AUTO_MODE=1
export LIMINAL_ALLOWED_ORIGINS=http://127.0.0.1:8000
export LIMINAL_ASR_CMD="$PY $FAKE/asr.py {audio} {work}"
export LIMINAL_DIARIZE_CMD="$PY $FAKE/diarize.py {audio} {work}"
export E2E_FAKE_MINUTES="$FAKE/minutes.py"
export LIMINAL_MINUTES_CMD="$PY $HERE/fake-minutes.py {work}/transcript.json --session {session} --type {type} --out {work}/minutes"
export SMTP_HOST=127.0.0.1 SMTP_PORT=1025 SMTP_FROM=mom-bot@hospital.local
export SMTP_ALLOWED_HOSTS=localhost,127.0.0.1 SMTP_STARTTLS=false SMTP_USERNAME= SMTP_PASSWORD=
export MOM_RECIPIENTS_MEDICAL=medical-board@hospital.local
export MOM_RECIPIENTS_EXECUTIVE=executive-board@hospital.local
export MOM_RECIPIENTS_ADMINISTRATIVE=admin-board@hospital.local

python3 "$HERE/smtp-sink.py" &
cd "$B"
exec "$PY" -m uvicorn main:app --host 127.0.0.1 --port 8000
