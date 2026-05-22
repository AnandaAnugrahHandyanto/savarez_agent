#!/bin/bash
set -e

HERMES_HOME="${HERMES_HOME:-/opt/data}"
INSTALL_DIR="/opt/hermes"
DASHBOARD_PORT=9119

# --- Privilege drop ---
if [ "$(id -u)" = "0" ]; then
    if [ -n "$HERMES_UID" ] && [ "$HERMES_UID" != "$(id -u hermes)" ]; then
        usermod -u "$HERMES_UID" hermes
    fi
    if [ -n "$HERMES_GID" ] && [ "$HERMES_GID" != "$(id -g hermes)" ]; then
        groupmod -o -g "$HERMES_GID" hermes 2>/dev/null || true
    fi

    # Fix ownership
    chown -R hermes:hermes "$HERMES_HOME" 2>/dev/null || true
    chown -R hermes:hermes "$INSTALL_DIR/.venv" 2>/dev/null || true

    echo "Dropping root privileges"
    exec gosu hermes "$0" "$@"
fi

# --- Running as hermes ---
source "${INSTALL_DIR}/.venv/bin/activate"

# Bootstrap directories and config
mkdir -p "$HERMES_HOME"/{cron,sessions,logs,hooks,memories,skills,skins,plans,workspace,home}
[ ! -f "$HERMES_HOME/.env" ] && cp "$INSTALL_DIR/.env.example" "$HERMES_HOME/.env"
[ ! -f "$HERMES_HOME/config.yaml" ] && cp "$INSTALL_DIR/cli-config.yaml.example" "$HERMES_HOME/config.yaml"
[ ! -f "$HERMES_HOME/SOUL.md" ] && cp "$INSTALL_DIR/docker/SOUL.md" "$HERMES_HOME/SOUL.md"

# Sync bundled skills
if [ -d "$INSTALL_DIR/skills" ]; then
    python3 "$INSTALL_DIR/tools/skills_sync.py"
fi

echo "═══════════════════════════════════════════════════════════"
echo "Hermes Agent (Robust) - Dashboard: $DASHBOARD_PORT"
echo "═══════════════════════════════════════════════════════════"

# Start Gateway in background
hermes gateway run > "$HERMES_HOME/logs/gateway.log" 2>&1 &

# Start Dashboard (foreground)
exec hermes dashboard \
    --host 0.0.0.0 \
    --port $DASHBOARD_PORT \
    --insecure \
    --no-open