#!/bin/bash
set -e

echo "[start.sh] Initializing Hermes environment..."

# --- Set core paths ---
export HOME=/data
export HERMES_HOME=/data/.hermes

# --- Validate required env ---
if [ -z "$GOOGLE_API_KEY" ]; then
  echo "[ERROR] GOOGLE_API_KEY is missing"
  exit 1
fi

# --- Prepare directory structure ---
echo "[start.sh] Ensuring directory structure..."
mkdir -p "$HERMES_HOME"/{cron,sessions,logs,memories,skills,pairing,hooks,image_cache,audio_cache,workspace}

# --- Build .env ---
echo "[start.sh] Writing .env..."

ENV_FILE="$HERMES_HOME/.env"
: > "$ENV_FILE"   # safely clear file

echo "GOOGLE_API_KEY=$GOOGLE_API_KEY" >> "$ENV_FILE"

# Messaging
[ -n "$TELEGRAM_BOT_TOKEN" ] && echo "TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN" >> "$ENV_FILE"
[ -n "$TELEGRAM_ALLOWED_USERS" ] && echo "TELEGRAM_ALLOWED_USERS=$TELEGRAM_ALLOWED_USERS" >> "$ENV_FILE"

# Optional integrations
[ -n "$GH_TOKEN" ] && echo "GH_TOKEN=$GH_TOKEN" >> "$ENV_FILE"
[ -n "$GITHUB_TOKEN" ] && echo "GITHUB_TOKEN=$GITHUB_TOKEN" >> "$ENV_FILE"

# --- Write config.yaml (deterministic model setup) ---
echo "[start.sh] Writing config.yaml..."

cat <<EOF > "$HERMES_HOME/config.yaml"
model:
  provider: gemini
  default: gemini-1.5-flash
EOF

# --- Minimal debug (SAFE: no secrets printed) ---
echo "[debug] ===== CONFIG ====="
cat "$HERMES_HOME/config.yaml" || true

echo "[debug] ===== HERMES CHECK ====="
hermes config check || echo "[debug] config check failed"

# --- Optional: background LLM smoke test (non-blocking) ---
echo "[debug] ===== LLM TEST (background) ====="
(hermes chat -z "Say hello briefly" || echo "[debug] LLM test failed") &

# --- Start server (MUST be last, non-blocking) ---
echo "[start.sh] Starting HTTP server..."
exec python /app/server.py
