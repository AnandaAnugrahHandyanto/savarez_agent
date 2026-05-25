---
description: Check whether Hermes MCP is in skills-only or live-ops mode
---

# Gateway Status

## Step 1: Fetch mode and health

1. `town_brief()`
2. If more detail is needed: `agent_health_summary()`

## Step 2: Interpret mode

- `gateway.reachable=true`: live ops tools may be usable.
- `gateway.reachable=false`: skills/context tools are still healthy if `skills_context_available=true`.
- Skills/context mode still includes read-only memory/reference reads via `learnings_read(file="memory.md")`.
- Messaging send/approval tools require a running gateway and active platform sessions.

## Step 3: Report

Summarize:
- MCP mode: `[skills_only/live_ops]`
- Gateway reachable: `[yes/no]`
- Skills/context available: `[yes/no]`
- Memory/reference reads available: `[yes/no]`
- Live ops caveat: `[what is unavailable]`
- Next action: `[start gateway / continue offline / investigate sessions]`

Do not treat gateway unavailability as a failure of the read-only fleet tools.
