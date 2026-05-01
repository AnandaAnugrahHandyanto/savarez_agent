#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
python -m pip install -q -e ".[all,dev]"
python -m pytest -q \
  tests/test_openclaw_multi_agent_team_e2e.py \
  tests/test_hermes_team_registry_api.py \
  tests/test_hermes_team_audit_diff.py \
  tests/tools/test_delegate.py \
  tests/agent/test_memory_provider.py
