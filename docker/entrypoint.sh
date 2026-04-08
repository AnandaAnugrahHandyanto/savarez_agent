#!/bin/bash
# Docker entrypoint: bootstrap config and data dirs, then launch supervisord
# which manages: hermes gateway (API server), hermes-a2a, and filebrowser.
set -e

HERMES_HOME="/opt/data"
INSTALL_DIR="/opt/hermes"

# AGENT_PERSONA: matches a filename in docker/personas/ (e.g. "harry", "vader")
PERSONA="${AGENT_PERSONA:-default}"

# ── Directory structure ────────────────────────────────────────────────────
mkdir -p "$HERMES_HOME"/{cron,sessions,logs,hooks,memories,skills,files}

# ── .env ──────────────────────────────────────────────────────────────────
if [ ! -f "$HERMES_HOME/.env" ]; then
    cp "$INSTALL_DIR/.env.example" "$HERMES_HOME/.env"
fi

# ── config.yaml ───────────────────────────────────────────────────────────
if [ ! -f "$HERMES_HOME/config.yaml" ]; then
    cp "$INSTALL_DIR/docker/config.yaml" "$HERMES_HOME/config.yaml"
fi

# ── SOUL.md (character persona) ───────────────────────────────────────────
# Always re-apply the persona on each start so changes to SOUL files take
# effect without rebuilding the image. Remove the lock file to force refresh.
PERSONA_SRC="$INSTALL_DIR/docker/personas/${PERSONA}.md"
if [ -f "$PERSONA_SRC" ]; then
    cp "$PERSONA_SRC" "$HERMES_HOME/SOUL.md"
else
    cp "$INSTALL_DIR/docker/SOUL.md" "$HERMES_HOME/SOUL.md"
fi

# ── Sync bundled skills ────────────────────────────────────────────────────
if [ -d "$INSTALL_DIR/skills" ]; then
    python3 "$INSTALL_DIR/tools/skills_sync.py"
fi

# ── Filebrowser — first-run initialisation ─────────────────────────────────
# FB_PASSWORD env var sets the admin password (required — no default).
# FB_ADMIN_USER defaults to "admin".
FB_DB="$HERMES_HOME/filebrowser.db"
FB_USER="${FB_ADMIN_USER:-admin}"
FB_PASS="${FB_PASSWORD:?FB_PASSWORD env var is required}"

if [ ! -f "$FB_DB" ]; then
    echo "[entrypoint] Initialising filebrowser database..."
    filebrowser config init \
        --database "$FB_DB"
    filebrowser config set \
        --database "$FB_DB" \
        --address  0.0.0.0 \
        --port     8080 \
        --root     "$HERMES_HOME" \
        --log      "$HERMES_HOME/logs/filebrowser.log"
    filebrowser users add "$FB_USER" "$FB_PASS" \
        --perm.admin \
        --database "$FB_DB"
    echo "[entrypoint] Filebrowser initialised. Admin user: $FB_USER"
fi

# ── A2A env vars — forwarded to supervisord child processes ────────────────
# A2A_KEY must be set — supervisord reads it from the environment inherited
# by the a2a child process (set via docker-compose env).
if [ -z "${A2A_KEY}" ]; then
    echo "[entrypoint] WARNING: A2A_KEY is not set. A2A server will start UNAUTHENTICATED."
fi

# Pass AGENT_* vars into supervisord environment so child processes inherit them
export AGENT_NAME="${AGENT_NAME:-hermes-agent}"
export AGENT_DESCRIPTION="${AGENT_DESCRIPTION:-A Hermes agent}"
export AGENT_SKILLS="${AGENT_SKILLS:-general}"

echo "[entrypoint] Starting agent: ${AGENT_NAME} (persona: ${PERSONA})"

# ── Launch supervisord (manages all three processes) ───────────────────────
exec supervisord -c /etc/supervisor/conf.d/hermes.conf
