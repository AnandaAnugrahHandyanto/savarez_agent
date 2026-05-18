#!/usr/bin/env bash
set -euo pipefail

AGENT_REPO="${AGENT_REPO:-/Users/preston/.hermes/hermes-agent}"
HERMES_SRC="${HERMES_SRC:-$AGENT_REPO}"
BOT_REPO="${BOT_REPO:-/Users/preston/robinhood/crypto_bot}"
PROFILE_NAME="${PROFILE_NAME:-crypto-bot-pm}"
export HERMES_SRC BOT_REPO PROFILE_NAME AGENT_REPO

required() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1"
    exit 1
  }
}

required git
required python3
required hermes

if [[ ! -d "$HERMES_SRC/.git" ]]; then
  echo "Missing active Hermes git checkout: $HERMES_SRC"
  exit 1
fi

if [[ ! -d "$BOT_REPO/.git" ]]; then
  echo "Missing crypto_bot git checkout: $BOT_REPO"
  exit 1
fi

if [[ ! -x "$AGENT_REPO/scripts/setup_crypto_bot_pm_profile.sh" ]]; then
  echo "Missing setup helper: $AGENT_REPO/scripts/setup_crypto_bot_pm_profile.sh"
  exit 1
fi

missing=0

required_hermes_paths=(
  "plugins/crypto-bot-pm/plugin.yaml"
  "plugins/crypto-bot-pm/__init__.py"
  "plugins/crypto-bot-pm/tools.py"
  "plugins/crypto-bot-pm/schemas.py"
  "plugins/crypto-bot-pm/scripts/hermes_pm/hermes_pm_status.py"
  "plugins/crypto-bot-pm/scripts/hermes_pm/generate_development_workstream_packet.py"
  "plugins/crypto-bot-pm/scripts/hermes_pm/generate_development_slice_packet.py"
  "skills/project-management/crypto-bot-pm/SKILL.md"
  "skills/development/codex-sidecar/SKILL.md"
  "projects/crypto_bot/crypto_bot.project.yaml"
  "tools/install_user_assets.py"
  "tools/runtime_asset_parity.py"
  "tools/crypto_bot_control_plane_self_check.py"
  "tools/crypto_bot_autonomy_readiness.py"
)

for rel in "${required_hermes_paths[@]}"; do
  if [[ ! -e "$HERMES_SRC/$rel" ]]; then
    echo "Missing active Hermes control-plane asset: $HERMES_SRC/$rel"
    missing=1
  fi
done

if [[ "$missing" -ne 0 ]]; then
  echo
  echo "Single-source control-plane prerequisites are not present yet."
  echo "Do not switch to /Users/preston/hermes or create a sidecar PM tooling worktree."
  echo "First port the required assets into the active Hermes checkout."
  exit 1
fi

echo "Installing Hermes runtime assets from $HERMES_SRC"
(
  cd "$HERMES_SRC"
  python3 tools/install_user_assets.py --format json >/tmp/crypto-bot-install-user-assets.json
)

echo "Syncing crypto-bot-pm profile"
(
  cd "$AGENT_REPO"
  PROFILE_NAME="$PROFILE_NAME" scripts/setup_crypto_bot_pm_profile.sh
)

echo "Smoke-testing crypto-bot-pm plugin tools"
python3 - <<'PY'
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

profile_plugin = Path("/Users/preston/.hermes/profiles/crypto-bot-pm/plugins/crypto-bot-pm/tools.py")
spec = importlib.util.spec_from_file_location("crypto_bot_pm_profile_tools", profile_plugin)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)

for name in [
    "crypto_bot_pm_status",
    "crypto_bot_pm_development_workstream",
    "crypto_bot_pm_development_slice",
]:
    result = json.loads(getattr(module, name)({"output_format": "json"}))
    print(f"{name}: success={result.get('success')} returncode={result.get('returncode')}")
    if not result.get("success"):
        print(json.dumps({k: result.get(k) for k in ("error", "stderr") if result.get(k)}, indent=2))
PY

echo
echo "Next verification from default profile:"
echo "  cd $HERMES_SRC"
echo "  python3 tools/crypto_bot_control_plane_self_check.py --format json"
echo "  python3 tools/crypto_bot_autonomy_readiness.py --format json"
