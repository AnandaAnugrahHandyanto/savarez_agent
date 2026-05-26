---
description: Guarded preflight for Town/OpenClaw/Hermes agent tasks before edits
arguments:
  - name: request
    description: The requested task or target, e.g. "diagnose herald" or "update selector-ranker docs"
    required: true
---

# Town / OpenClaw Preflight: {{request}}

## Purpose

Before any Hermes/OpenClaw/Town agent task, collect context and classify whether
the task is safe, gated, or blocked.

This command is read-only. It does not authorize edits.

## Step 1: Read governing references

1. Read `docs/TOWN_OPENCLAW_AGENT_FLOW_CONTRACT.md`.
2. Read `docs/FAILURE_PATTERN_LIBRARY.md`.

## Step 2: Fetch MCP context when available

Use these MCP tools where available:

1. `fleet_context_snapshot()`
2. `agent_health_summary()`
3. `town_brief()`
4. `skills_list()`
5. `agents_list(include_heartbeat=true)`
6. If a named agent or skill is implied:
   - `agents_get(name="<target>")`
   - `skills_read(name="<target>")`
7. If a spec, artifact, or failure mode is implied:
   - `knowledge_query(question="{{request}}")`
   - `knowledge_read(artifact="held_spec_ledger")`
   - `learnings_read()`

## Step 3: Classify touched surface

Classify whether the request touches any of:

- docs only
- wrapper skill
- registry
- runtime identity
- MCP config
- gateway
- cron
- production code
- model/ranker/selector/sizing/KG

## Step 4: Risk class

Use exactly one:

- `SAFE` — docs/proposal/test-only, no governed runtime or production surface.
- `GATED` — may be valid, but requires explicit operator approval before edits.
- `BLOCKED` — violates the flow contract or active governance constraints.

Mark as `GATED` or `BLOCKED` if the request touches:

- `AGENT_REGISTRY.json`
- `skills/openclaw/*`
- MCP config
- gateway/platform code
- cron
- runtime identity files
- SOUL/HEARTBEAT/HISTORY writes
- production model/ranker/selector/sizing/KG
- Codegraph Hermes registration

## Step 5: Return report

Return:

```text
Target agent/skill:
Source-of-truth consulted:
Known failure-pattern matches:
Health warnings:
Touched surface:
Risk class: SAFE | GATED | BLOCKED
Proposed next action:
Exact files that would be touched:
Approval required: yes/no
```

## Stop rule

Stop before edits unless the user explicitly approves the proposed next action.

Do not synthesize identity from registry metadata or OpenClaw wrapper text.
