#!/usr/bin/env bash
set -euo pipefail

source "$HOME/.local/bin/hermes-zellij-common"
require_cmd hermes

if [[ $# -lt 1 ]]; then
  echo "Usage: hermes-zellij-start <session> [hermes args...]" >&2
  exit 1
fi

session="$1"
shift || true

ensure_session "$session"
pane_id="$(zellij -s "$session" run --cwd "$PWD" -- hermes "$@")"
printf 'session=%s\npane=%s\n' "$session" "$pane_id"
