#!/bin/bash
set -e

export HOME=/data
export HERMES_HOME=/data/.hermes

echo "[start] preparing..."

mkdir -p "$HERMES_HOME"

# --- required env ---
if [ -z "$GOOGLE_API_KEY" ]; then
  echo "[ERROR] GOOGLE_API_KEY missing"
  exit 1
fi

# --- write env ---
ENV_FILE="$HERMES_HOME/.env"
: > "$ENV_FILE"

echo "GOOGLE_API_KEY=$GOOGLE_API_KEY" >> "$ENV_FILE"
[ -n "$TELEGRAM_BOT_TOKEN" ] && echo "TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN" >> "$ENV_FILE"
[ -n "$TELEGRAM_ALLOWED_USERS" ] && echo "TELEGRAM_ALLOWED_USERS=$TELEGRAM_ALLOWED_USERS" >> "$ENV_FILE"

# --- config ---
cat <<EOF > "$HERMES_HOME/config.yaml"
model:
  provider: gemini
  default: gemini-1.5-flash
EOF

echo "[start] launching server..."
exec python /app/server.py
``
