#!/bin/sh
# Simple entrypoint for Railway / single-process deployments.
# Replaces the s6-overlay supervision tree with a minimal bootstrap that:
#   1. Creates required data directories
#   2. Seeds .env and config.yaml from examples on first boot
#   3. Writes environment variables to .env so Hermes can read them
#   4. Activates the Python venv
#   5. Runs `hermes gateway` in server mode
#
# Environment variables consumed:
#   OPENROUTER_API_KEY   - OpenRouter API key (primary LLM provider)
#   OPENAI_API_KEY       - OpenAI API key (alternative LLM provider)
#   HERMES_MODEL         - Default model override (e.g. anthropic/claude-opus-4.6)
#   TELEGRAM_BOT_TOKEN   - Telegram bot token for the gateway adapter
#   HERMES_HOME          - Data directory (default: /opt/data)

set -eu

HERMES_HOME="${HERMES_HOME:-/opt/data}"
INSTALL_DIR="/opt/hermes"

echo "[entrypoint] Starting Hermes simple entrypoint"

# --- Create required data directories ---
mkdir -p \
    "$HERMES_HOME/cron" \
    "$HERMES_HOME/sessions" \
    "$HERMES_HOME/logs" \
    "$HERMES_HOME/hooks" \
    "$HERMES_HOME/memories" \
    "$HERMES_HOME/skills" \
    "$HERMES_HOME/skins" \
    "$HERMES_HOME/plans" \
    "$HERMES_HOME/workspace" \
    "$HERMES_HOME/home"

echo "[entrypoint] Directories created"

# --- Seed config files on first boot ---
if [ ! -f "$HERMES_HOME/.env" ] && [ -f "$INSTALL_DIR/.env.example" ]; then
    cp "$INSTALL_DIR/.env.example" "$HERMES_HOME/.env"
    echo "[entrypoint] Seeded .env from .env.example"
fi

if [ ! -f "$HERMES_HOME/config.yaml" ] && [ -f "$INSTALL_DIR/cli-config.yaml.example" ]; then
    cp "$INSTALL_DIR/cli-config.yaml.example" "$HERMES_HOME/config.yaml"
    echo "[entrypoint] Seeded config.yaml from cli-config.yaml.example"
fi

# --- Write environment variables to .env so Hermes can read them ---
# Hermes reads API keys from the .env file, not directly from the container
# environment. We append any non-empty env vars here so they take effect.
# Each key is written only if the variable is set and non-empty; existing
# lines for the same key are removed first to avoid duplicates on restart.
write_env_var() {
    key="$1"
    value="$2"
    if [ -n "$value" ]; then
        # Strip any existing line(s) for this key, then append the new value.
        if [ -f "$HERMES_HOME/.env" ]; then
            # Use a temp file to avoid in-place sed portability issues.
            grep -v "^${key}=" "$HERMES_HOME/.env" > "$HERMES_HOME/.env.tmp" || true
            mv "$HERMES_HOME/.env.tmp" "$HERMES_HOME/.env"
        fi
        printf '%s=%s\n' "$key" "$value" >> "$HERMES_HOME/.env"
        echo "[entrypoint] Wrote $key to .env"
    fi
}

write_env_var "OPENROUTER_API_KEY" "${OPENROUTER_API_KEY:-}"
write_env_var "OPENAI_API_KEY"     "${OPENAI_API_KEY:-}"
write_env_var "HERMES_MODEL"       "${HERMES_MODEL:-}"
write_env_var "TELEGRAM_BOT_TOKEN" "${TELEGRAM_BOT_TOKEN:-}"

# Restrict .env to owner-only access (contains secrets).
chmod 600 "$HERMES_HOME/.env" 2>/dev/null || true

# --- Activate the Python venv ---
# shellcheck disable=SC1091
. "$INSTALL_DIR/.venv/bin/activate"

echo "[entrypoint] Python venv activated"

# --- Change to the data directory and run hermes gateway ---
cd "$HERMES_HOME"

echo "[entrypoint] Launching hermes gateway"
exec hermes gateway
