#!/usr/bin/env bash
# Open local firewall (ufw) for Hermes API + dashboard TCP ports.
# Defaults: API 8642, dashboard 9112 (matches docker-compose.yml in this repo).
# Override dashboard port: HERMES_DASHBOARD_PORT=9119 ./scripts/ufw_allow_hermes_ports.sh
set -euo pipefail

API_PORT="${HERMES_API_PORT:-8642}"
DASH_PORT="${HERMES_DASHBOARD_PORT:-9112}"

if ! command -v ufw >/dev/null 2>&1; then
  echo "ufw not found; install it or configure your firewall manually." >&2
  exit 1
fi

sudo ufw allow "${API_PORT}/tcp" comment "Hermes OpenAI-compatible API"
sudo ufw allow "${DASH_PORT}/tcp" comment "Hermes Web Dashboard"
echo "Allowed TCP ${API_PORT} (API) and ${DASH_PORT} (dashboard). Check: sudo ufw status"
