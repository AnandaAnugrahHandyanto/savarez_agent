#!/usr/bin/env bash
set -euo pipefail
cd /root/.hermes/hermes-agent
export PYTHONPATH=/root/.hermes/hermes-agent
exec python3 scripts/codex_queue_runner.py "$@"
