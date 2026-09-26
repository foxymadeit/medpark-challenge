#!/usr/bin/env bash
# Proves Liminal keeps everything on this machine:
#   1. the test suite runs with every non-loopback connection refused in-process;
#   2. compose publishes ports on 127.0.0.1 only and the service network has no route out;
#   3. whatever is listening right now on Liminal's ports is bound to loopback.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "1/3 tests with outbound connections blocked"
uv run python -m pytest -q tests/test_offline.py tests/test_liminal.py -k "offline or outbound or nothing_leaves or full_flow"

echo "2/3 compose: loopback ports, internal network"
docker compose --profile server config --format json | python3 -c '
import json, sys
c = json.load(sys.stdin)
bad = [name + ":" + str(p.get("published")) for name, s in c["services"].items()
       for p in s.get("ports", []) if p.get("host_ip") not in ("127.0.0.1", "::1")]
assert not bad, f"ports open beyond this machine: {bad}"
assert c["networks"]["internal"].get("internal") is True, "the internal network can reach out"
env = c["services"].get("n8n", {}).get("environment", {})
calls_home = [k for k in ("N8N_DIAGNOSTICS_ENABLED", "N8N_VERSION_NOTIFICATIONS_ENABLED", "N8N_TEMPLATES_ENABLED",
                          "N8N_PERSONALIZATION_ENABLED", "N8N_COMMUNITY_PACKAGES_ENABLED") if env and env.get(k) != "false"]
assert not calls_home, f"n8n would call its servers: {calls_home}"
print("   ok: every port on 127.0.0.1; internal network has no route out; n8n telemetry, updates and templates off")'

echo "3/3 listening sockets on Liminal ports"
if command -v lsof >/dev/null; then
  open=$(lsof -nP -iTCP -sTCP:LISTEN 2>/dev/null | awk '$9 ~ /:(8000|1025|8025|11434)$/ && $9 !~ /^(127\.0\.0\.1|\[::1\]|localhost):/ {print $1, $9}' || true)
  if [ -n "$open" ]; then echo "   listening beyond loopback:"; echo "$open"; exit 1; fi
fi
echo "   ok"
echo "offline check passed"
