# Hermes AI Office — Stage 3 Non-Goals and Mutation Boundary

Last updated: 2026-05-08 11:54 KST
Status: Stage 3 safety/product boundary. Documentation-only; no implementation approved.

## Purpose

This document defines what the read-only MVP must not do, and which existing Hermes endpoints/actions are outside the allowed boundary until the user explicitly approves a later implementation/control stage.

## Core boundary

The Stage 6 read-only MVP, if later approved, may read and normalize safe metadata. It must not mutate Hermes runtime state.

Allowed in read-only MVP design:

- Read Kanban boards/tasks/counts/diagnostics/events through safe serializers.
- Read cron job health/status/schedule/delivery metadata.
- Read session metadata/provenance summaries.
- Read/resolve topic labels from a designed registry or safe config-derived source.
- Display source health and redaction reports.
- Link to existing dashboard pages where safe.

Not allowed in read-only MVP:

- creating, editing, reassigning, reclaiming, dispatching, archiving, or deleting tasks,
- creating, pausing, resuming, triggering, editing, or deleting cron jobs,
- restarting gateway/dashboard/systemd services,
- editing config, `.env`, credentials, tools, skills, memory, or MCP settings,
- approving/denying gateway commands,
- sending Telegram/Discord/Slack messages,
- writing to NAS/Obsidian/shared ledger,
- exposing dashboard outside localhost,
- adding dependencies or vendoring Pixel Agents code,
- reimplementing chat/transcript/composer behavior in React.

## Existing endpoints to avoid in MVP

### Kanban plugin mutation endpoints

Avoid all mutation/control endpoints under `/api/plugins/kanban`, including but not limited to:

- `POST /tasks`
- `PATCH /tasks/{task_id}`
- `POST /tasks/{task_id}/comments`
- `POST /links`
- `DELETE /links`
- `POST /tasks/bulk`
- `POST /tasks/{task_id}/reclaim`
- `POST /tasks/{task_id}/specify`
- `POST /tasks/{task_id}/reassign`
- `POST/DELETE /tasks/{task_id}/home-subscribe/{platform}`
- `POST /dispatch`
- board create/patch/delete/switch endpoints

Read-only candidates, subject to Stage 5 API/security design:

- `GET /api/plugins/kanban/boards`
- `GET /api/plugins/kanban/board`
- `GET /api/plugins/kanban/tasks/{task_id}` with redacted serializer rules
- `GET /api/plugins/kanban/diagnostics`
- `GET /api/plugins/kanban/stats`
- `GET /api/plugins/kanban/assignees`
- `GET /api/plugins/kanban/home-channels`
- `WebSocket /api/plugins/kanban/events` only if redacted and authenticated appropriately

Security note:

Stage 2 found plugin HTTP routes under `/api/plugins/` are skipped by the dashboard auth middleware, while the Kanban WebSocket requires a token. Stage 5 must decide whether AI Office endpoints live under protected built-in `/api/office/...` routes rather than unauthenticated plugin routes.

### Cron mutation endpoints

Avoid:

- `POST /api/cron/jobs`
- `PUT /api/cron/jobs/{job_id}`
- `POST /api/cron/jobs/{job_id}/pause`
- `POST /api/cron/jobs/{job_id}/resume`
- `POST /api/cron/jobs/{job_id}/trigger`
- `DELETE /api/cron/jobs/{job_id}`

Read-only candidates:

- `GET /api/cron/jobs`
- `GET /api/cron/jobs/{job_id}`

Additional boundary:

- Do not read or display raw cron output contents by default.
- Do not read script file contents for UI display.
- Do not execute scripts or trigger scheduler ticks.

### Session endpoints

Potentially safe:

- `GET /api/sessions` for metadata lists.
- `GET /api/sessions/search` only if snippets are redacted and intentionally in scope.

Unsafe by default for AI Office:

- `GET /api/sessions/{session_id}/messages` as default office content.
- Full message bubbles/tool-call JSON/reasoning display.

Rationale:

The existing Sessions page can remain a dedicated session browser. AI Office should default to metadata/provenance summaries.

### Gateway/service/config boundaries

Avoid all gateway/service/config controls in AI Office MVP:

- no `/restart` equivalent,
- no `hermes gateway restart/start/stop`,
- no systemd controls,
- no toolset/config/model editing,
- no pairing approvals,
- no message sending.

## Red lines for privacy

Never display:

- bot tokens,
- API keys,
- `.env` values,
- `auth.json` contents,
- credential pool data,
- raw tool arguments/outputs,
- raw shell command output where secrets/paths may appear,
- full prompts/transcripts/system prompts/reasoning,
- unredacted cron prompt/script/output content.

Default-hide but potentially review later:

- task body/result/comments,
- session preview snippets,
- worker logs,
- stack traces,
- absolute local paths,
- chat/user/message ids in remote mode.

## Non-goals for Stage 3–6

1. Pixel/game visualization.
2. Direct Pixel Agents code reuse.
3. Asset/sprite reuse.
4. Synthetic Smallville-style agent society.
5. Browser task controls.
6. Browser cron controls.
7. Remote/public dashboard deployment.
8. NAS/Obsidian sync integration.
9. LLM-generated speech bubbles/summaries.
10. A second chat UI.
11. A new source-of-truth task database.
12. Automatic incident creation from cron failures.

## Mutation approval gates

Before any later mutation feature can be considered, require a separate design/review covering:

1. Exact action list and endpoint list.
2. Authentication/authorization posture.
3. Confirmation/approval UX.
4. Audit logging.
5. Rollback or failure behavior.
6. Tests proving read-only components cannot call mutation endpoints.
7. User approval for that specific implementation slice.

## Stage 6 implementation preconditions

Before any code implementation begins, Stage 4 and Stage 5 should provide:

- topic registry/provenance storage decision,
- backend endpoint/auth placement decision,
- redaction serializer policy,
- data-source failure behavior,
- frontend component plan,
- test plan using `scripts/run_tests.sh`,
- explicit user approval for implementation.
