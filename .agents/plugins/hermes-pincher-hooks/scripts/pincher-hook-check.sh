#!/usr/bin/env bash
# Goose Open Plugins hook bridge for Pincher.
#
# Goose invokes this command for PreToolUse events and pipes the event payload
# as JSON on stdin. Keep the bridge tiny and deterministic: preserve the exact
# Goose payload, annotate where it came from, then delegate the policy decision
# to Pincher's hook checker. Pincher already emits the JSON decision shape the
# host agent expects.
set -euo pipefail

payload="$(cat)"
plugin_root="${PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

# Lightweight audit trail for local dogfood/debugging. Never block if the log
# cannot be written; hook correctness must depend on pincher hook-check only.
{
  printf -- '---- PreToolUse @ %s ----\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  printf '%s\n' "$payload"
} >> "${plugin_root}/last-event.log" 2>/dev/null || true

# Pass the event through unchanged. This preserves Goose's native fields
# (event, tool_name, tool_input, etc.) and also works with Claude-style payloads
# if a user runs the script manually while comparing agent hook systems.
printf '%s' "$payload" | pincher hook-check
