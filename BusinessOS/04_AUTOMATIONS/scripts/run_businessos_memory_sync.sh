#!/usr/bin/env bash
set -euo pipefail

WORKDIR="/home/yuiop/.hermes/hermes-agent"
LOG_DIR="/home/yuiop/.local/state/businessos/logs"
LOG_FILE="$LOG_DIR/memory-sync.log"

mkdir -p "$LOG_DIR"

cd "$WORKDIR"
exec "$WORKDIR/venv/bin/python" "$WORKDIR/BusinessOS/04_AUTOMATIONS/scripts/sync_businessos_memory.py" >> "$LOG_FILE" 2>&1
