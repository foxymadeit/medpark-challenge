#!/usr/bin/env bash
# Loads Liminal's routing workflow and the mail-server credential into the
# self-hosted n8n from compose.yaml, and switches the workflow on.
#   docker compose up -d mailpit n8n && bash n8n/setup.sh
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose cp n8n/liminal-routing.json n8n:/tmp/liminal-routing.json
docker compose cp n8n/smtp-credential.json n8n:/tmp/smtp-credential.json
docker compose exec -T n8n n8n import:credentials --input=/tmp/smtp-credential.json
docker compose exec -T n8n n8n import:workflow --input=/tmp/liminal-routing.json
docker compose exec -T n8n sh -c 'n8n publish:workflow --id=liminalRouting01 2>/dev/null || n8n update:workflow --id=liminalRouting01 --active=true'
docker compose restart n8n   # activation takes effect on start
echo "n8n ready: editor http://127.0.0.1:5678, webhook http://127.0.0.1:5678/webhook/liminal-minutes"
echo "point the backend at it: LIMINAL_N8N_WEBHOOK=http://127.0.0.1:5678/webhook/liminal-minutes"
