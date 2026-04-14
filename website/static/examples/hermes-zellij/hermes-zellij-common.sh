#!/usr/bin/env bash
set -euo pipefail

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

is_pane_id() {
  [[ "${1:-}" =~ ^terminal_[0-9]+$ || "${1:-}" =~ ^[0-9]+$ ]]
}

normalize_pane_id() {
  local pane="${1:-}"
  if [[ "$pane" =~ ^[0-9]+$ ]]; then
    printf 'terminal_%s\n' "$pane"
  else
    printf '%s\n' "$pane"
  fi
}

ensure_session() {
  local session="$1"
  zellij attach -b "$session" >/dev/null 2>&1 || true
}

resolve_pane() {
  local session="$1"
  local requested="${2:-}"

  if [[ -n "$requested" ]]; then
    normalize_pane_id "$requested"
    return 0
  fi

  zellij -s "$session" action list-panes --json \
    | python3 -c 'import json,sys
panes=json.load(sys.stdin)
terminals=[p for p in panes if not p.get("is_plugin") and not p.get("exited")]
if not terminals:
    raise SystemExit("No active terminal panes found")
focused=[p for p in terminals if p.get("is_focused")]
if focused:
    chosen=focused[0]
else:
    terminals.sort(key=lambda p: int(p.get("id", -1)))
    chosen=terminals[-1]
print("terminal_%s" % chosen["id"])'
}

require_cmd zellij
require_cmd python3
