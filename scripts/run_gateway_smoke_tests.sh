#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

VENV_DIR=""
for candidate in ".venv" "venv"; do
  if [[ -f "$candidate/bin/activate" ]]; then
    VENV_DIR="$candidate"
    break
  fi
done

if [[ -n "$VENV_DIR" ]]; then
  # Reuse the local project venv when available.
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
fi

PYTHON_BIN=""
if [[ -n "${VIRTUAL_ENV:-}" && -x "${VIRTUAL_ENV}/bin/python" ]]; then
  PYTHON_BIN="${VIRTUAL_ENV}/bin/python"
elif [[ -n "$VENV_DIR" && -x "$VENV_DIR/bin/python" ]]; then
  PYTHON_BIN="$VENV_DIR/bin/python"
else
  PYTHON_BIN="$(command -v python3)"
fi

"$PYTHON_BIN" -m pytest \
  tests/agent/test_auxiliary_client.py \
  tests/agent/test_error_classifier.py \
  tests/hermes_cli/test_gateway.py \
  tests/hermes_cli/test_gateway_service.py \
  tests/hermes_cli/test_gateway_wsl.py \
  tests/gateway/test_session.py \
  tests/gateway/test_telegram_*.py \
  --tb=short \
  -n0 \
  -q
