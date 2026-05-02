#!/usr/bin/env bash
set -euo pipefail

source "$HOME/.local/bin/hermes-zellij-common"

if [[ $# -lt 1 ]]; then
  echo "Usage: hermes-zellij-stop <session> [pane_id] [--keep-session]" >&2
  exit 1
fi

session="$1"
shift || true
pane_hint=""
keep_session=0

if [[ $# -gt 0 ]] && is_pane_id "$1"; then
  pane_hint="$1"
  shift
fi
if [[ ${1:-} == "--keep-session" ]]; then
  keep_session=1
  shift || true
fi
if [[ $# -gt 0 ]]; then
  echo "Unexpected arguments: $*" >&2
  exit 1
fi

pane_id="$(resolve_pane "$session" "$pane_hint")"
zellij -s "$session" action write-chars -p "$pane_id" "/exit"
zellij -s "$session" action send-keys -p "$pane_id" Enter
sleep 2
if [[ "$keep_session" -eq 0 ]]; then
  zellij kill-session "$session" >/dev/null 2>&1 || true
fi
printf 'session=%s\npane=%s\n' "$session" "$pane_id"
