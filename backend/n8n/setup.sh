#!/usr/bin/env bash
# Loads Liminal's routing workflow into the self-hosted n8n and switches it on.
#   bash n8n/setup.sh          (from backend/; starts gateway, Mailpit and n8n)
# The first run writes two random secrets to backend/.env (mode 0600):
# N8N_ENCRYPTION_KEY, which encrypts the credentials n8n stores, and
# LIMINAL_N8N_SECRET, the header the backend must send to the webhook.
set -euo pipefail
cd "$(dirname "$0")/.."
touch .env && chmod 600 .env
grep -q '^N8N_ENCRYPTION_KEY=' .env || echo "N8N_ENCRYPTION_KEY=$(openssl rand -hex 32)" >> .env
grep -q '^LIMINAL_N8N_SECRET=' .env || echo "LIMINAL_N8N_SECRET=$(openssl rand -hex 24)" >> .env
secret=$(grep '^LIMINAL_N8N_SECRET=' .env | cut -d= -f2-)
docker compose up -d gateway mailpit n8n
until curl -sf http://127.0.0.1:5678/healthz >/dev/null; do sleep 2; done
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
python3 - "$secret" > "$tmp/credentials.json" <<'PY'
import json, sys
creds = json.load(open("n8n/smtp-credential.json"))
creds.append({"id": "liminalWebhook01", "name": "Liminal backend secret", "type": "httpHeaderAuth",
              "data": {"name": "X-Liminal-Secret", "value": sys.argv[1]}})
print(json.dumps(creds))
PY
docker compose cp "$tmp/credentials.json" n8n:/tmp/credentials.json
docker compose cp n8n/liminal-routing.json n8n:/tmp/liminal-routing.json
docker compose exec -T n8n n8n import:credentials --input=/tmp/credentials.json
docker compose exec -T -u root n8n rm -f /tmp/credentials.json   # the secret must not stay in the container
docker compose exec -T n8n n8n import:workflow --input=/tmp/liminal-routing.json
docker compose exec -T n8n sh -c 'n8n publish:workflow --id=liminalRouting01 2>/dev/null || n8n update:workflow --id=liminalRouting01 --active=true'
docker compose restart n8n   # activation takes effect on start
echo "n8n ready: editor http://127.0.0.1:5678, webhook http://127.0.0.1:5678/webhook/liminal-minutes"
echo "backend: LIMINAL_N8N_WEBHOOK=http://127.0.0.1:5678/webhook/liminal-minutes (LIMINAL_N8N_SECRET is in .env)"
