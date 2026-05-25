---
description: Bootstrap a Cursor agent with bounded Hermes Town context
---

# Cursor Bootstrap

## Step 1: Start with the compact view

1. `town_brief()` — status, paths, memory/read status, gateway mode, active issues, next MCP calls.
2. If `town_brief` is unavailable, use `fleet_context_snapshot(summary=True)`.

## Step 2: Decide whether to expand context

- If changing a named agent: run `town_handoff_bundle(agent_name="<agent>")`.
- If memory/reference context matters: run `learnings_read(file="memory.md")`.
- If changing a governed spec or pipeline: run `town_handoff_bundle(spec_id="<spec>")`.
- If health is not `ok`: run `agent_health_summary()`.

## Step 3: Report before editing

Summarize:
- Source of truth: `[HERMES_AGENTS_DIR/HERMES_REPO/agents/etc.]`
- Memory/reference reads: `[available/missing, path]`
- Gateway: `[reachable/not reachable]`
- Missing layers or stale heartbeats: `[list or none]`
- Held spec flags: `[count and top matches]`
- Next allowed action: `[specific action]`

Do not write to `.learnings/`, artifacts, registry, or SOUL files through MCP.
