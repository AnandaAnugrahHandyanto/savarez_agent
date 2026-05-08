# Hermes AI Office — Stage 5 Backend API Architecture

Last updated: 2026-05-08 12:17 KST
Status: Stage 5 technical architecture design. Documentation-only; no implementation approved.

## Stage 5 scope

This document turns the Stage 3 `OfficeState` model and Stage 4 provenance/privacy design into a concrete backend API plan for a future Stage 6 read-only MVP.

Stage 5 does not approve or perform:

- backend implementation,
- frontend implementation,
- dependency additions,
- dashboard/gateway/cron/service restarts,
- config edits,
- Kanban/cron mutations,
- NAS/Obsidian writes,
- public dashboard exposure.

## Decision summary

1. Put the AI Office API under protected built-in dashboard routes: `/api/office/...`.
2. Do not use unauthenticated plugin HTTP routes as browser-facing AI Office endpoints.
3. Make the browser consume only redacted `OfficeState` DTOs, never raw Kanban/session/cron/source rows.
4. Keep Stage 6 read-only and localhost-first.
5. Add remote mode only as an explicit unsupported/deferred capability marker, not an enabled network mode.

## Why built-in `/api/office/...` routes

Stage 2 found that `hermes_cli/web_server.py` applies dashboard token auth to most `/api/` routes, but skips paths starting with `/api/plugins/`:

```python
if path.startswith("/api/") and path not in _PUBLIC_API_PATHS and not path.startswith("/api/plugins/"):
    ... require X-Hermes-Session-Token ...
```

Kanban plugin HTTP routes are therefore not the right browser-facing boundary for AI Office. They may still be internal implementation inputs if called server-side or if existing Python helpers are reused, but the AI Office contract should be a protected built-in route.

Recommended placement:

```text
hermes_cli/web_server.py
  GET /api/office/state
  GET /api/office/state/summary
  GET /api/office/sources
  GET /api/office/schema
```

Future implementation may move aggregation helpers into a dedicated module such as:

```text
hermes_cli/office_state.py
hermes_cli/office_adapters.py
hermes_cli/office_redaction.py
```

but the HTTP route should remain in the protected built-in dashboard app or an explicitly authenticated equivalent.

## Endpoint contract

### `GET /api/office/state`

Primary read-only snapshot endpoint.

Query parameters:

| Parameter | Values | Default | Stage 6 behavior |
|---|---|---|---|
| `mode` | `localhost` | `localhost` | Only supported mode in Stage 6. |
| `include_archived` | `true|false` | `false` | Controls archived Kanban task inclusion. |
| `include_recent_done` | integer | `20` | Limits done/history items. |
| `include_session_titles` | `true|false` | `false` | Must remain false until redaction tests pass. |
| `include_debug` | `true|false` | `false` | Adds safe adapter timing/warnings only; no raw paths/secrets. |

Response: `office_state` from `office-state-model.md`, serialized after redaction.

Required top-level shape:

```yaml
schema_version: 1
generated_at: "ISO timestamp"
mode: "read_only"
display_mode: "localhost"
data_sources: []
summary: {}
rooms: []
agents: []
work_items: []
automations: []
topics: []
events: []
provenance: []
redactions:
  policy_version: 1
  redacted_field_count: 0
  omitted_sections: []
  warnings: []
capabilities:
  read_only: true
  mutations_enabled: false
  remote_mode: "unsupported"
```

### `GET /api/office/state/summary`

Small summary endpoint for future sidebar/status widgets.

Response contains only:

```yaml
generated_at: "ISO timestamp"
data_sources: []
summary: {}
redactions:
  policy_version: 1
  warnings: []
```

This endpoint is optional for Stage 6; the frontend can start with `/api/office/state` only.

### `GET /api/office/sources`

Debug-friendly source health endpoint.

Response contains:

```yaml
generated_at: "ISO timestamp"
sources:
  - id: "kanban|cron|sessions|topics|provenance"
    status: "ok|partial|missing|unavailable|error"
    checked_at: "ISO timestamp"
    item_count: 0
    warning_count: 0
    error_summary: "redacted optional string"
```

This must not include raw exception tracebacks, raw file paths, `.env` values, or secrets.

### `GET /api/office/schema`

Static DTO version/capability descriptor.

Response:

```yaml
schema_version: 1
redaction_policy_version: 1
supported_display_modes: ["localhost"]
unsupported_display_modes: ["remote"]
mutation_endpoints: []
```

## Authentication and authorization

Use the existing dashboard session token behavior:

- frontend calls use `fetchJSON` from `web/src/lib/api.ts`, which injects `X-Hermes-Session-Token` from `window.__HERMES_SESSION_TOKEN__`,
- backend route is not added to `_PUBLIC_API_PATHS`,
- route is not mounted under `/api/plugins/`,
- no API key, token, `.env`, `auth.json`, or credential-pool content is read or returned.

Stage 6 tests should verify:

1. `/api/office/state` returns `401` without the dashboard session token.
2. `/api/office/state` returns `200` with `X-Hermes-Session-Token`.
3. No `POST`, `PUT`, `PATCH`, or `DELETE` `/api/office/...` mutation routes exist.
4. The response has `capabilities.mutations_enabled = false`.

## Read-only guarantees

The API implementation must use read-only data access patterns:

- Kanban: read existing board/task/diagnostic/event metadata; no create/edit/reassign/reclaim/dispatch/archive calls.
- Cron: read jobs and run state; no create/pause/resume/trigger/delete calls; no scheduler tick.
- Sessions: read metadata/list counts; do not return raw messages/tool calls/reasoning.
- Topics: read registry/projection if present; do not edit registry or Telegram topics.
- Provenance: compute projection in memory for Stage 6; no backfill writes.

Stage 6 should not expose any endpoint equivalent to:

```text
POST /api/plugins/kanban/dispatch
POST /api/cron/jobs/{id}/trigger
POST /api/gateway/restart
PUT /api/config
PUT /api/env
```

## DTO boundaries

The backend route must serialize a new safe DTO. It must not proxy raw responses from:

- `/api/plugins/kanban/board`, because task rows can include `body`, `result`, `latest_summary`, comments, and raw diagnostics,
- `/api/cron/jobs`, because jobs include `prompt`, `script`, `context_from`, model/toolset settings, and delivery strings,
- `/api/sessions/{id}/messages`, because transcripts, tool calls, reasoning, and system prompts are sensitive.

Instead, the aggregation flow should be:

```text
source adapter -> normalized internal model -> redaction serializer -> OfficeState DTO -> browser
```

## Display modes

Stage 6 supports only:

```yaml
display_mode: localhost
remote_mode: unsupported
```

Localhost mode may display clearly labeled internal ids when useful:

- board id,
- task id,
- session id,
- cron job id,
- Telegram thread id,
- internal chat id only if explicitly labeled `internal` and passed through policy.

Remote/Tailscale/public modes are not enabled by the API. If a future caller passes `mode=remote`, Stage 6 should return either `400 unsupported display mode` or a DTO with remote mode marked unsupported and stricter hidden ids. Do not silently serve local-internal ids as remote-safe.

## Error handling contract

One source failure must not blank the whole OfficeState.

Recommended route behavior:

1. Each adapter returns either data plus `status=ok|partial`, or an error source status.
2. The aggregator still returns HTTP 200 if at least the server can build a syntactically valid `OfficeState`.
3. `data_sources[]` records per-source failure.
4. HTTP 500 is reserved for bugs that prevent DTO creation entirely.
5. Error summaries are short and redacted.

Example:

```yaml
data_sources:
  - id: kanban
    status: ok
    item_count: 12
  - id: cron
    status: error
    item_count: 0
    error_summary: "read failed: permission denied"
summary:
  failed_automation_count: null
  needs_attention_count: 5
```

Do not convert `cron` failure into `failed_automation_count: 0`.

## Stage 6 implementation slices implied by this API design

1. Add backend DTO dataclasses/types and redaction helpers.
2. Add a minimal `/api/office/schema` endpoint with auth tests.
3. Add `/api/office/state` returning empty but valid DTO and source statuses.
4. Add Kanban adapter and tests.
5. Add cron adapter and tests.
6. Add session metadata adapter and tests.
7. Add topic/provenance computed adapters and tests.
8. Add frontend page after API tests pass.

## Open follow-ups

- Whether Stage 6 should read an optional seed topic registry file if present.
- Whether local mode should show raw chat id by default or hide it behind an internal-id flag.
- Whether session titles can ship in Stage 6 after redaction tests, or remain off until Stage 7.
