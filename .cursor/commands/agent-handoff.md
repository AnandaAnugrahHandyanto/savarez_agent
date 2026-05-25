---
description: Build a read-only handoff bundle for a named Hermes agent
arguments:
  - name: agent_name
    description: Agent name to hand off, e.g. herald or bellringer
    required: true
---

# Agent Handoff: {{agent_name}}

## Step 1: Fetch the bounded bundle

1. `town_handoff_bundle(agent_name="{{agent_name}}")`
2. If the bundle reports `agent.found=false`, fall back to:
   - `agents_get(name="{{agent_name}}")`
   - `skills_read(name="{{agent_name}}")`

## Step 2: Check authority and truth layers

- Use SOUL.md / IDENTITY / HEARTBEAT as behavioral truth.
- Use `AGENT_REGISTRY.json` only as index and discovery metadata.
- Check latest-state, held-spec, contradiction, and memory/reference matches in the bundle.

## Step 3: Report for the receiving agent

Summarize:
- Agent found: `[yes/no]`
- Behavioral truth path: `[SOUL.md path]`
- Registry status/lane/authority: `[values]`
- Heartbeat status: `[fresh/stale/missing]`
- Memory/reference matches: `[list or none]`
- Relevant held specs or contradictions: `[list or none]`
- Safe next action: `[specific action]`

Do not write to `.learnings/`, artifacts, registry, or SOUL files through MCP.
