#!/usr/bin/env bash
# Detect a missing or broken Hermes venv and rebuild it.
#
# Idempotent: a no-op if the venv is healthy.  Heals it if not.
# Intended to run from launchd or cron.  Logs to ~/.hermes/logs/venv-watchdog.log.
#
# Health = `<venv>/bin/python -c "import hermes_cli"` exits 0.

set -eu

VENV="$HOME/.hermes/hermes-agent/venv"
INSTALL_DIR="$HOME/.hermes/hermes-agent"
LOG_DIR="$HOME/.hermes/logs"
LOG="$LOG_DIR/venv-watchdog.log"
UV="$HOME/.local/bin/uv"

mkdir -p "$LOG_DIR"
ts() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
log() { echo "$(ts) $*" >> "$LOG"; }

# Health probe — if both pass, exit silently (no-op).
if [ -x "$VENV/bin/python" ] && "$VENV/bin/python" -c "import hermes_cli" >/dev/null 2>&1; then
    exit 0
fi

log "venv unhealthy or missing — starting rebuild"

if [ ! -x "$UV" ]; then
    log "ERROR: uv not found at $UV — cannot rebuild.  Install uv first."
    exit 1
fi

if [ ! -f "$INSTALL_DIR/pyproject.toml" ]; then
    log "ERROR: $INSTALL_DIR/pyproject.toml missing — install dir corrupted, manual recovery needed."
    exit 1
fi

# If a broken venv directory exists, blow it away before recreating.
if [ -d "$VENV" ]; then
    log "removing broken $VENV"
    rm -rf "$VENV"
fi

cd "$INSTALL_DIR"

log "creating fresh venv with Python 3.11"
if ! "$UV" venv venv --python 3.11 >> "$LOG" 2>&1; then
    log "ERROR: uv venv failed (see above)"
    exit 1
fi

log "installing hermes editable + all extras (may take ~1 minute)"
if ! VIRTUAL_ENV="$VENV" "$UV" pip install -e ".[all]" >> "$LOG" 2>&1; then
    log "ERROR: editable install failed"
    exit 1
fi

# Optional: supertonic (local TTS provider) — best effort, won't fail rebuild.
if ! VIRTUAL_ENV="$VENV" "$UV" pip install supertonic >> "$LOG" 2>&1; then
    log "WARN: supertonic install failed (TTS will fall back to other providers)"
fi

# Final health check
if "$VENV/bin/python" -c "import hermes_cli" >/dev/null 2>&1; then
    log "rebuild OK — hermes_cli importable"
    exit 0
else
    log "ERROR: rebuild completed but hermes_cli still not importable"
    exit 1
fi
