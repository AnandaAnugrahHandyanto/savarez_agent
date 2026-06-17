---
name: sap-crew-delegate
description: Delegate SAP/ABAP/CDS/RAP/CPI/transport tasks to the CrewAI control-plane. Hermes does pre-flight (validate login + plan + quota via the auth introspect endpoint) then fires the full crew workflow (4-agent pipeline + Hermes quality gate) through the registered sap_crew MCP server. Trigger when the user asks for SAP/ABAP code generation, review, analysis, transport release, or anything referencing Z*/Y* objects, ABAP, CDS, RAP, BTP, CPI, or SAP transactions.
version: 1.0.0
author: Hermes Agent (Nous Research)
license: MIT
metadata:
  hermes:
    tags: [SAP, ABAP, CrewAI, Delegation, MCP, Quality-Gate]
    related_skills: [mcp]
---

# SAP Crew Delegate

Hermes is the **master orchestrator**; the CrewAI backend (`apps/api-railway`) is the
**SAP skills/agents orchestrator**. For SAP-domain work, Hermes does NOT solve the task
itself — it triages, authenticates, and delegates the whole task to the crew, which runs
its 4-agent pipeline (orchestration → synthesis → review → final) plus the Hermes
quality gate (abaplint + auto-fix), and returns a finished answer.

## Prerequisites

1. The `sap_crew` MCP server registered in `~/.hermes/config.yaml` (see
   `docs/sap-crew-integration.md`). This exposes `sap_copilot_delegate` and the granular
   SAP tools (`sap_*`, `abap_lint`, `cpi_*`).
2. `API_RAILWAY_TOKEN` set in `~/.hermes/.env` (bearer for the control-plane).

## When to delegate

Trigger delegation when the request is SAP-domain:
- ABAP code generation, refactor, review, TDD
- CDS / RAP / BTP / Clean Core questions
- Objects named `Z*` / `Y*`, transactions, transports
- CPI iFlows, OData, BAPI/RFC, HANA

Generic dev/web/research tasks → handle with Hermes' own tools, do NOT delegate.

This skill runs in the **admin** context (Telegram / CLI), single identity, one
`API_RAILWAY_TOKEN`. End users never reach this skill — they call api-railway over HTTP
directly.

## Flow

1. **Delegate the full task.** Call the `sap_copilot_delegate` tool from the `sap_crew`
   MCP server with the request:
   - `prompt`: the full SAP request
   - `plan`: `pro` for admin (machinery token = unlimited)
   - `intent_hint`: optional short hint (e.g. "abap-review", "cds-generate")

   The control-plane re-validates the token and consumes quota exactly once (admin = no
   quota cost). This call is **high latency** (cheap-first + 4 agents + lint loop) — up to
   ~180s.

2. **Deliver.** Return the crew's `reply` on Telegram/CLI. Mention any quality-gate
   improvements the crew reported.

Optional health/quota peek (mostly a no-op for admin):
`POST $API_RAILWAY_URL/v1/auth/introspect` → `{valid, plan, used, limit, allowed}`.

## Granular fallback

For a single, well-scoped SAP action (e.g. just lint a snippet, just read one ADT
object), call the matching granular `sap_crew` tool directly (`abap_lint`,
`sap_adt_cli`, `sap_odata_query`, ...) instead of the full pipeline.

## Notes

- Never put `API_RAILWAY_TOKEN` in the versioned config — use `~/.hermes/.env`.
- Do not re-implement the SAP intent analysis or cheap-first routing here; that lives in
  the control-plane. Hermes only does coarse "is this SAP?" triage.
