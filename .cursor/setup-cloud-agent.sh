#!/usr/bin/env bash
# Cursor Cloud bootstrap for Hermes development/test sessions.
#
# Keep this focused on agent-readiness: install the repository's existing
# dev extra so scripts/run_tests.sh can run pytest-based tests immediately.

set -euo pipefail

ROOT="${1:-${CURSOR_WORKSPACE:-$(pwd)}}"
cd "$ROOT"

if command -v uv >/dev/null 2>&1; then
  uv sync --extra dev
  if [ -x "$ROOT/.venv/bin/hermes" ]; then
    "$ROOT/.venv/bin/hermes" --version
  else
    uv run hermes --version
  fi
  exit 0
fi

if [ ! -x "$ROOT/.venv/bin/python" ] && [ ! -x "$ROOT/venv/bin/python" ]; then
  ./setup-hermes.sh
fi

if [ -x "$ROOT/.venv/bin/python" ]; then
  SETUP_PYTHON="$ROOT/.venv/bin/python"
elif [ -x "$ROOT/venv/bin/python" ]; then
  SETUP_PYTHON="$ROOT/venv/bin/python"
else
  echo "error: no virtualenv found after setup" >&2
  exit 1
fi

"$SETUP_PYTHON" -m pip install -e ".[dev]"

VENV_BIN="$(dirname "$SETUP_PYTHON")"
if [ -x "$VENV_BIN/hermes" ]; then
  "$VENV_BIN/hermes" --version
else
  hermes --version
fi
