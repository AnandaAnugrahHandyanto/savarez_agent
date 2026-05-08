# Hermes AI Office — Stage 5 Frontend Component Architecture

Last updated: 2026-05-08 12:17 KST
Status: Stage 5 technical architecture design. Documentation-only; no implementation approved.

## Purpose

This document defines the non-pixel read-only frontend structure for the future Stage 6 MVP. It translates Stage 3 information architecture into concrete React page/component boundaries while preserving the existing dashboard `/chat` TUI boundary.

## Placement decision

Recommended Stage 6 placement:

```text
web/src/pages/OfficePage.tsx
web/src/lib/api.ts             # add getOfficeState/read-only API method
web/src/App.tsx                # add /office route and sidebar nav item
web/src/types/office.ts        # DTO types if not colocated
web/src/components/office/*    # page sections/cards/drawer
```

Route:

```text
/office
```

Sidebar label:

```text
Office
```

The existing `/chat` route remains the persistent embedded real Hermes TUI. AI Office must not implement a second chat transcript, composer, slash-command handler, or PTY flow.

## API client pattern

Use the existing dashboard client:

```ts
fetchJSON<OfficeState>("/api/office/state")
```

This preserves:

- `X-Hermes-Session-Token` injection,
- `window.__HERMES_BASE_PATH__` reverse-proxy prefix support,
- existing error behavior.

Do not call plugin APIs directly from the AI Office page for MVP. The frontend should consume only redacted `/api/office/...` DTOs.

## Page hierarchy

```text
OfficePage
  ├─ OfficeHeader
  ├─ SourceHealthStrip
  ├─ NeedsAttentionSummary
  ├─ OfficeLayoutGrid
  │   ├─ RoomsPanel
  │   ├─ WorkItemsPanel
  │   ├─ AutomationsPanel
  │   ├─ TopicRoutingPanel
  │   └─ ActivityPanel
  ├─ RedactionStatusPanel
  └─ OfficeInspectorDrawer
```

Initial MVP can implement these as card/list/table sections. Pixel rendering is explicitly deferred.

## Component contracts

### `OfficePage`

Responsibilities:

- fetch `/api/office/state`,
- show loading/error/empty states,
- own selected item state for inspector,
- poll on a modest interval if live updates are not implemented,
- never call mutation APIs.

Recommended polling for Stage 6:

- 10–30 seconds by default,
- manual refresh button is acceptable if it only refetches,
- no WebSocket requirement for first MVP.

### `OfficeHeader`

Inputs:

- `generated_at`,
- `mode`,
- `display_mode`,
- `capabilities`.

Displays:

- product name `Hermes AI Office`,
- `Read-only MVP` badge,
- generated timestamp,
- `Localhost/internal mode` badge,
- warning if remote mode is unsupported.

Must not include:

- start/stop/restart controls,
- config/model/tool editors,
- gateway controls.

### `SourceHealthStrip`

Inputs:

- `data_sources[]`.

Displays cards for:

- Kanban,
- Cron,
- Sessions,
- Topics,
- Provenance.

Rules:

- `ok` is visually calm.
- `partial` and `missing` are warning/informational.
- `error` is high-priority.
- Missing/unavailable source is never rendered as zero work without an explicit source status.
- Clicking a source opens the inspector in source-health mode.

### `NeedsAttentionSummary`

Inputs:

- `summary`,
- high-priority `work_items`,
- failed/timed-out `automations`.

Priority order:

1. blocked tasks,
2. stale/running tasks with diagnostics,
3. failed or timed-out automations,
4. unknown provenance on active work,
5. ready/todo queues.

Displays compact cards/counters and links to filtered panels.

### `RoomsPanel`

Inputs:

- `rooms[]`,
- `topics[]`,
- counts from `summary` or room `counts`.

Room types:

- `kanban_board`,
- `telegram_topic`,
- `system_area`,
- `unknown`.

Rules:

- Kanban board rooms show status counts.
- Telegram topic rooms show purpose/confidence and internal-id policy.
- Unknown room is explicit, not hidden.
- No pixel map layout in Stage 6.

### `WorkItemsPanel`

Inputs:

- `work_items[]`,
- `agents[]`,
- `provenance[]`.

Default grouping:

1. blocked,
2. running,
3. ready,
4. todo/triage,
5. recently done.

Visible fields:

- redacted title,
- status,
- board/room,
- assignee,
- priority,
- updated timestamp,
- flags/diagnostics,
- provenance confidence.

Hidden by default:

- body,
- result,
- comments,
- logs,
- raw events,
- raw transcript.

Click behavior:

- opens inspector drawer with safe metadata only.
- may show a safe link to existing Kanban page later, but no embedded raw details in MVP.

### `AutomationsPanel`

Inputs:

- `automations[]`,
- delivery-related `topics[]` and `provenance[]`.

Visible fields:

- cron job name,
- enabled/state,
- schedule display,
- next run,
- last run,
- last status,
- redacted last error,
- delivery target label/fallback,
- output artifact count.

Must not include:

- trigger/pause/resume/delete buttons,
- prompt/script/context/output content,
- raw output file paths.

The audited `daily-hermes-health-digest` timeout should render as warning if present in future live data.

### `TopicRoutingPanel`

Inputs:

- `topics[]`,
- delivery/provenance records.

Displays:

- known topics with label/purpose/confidence,
- delivery targets from cron/Kanban subscriptions,
- unknown topic bucket,
- warnings such as `registry_missing`, `origin_thread_lost`, `unknown_topic_label`.

Privacy rules:

- no bot tokens,
- no Telegram message text,
- no sender names/user ids by default,
- internal chat/thread ids only per display policy.

### `ActivityPanel`

Inputs:

- `events[]`.

Event types:

- task status changed,
- run started/ended,
- diagnostic surfaced,
- cron last run status,
- session metadata activity,
- topic/delivery observed.

Rules:

- Show safe event kind, timestamp, severity, and redacted summary.
- Do not display raw payloads/tool outputs/logs.
- Live animation is optional and can wait.

### `RedactionStatusPanel`

Inputs:

- `redactions`.

Displays:

- policy version,
- omitted categories,
- warning codes,
- redacted field count.

Recommended MVP position:

- collapsed panel or inspector tab, not prominent first-viewport content,
- visible enough that privacy behavior is inspectable and testable.

### `OfficeInspectorDrawer`

Modes:

- source health,
- room,
- work item,
- automation,
- topic/provenance,
- redaction.

Allowed details:

- exact local ids when policy allows,
- status history summary,
- dependency counts,
- linked safe provenance ids,
- missing reasons,
- redaction categories.

Forbidden details:

- raw transcript,
- raw tool JSON,
- full worker log,
- cron prompt/script/output,
- secrets/config values,
- service control buttons.

## State and failure handling

### Loading

Show skeleton cards for the page sections. Do not display stale successful data as fresh unless timestamp is visible.

### API 401

Show `Dashboard session expired or unauthorized` and suggest reloading the dashboard. Do not attempt alternate auth.

### API 500

Show page-level error, but preserve any response body error summary only if redacted. Stage 6 backend should normally prefer per-source statuses over whole-page 500.

### Source-level failures

Render unaffected sections normally and show source card warning/error.

### Empty states

- Kanban ok + zero boards/tasks => `No Kanban work found`.
- Cron ok + zero jobs => `No scheduled automations`.
- Topics missing => `No topic registry yet; explicit delivery ids may still appear as unknown topics`.
- Provenance unknown => `Legacy item — provenance was not captured`.

## Styling posture

Use existing dashboard visual language and components first. The MVP should be clear and inspectable, not game-like.

Good defaults:

- card grid,
- compact tables/lists,
- severity badges,
- confidence/missing-reason chips,
- collapsible inspector.

Deferred:

- pixel sprites,
- PixiJS/Phaser/canvas,
- LLM-generated bubbles,
- avatar animations,
- simulated office movement.

## Stage 6 frontend verification targets

1. `/office` route renders with mock/fixture OfficeState.
2. Source failures render as warnings, not zero data.
3. Read-only badge is visible.
4. No mutation buttons are present.
5. Sensitive keys like `prompt`, `script`, `tool_calls`, `messages`, `body`, `result`, and `logs` are not rendered from fixtures.
6. Existing `/chat` route continues to mount persistent `ChatPage` unchanged.
7. `fetchJSON` is used so session token and base path are honored.
