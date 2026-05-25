# Latest State — Local Cursor/Hermes Snapshot

Generated: 2026-05-25
Scope: local workspace bootstrap for Hermes MCP `fleet_context_snapshot`
Source: `.learnings/memory.md` HOT-tier memory + current Hermes repo state

## Status

- Mode: MCP skills/context is always available; live-ops is available only when the Hermes gateway is running.
- Hermes repo: `/workspace`
- Runtime agents directory: `/workspace/agents`
- Agent registry: present
- Registered agents: 30
- HOT learnings: present at `/workspace/.learnings/memory.md`
- MCP skills/context tools: present (`fleet_context_snapshot`, `agent_health_summary`, `knowledge_query`, `town_brief`, skills/agents/knowledge/learnings/artifacts readers)
- Town skill snapshots: 39 files under `docs/skills/*/SKILL.md`
- OpenClaw agent wrapper skills: 31 files under `skills/openclaw/*/SKILL.md`
- Current main: `a654b3d6b` (`cursor: update pipeline-production and llm-config rules — CI fix + gateway`)

## Project State

- Project: Wake Robin Capital biotech investment screener.
- Production pipeline: 13-step daily cron, 5:30 PM ET.
- Governance mode: CCFT; deterministic outputs required.
- Active ruleset: v1.14.0 (`8887576e`), coinvest-only selector and pairwise_minimal ranker.
- Sort anchor: `selector_score` (`coinvest_score_z` 100%).
- `inst_delta_z`: zeroed in selector since 2026-05-04.
- Model fleet: `deepseek/deepseek-v4-flash:free` per HOT memory.

## Freeze / Gate State

- Architecture freeze: active through the h20d checkpoint (~2026-05-26).
- Expected path per HOT memory: Path A / freeze lift, June 1 KG deployment + ranker shadow start.
- No enforcement, scoring, or ranking changes before freeze lift without explicit operator approval.

## Data / Cohort State

- Q1 2026 13F cohort: cleared as of 2026-05-19.
- Next 13F cycle: Q2 2026, deadline ~2026-08-14.

## Local Identity Substrate Note

- `/workspace/agents` is registry/index only in this cloud checkout.
- Runtime SOUL/HEARTBEAT/IDENTITY documents require a local `HERMES_AGENTS_DIR` mount pointing at the operational repo.
- Do not synthesize runtime identity layers from registry metadata or OpenClaw wrapper skills.

## Notes

This file is a local MCP knowledge-layer bootstrap artifact. It is not an
independent production ledger and should not supersede canonical runtime
wrappers, SOUL/IDENTITY/HEARTBEAT files, registry data, or governance memos.
