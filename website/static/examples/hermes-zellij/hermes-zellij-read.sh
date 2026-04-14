#!/usr/bin/env bash
set -euo pipefail

source "$HOME/.local/bin/hermes-zellij-common"

if [[ $# -lt 1 ]]; then
  echo "Usage: hermes-zellij-read <session> [pane_id] [dump-screen args...]" >&2
  exit 1
fi

session="$1"
shift || true
pane_hint=""
if [[ $# -gt 0 ]] && is_pane_id "$1"; then
  pane_hint="$1"
  shift
fi

pane_id="$(resolve_pane "$session" "$pane_hint")"
if [[ $# -eq 0 ]]; then
  set -- --full
fi

zellij -s "$session" action dump-screen -p "$pane_id" "$@"
