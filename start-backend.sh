#!/usr/bin/env bash
# Hermes OpenAI-compatible API + messaging gateway (reads ~/.hermes/.env).
# Default API bind: set API_SERVER_HOST / API_SERVER_PORT / API_SERVER_KEY there.
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
exec hermes gateway run "$@"
