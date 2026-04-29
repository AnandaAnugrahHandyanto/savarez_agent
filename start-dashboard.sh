#!/usr/bin/env bash
# Hermes web dashboard (FastAPI / static UI).
# Override with env: HERMES_DASHBOARD_HOST, HERMES_DASHBOARD_PORT.
# Non-loopback bind requires --insecure (set HERMES_DASHBOARD_INSECURE=1).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
if [[ -f .venv/bin/activate ]]; then
  # shellcheck source=/dev/null
  source .venv/bin/activate
elif [[ -f venv/bin/activate ]]; then
  # shellcheck source=/dev/null
  source venv/bin/activate
fi

HOST="${HERMES_DASHBOARD_HOST:-127.0.0.1}"
PORT="${HERMES_DASHBOARD_PORT:-9112}"
NO_OPEN="${HERMES_DASHBOARD_NO_OPEN:-0}"

args=(--host "$HOST" --port "$PORT")
if [[ "$NO_OPEN" == "1" ]]; then
  args+=(--no-open)
fi

if [[ "$HOST" != "127.0.0.1" && "$HOST" != "localhost" && "$HOST" != "::1" ]]; then
  if [[ "${HERMES_DASHBOARD_INSECURE:-0}" != "1" ]]; then
    echo "Binding to ${HOST} requires HERMES_DASHBOARD_INSECURE=1 (dashboard has no robust remote auth)." >&2
    exit 1
  fi
  args+=(--insecure)
fi

exec hermes dashboard "${args[@]}" "$@"
