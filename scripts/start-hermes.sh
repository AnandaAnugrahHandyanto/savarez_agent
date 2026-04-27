#!/usr/bin/env bash

set -e

PROJECT_ROOT="/home/andrey/dev/hermes-agent"
WEB_ROOT="/home/andrey/dev/hermes-agent/web"
BACKEND_PORT=9119
FRONTEND_PORT=3001
HERMES_TOKEN="${HERMES_SESSION_TOKEN:-dev-hermes-token-arkeon}"

echo "Starting Hermes..."

# Validate paths
if [[ "$WEB_ROOT" == *"/HermesWeb"* ]]; then
  echo "ERROR: WEB_ROOT points to old HermesWeb directory"
  exit 1
fi

if [[ ! -f "$WEB_ROOT/src/features/code/CodeCockpitPage.tsx" ]]; then
  echo "ERROR: CodeCockpitPage.tsx not found in $WEB_ROOT"
  exit 1
fi

# Clear logs
: > /tmp/hermes-backend.log
: > /tmp/hermes-frontend.log

# Kill old processes on ports
echo "  [0/3] Cleaning up old processes..."
lsof -ti:$BACKEND_PORT 2>/dev/null | xargs -r kill -9 2>/dev/null || true
lsof -ti:$FRONTEND_PORT 2>/dev/null | xargs -r kill -9 2>/dev/null || true
sleep 1

# ── Backend ──────────────────────────────────────────────────────────────────
cd "$PROJECT_ROOT"
source .venv/bin/activate

echo "  [1/3] Backend (port $BACKEND_PORT)..."
HERMES_SESSION_TOKEN="$HERMES_TOKEN" \
nohup python -m uvicorn hermes_cli.web_server:app \
  --host 127.0.0.1 \
  --port "$BACKEND_PORT" \
  --reload > /tmp/hermes-backend.log 2>&1 &

# Healthcheck backend with retry (up to 20s)
echo "       Waiting for backend..."
backend_ok=0
for i in $(seq 1 20); do
  if curl -fsS "http://127.0.0.1:$BACKEND_PORT/api/status" > /dev/null 2>&1; then
    echo "       Backend OK (${i}s)"
    backend_ok=1
    break
  fi
  if [ "$i" -eq 20 ]; then
    echo "       Backend failed to start — check /tmp/hermes-backend.log"
    tail -n 20 /tmp/hermes-backend.log
    exit 1
  fi
  sleep 1
done

# Validate Code Mode endpoints
echo "       Validating Code Mode..."
if ! curl -fsS "http://127.0.0.1:$BACKEND_PORT/api/code/skills" > /dev/null 2>&1; then
  echo "       Warning: /api/code/skills not responding"
fi

# ── Frontend ─────────────────────────────────────────────────────────────────
cd "$WEB_ROOT"

echo "  [2/3] Frontend (port $FRONTEND_PORT)..."
nohup npm run dev -- --port "$FRONTEND_PORT" > /tmp/hermes-frontend.log 2>&1 &

# Healthcheck frontend with retry (up to 20s)
echo "       Waiting for frontend..."
frontend_ok=0
for i in $(seq 1 20); do
  if curl -fsS "http://127.0.0.1:$FRONTEND_PORT" > /dev/null 2>&1; then
    echo "       Frontend OK (${i}s)"
    frontend_ok=1
    break
  fi
  if [ "$i" -eq 20 ]; then
    echo "       Frontend failed to start — check /tmp/hermes-frontend.log"
    tail -n 20 /tmp/hermes-frontend.log
    exit 1
  fi
  sleep 1
done

echo "  [3/3] Validation complete"
echo ""
echo "System ready:"
echo "  Code        : http://localhost:$FRONTEND_PORT/code"
echo "  Frontend    : http://localhost:$FRONTEND_PORT"
echo "  Backend     : http://localhost:$BACKEND_PORT"
echo "  Status      : http://localhost:$BACKEND_PORT/api/status"
echo "  Skills      : http://localhost:$BACKEND_PORT/api/code/skills"
echo ""
echo "Logs:"
echo "  tail -f /tmp/hermes-backend.log"
echo "  tail -f /tmp/hermes-frontend.log"
echo ""
echo "Stop: hermes-down"
