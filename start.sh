#!/bin/bash
set -e

echo "[start.sh] Initializing Hermes environment..."

# --- Set paths ---
export HOME=/data
export HERMES_HOME=/data/.hermes

# --- Create required directories ---
echo "[start.sh] Ensuring directory structure..."
mkdir -p "$HERMES_HOME"/{cron,sessions,logs,memories,skills,pairing,hooks,image_cache,audio_cache,workspace}

# --- Build .env file from Railway variables ---
echo "[start.sh] Writing environment variables to .env..."

ENV_FILE="$HERMES_HOME/.env"
> "$ENV_FILE"  # clear file every startup

# Only write variables if they exist (prevents empty values)
[ -n "$OPENAI_API_KEY" ] && echo "OPENAI_API_KEY=$OPENAI_API_KEY" >> "$ENV_FILE"
[ -n "$OPENROUTER_API_KEY" ] && echo "OPENROUTER_API_KEY=$OPENROUTER_API_KEY" >> "$ENV_FILE"
[ -n "$GOOGLE_API_KEY" ] && echo "GOOGLE_API_KEY=$GOOGLE_API_KEY" >> "$ENV_FILE"
[ -n "$TELEGRAM_BOT_TOKEN" ] && echo "TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN" >> "$ENV_FILE"
[ -n "$GH_TOKEN" ] && echo "GH_TOKEN=$GH_TOKEN" >> "$ENV_FILE"
[ -n "$GITHUB_TOKEN" ] && echo "GITHUB_TOKEN=$GITHUB_TOKEN" >> "$ENV_FILE"
[ -n "$TELEGRAM_ALLOWED_USERS" ] && echo "TELEGRAM_ALLOWED_USERS=$TELEGRAM_ALLOWED_USERS" >> "$ENV_FILE"

# --- Seed config.yaml if missing ---
if [ ! -f "$HERMES_HOME/config.yaml" ] && [ -f /opt/hermes-agent/cli-config.yaml.example ]; then
  echo "[start.sh] Seeding config.yaml from example"
  cp /opt/hermes-agent/cli-config.yaml.example "$HERMES_HOME/config.yaml"
fi

# --- Start application ---
echo "[start.sh] Starting admin server..."
exec python /app/server.py
