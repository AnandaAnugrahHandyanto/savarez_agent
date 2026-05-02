#!/usr/bin/env bash
set -euo pipefail

source "$HOME/.local/bin/hermes-zellij-common"

if [[ $# -lt 2 ]]; then
  echo "Usage: hermes-zellij-send <session> [pane_id] <message...>" >&2
  exit 1
fi

session="$1"
shift
pane_hint=""
if [[ $# -gt 0 ]] && is_pane_id "$1"; then
  pane_hint="$1"
  shift
fi

if [[ $# -lt 1 ]]; then
  echo "Missing message" >&2
  exit 1
fi

pane_id="$(resolve_pane "$session" "$pane_hint")"
message="$*"
zellij -s "$session" action write-chars -p "$pane_id" "$message"
zellij -s "$session" action send-keys -p "$pane_id" Enter
printf 'session=%s\npane=%s\n' "$session" "$pane_id"
