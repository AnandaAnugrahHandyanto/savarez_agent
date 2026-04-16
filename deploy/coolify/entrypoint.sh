#!/bin/bash
# Coolify wrapper around the upstream Hermes entrypoint.
#
# Responsibilities (as root, before privilege drop):
#   1. Require NEBIUS_API_KEY.
#   2. Render /opt/data/config.yaml from /opt/coolify/config.template.yaml,
#      substituting ${VAR} placeholders with environment values.
#   3. Seed /opt/data/.env with NEBIUS_API_KEY (chmod 600).
#   4. Hand off to /opt/hermes/docker/entrypoint.sh, which drops to the
#      `hermes` user and execs `hermes "$@"`.
#
# This file is bind-mounted read-only at runtime so you never have to rebuild
# the image to tweak deploy behavior — edit, commit, redeploy.
set -euo pipefail

HERMES_HOME="${HERMES_HOME:-/opt/data}"
TEMPLATE="/opt/coolify/config.template.yaml"
UPSTREAM_ENTRYPOINT="/opt/hermes/docker/entrypoint.sh"

log() { printf '[coolify] %s\n' "$*" >&2; }

render_config() {
    # Use python3 (already in the image) for safe ${VAR} substitution —
    # no reliance on envsubst, no shell quoting traps on API keys.
    TEMPLATE="$TEMPLATE" python3 - <<'PY'
import os, string, pathlib, sys
tmpl = string.Template(pathlib.Path(os.environ["TEMPLATE"]).read_text())
sys.stdout.write(tmpl.safe_substitute(os.environ))
PY
}

if [ "$(id -u)" = "0" ]; then
    mkdir -p "$HERMES_HOME"

    if [ -z "${NEBIUS_API_KEY:-}" ]; then
        log "ERROR: NEBIUS_API_KEY is not set. Add it as a secret in Coolify."
        exit 1
    fi

    # Defaults — safe to re-evaluate at every boot.
    export NEBIUS_BASE_URL="${NEBIUS_BASE_URL:-https://api.studio.nebius.com/v1}"
    export HERMES_PRIMARY_MODEL="${HERMES_PRIMARY_MODEL:-Qwen/Qwen3-Coder-480B-A35B-Instruct}"
    export HERMES_FALLBACK_MODEL="${HERMES_FALLBACK_MODEL:-deepseek-ai/DeepSeek-V3}"

    uid="${HERMES_UID:-$(id -u hermes 2>/dev/null || echo 10000)}"
    gid="${HERMES_GID:-$(id -g hermes 2>/dev/null || echo 10000)}"

    config="$HERMES_HOME/config.yaml"
    if [ ! -f "$config" ] || [ "${HERMES_FORCE_CONFIG_REWRITE:-0}" = "1" ]; then
        log "rendering $config from template"
        tmp="$(mktemp)"
        render_config > "$tmp"
        install -m 0600 -o "$uid" -g "$gid" "$tmp" "$config"
        rm -f "$tmp"
    else
        log "keeping existing $config (set HERMES_FORCE_CONFIG_REWRITE=1 to regenerate)"
    fi

    # Keep NEBIUS_API_KEY in ~/.hermes/.env in sync with the env var so that
    # interactive `docker exec` sessions still work without re-exporting it.
    envfile="$HERMES_HOME/.env"
    [ -f "$envfile" ] || install -m 0600 -o "$uid" -g "$gid" /dev/null "$envfile"
    tmp="$(mktemp)"
    grep -v '^NEBIUS_API_KEY=' "$envfile" > "$tmp" || true
    printf 'NEBIUS_API_KEY=%s\n' "$NEBIUS_API_KEY" >> "$tmp"
    install -m 0600 -o "$uid" -g "$gid" "$tmp" "$envfile"
    rm -f "$tmp"
fi

exec "$UPSTREAM_ENTRYPOINT" "$@"
