#!/bin/bash
# Deploy Nash AI to VPS for the first time
# Usage: ./nash-config/setup-vps.sh <VPS_IP>
# Requires: root SSH access, Tailscale up
set -euo pipefail

VPS_IP="${1:?VPS IP required (e.g. 100.86.15.64)}"
VPS_USER="root"
REMOTE_DIR="/opt/projects/nash-ai"
HERMES_HOME="/root/.hermes"

echo "==> [1/6] Checking connectivity..."
ssh -o ConnectTimeout=5 "${VPS_USER}@${VPS_IP}" "echo OK" || { echo "Cannot reach VPS"; exit 1; }

echo "==> [2/6] Cloning nash-ai to VPS..."
ssh "${VPS_USER}@${VPS_IP}" bash <<'REMOTE'
set -euo pipefail
if [ -d /opt/projects/nash-ai/.git ]; then
  echo "Already cloned — pulling latest"
  cd /opt/projects/nash-ai && git pull
  exit 0
fi
mkdir -p /opt/projects
git clone https://github.com/93michaelnash/nash-ai.git /opt/projects/nash-ai
REMOTE

echo "==> [3/6] Creating Python venv and installing dependencies..."
ssh "${VPS_USER}@${VPS_IP}" bash <<'REMOTE'
set -euo pipefail
cd /opt/projects/nash-ai
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -e ".[messaging,cron,mcp]"
REMOTE

echo "==> [4/6] Copying config files..."
ssh "${VPS_USER}@${VPS_IP}" "mkdir -p ${HERMES_HOME}"
scp nash-config/config.yaml "${VPS_USER}@${VPS_IP}:${HERMES_HOME}/config.yaml"
# .env must exist — copy from .env.example if not already there
ssh "${VPS_USER}@${VPS_IP}" "test -f ${HERMES_HOME}/.env && echo '.env exists' || (cp ${REMOTE_DIR}/nash-config/.env.example ${HERMES_HOME}/.env && echo 'Created .env from example — FILL IN YOUR SECRETS')"

echo "==> [5/6] Installing systemd service..."
scp nash-config/nash.service "${VPS_USER}@${VPS_IP}:/etc/systemd/system/nash.service"
ssh "${VPS_USER}@${VPS_IP}" "systemctl daemon-reload && systemctl enable nash"

echo ""
echo "==> Setup complete."
echo ""
echo "  NEXT STEP: Fill in secrets on VPS:"
echo "    ssh ${VPS_USER}@${VPS_IP} 'nano ${HERMES_HOME}/.env'"
echo ""
echo "  Required secrets:"
echo "    TELEGRAM_BOT_TOKEN   — from @BotFather"
echo "    TELEGRAM_ALLOWED_USERS — your numeric Telegram user ID (get via @userinfobot)"
echo "    TELEGRAM_HOME_CHANNEL  — chat ID for cron messages"
echo "    GROQ_API_KEY           — from console.groq.com/keys (free)"
echo "    ANTHROPIC_API_KEY      — from console.anthropic.com (Prism reads this)"
echo ""
echo "  Then start the daemon:"
echo "    ssh ${VPS_USER}@${VPS_IP} 'systemctl start nash && journalctl -u nash -f'"
