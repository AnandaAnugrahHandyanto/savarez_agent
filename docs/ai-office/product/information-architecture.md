# Hermes AI Office — Stage 3 Information Architecture

Last updated: 2026-05-08 11:54 KST
Status: Stage 3 information architecture. Documentation-only; no implementation approved.

## IA principle

The MVP should first be an operational map, not a game. The pixel-office metaphor is useful language, but the first UI should remain exact, inspectable, and boring enough to trust.

## Navigation placement

Future implementation candidate, not approved in Stage 3:

- Existing dashboard keeps `/chat` as embedded `hermes --tui`.
- AI Office should be a new sidecar page such as `/office` or a dashboard plugin tab, after Stage 5 decides endpoint/auth placement.
- It should not replace `/sessions`, `/cron`, `/plugins/kanban`, or `/chat`; it summarizes and links to safe detail surfaces.

## MVP page hierarchy

```text
AI Office
  ├─ Header / read-only badge
  ├─ Source health strip
  ├─ Needs-attention summary
  ├─ Rooms / workstreams
  │   ├─ Kanban board rooms
  │   ├─ Telegram topic rooms
  │   └─ System rooms
  ├─ Work items
  │   ├─ blocked
  │   ├─ running
  │   ├─ ready/todo
  │   └─ recently done
  ├─ Automations
  │   ├─ cron jobs
  │   ├─ failed/timed-out jobs
  │   └─ next scheduled jobs
  ├─ Topic routing
  │   ├─ known topics
  │   ├─ delivery targets
  │   └─ unknown provenance bucket
  ├─ Activity/events
  │   ├─ safe status events
  │   └─ warnings/errors
  └─ Inspector drawer
      ├─ selected room
      ├─ selected work item
      ├─ selected automation
      └─ selected topic/provenance
```

## Top-level sections

### 1. Header / read-only badge

Purpose:

- Reinforce that the MVP cannot mutate state.
- Show generated timestamp and mode.

Content:

- Product name: `Hermes AI Office` unless renamed later.
- Badge: `Read-only MVP`.
- Timestamp: `generated_at`.
- Optional link to `STATUS.md`/`NEXT.md` later, but no file write behavior.

### 2. Source health strip

Purpose:

- Make partial data obvious.
- Avoid interpreting missing source as empty work.

Cards:

- Kanban: `ok|partial|missing|error` plus board/task count.
- Cron: `ok|partial|missing|error` plus job count/failure count.
- Sessions: `ok|partial|missing|error` plus safe session count/source count.
- Topics: `ok|partial|missing|error` plus known/unknown count.

### 3. Needs-attention summary

Purpose:

- Put `blocked` and failed automations first.

Content priority:

1. Blocked Kanban work.
2. Running work that is stale or has diagnostics.
3. Cron jobs with `last_status=error`, timeout, delivery error, or `state=error`.
4. Unknown provenance for otherwise important work.
5. Ready/todo queues.

### 4. Rooms / workstreams

Purpose:

- Map Hermes concepts into the office metaphor without requiring a pixel renderer.

Room types:

| Room type | Source | Example from audit | MVP rendering |
|---|---|---|---|
| Kanban board room | Kanban board | `hermes-runtime` | card/list row with counts |
| Telegram topic room | Topic registry/delivery/source | `00-운영실`, `70-자동화` | routing room card |
| Automation room | Cron grouping | daily health digest | optional grouping under topic room |
| Unknown room | Missing provenance | unknown topic/session | explicit unknown bucket |

Rules:

- Use rooms as grouping, not as source of truth.
- Do not fabricate a room when no source/provenance exists; put it under `unknown`.
- Pixel room layout is deferred.

### 5. Work items

Purpose:

- Show actionable task state.

Default grouping:

1. Blocked.
2. Running.
3. Ready.
4. Todo/triage.
5. Recently done.

Card fields:

- safe title,
- status,
- board/room,
- assignee,
- priority if available,
- updated time,
- flags/diagnostics,
- provenance confidence (`observed`, `derived`, `unknown`).

Hidden by default:

- body,
- result,
- comments,
- logs,
- raw events,
- raw session transcript.

### 6. Automations

Purpose:

- Represent cron jobs as scheduled bots/machines.

Fields:

- job name,
- enabled/state,
- schedule display,
- last run,
- next run,
- last status,
- redacted last error,
- delivery room/topic,
- output artifact count only.

MVP behavior:

- The audited `daily-hermes-health-digest` timeout should show as a warning.
- No trigger/pause/resume/delete controls.

### 7. Topic routing

Purpose:

- Explain where Telegram-origin or Telegram-destination work belongs.

Display groups:

- Known topics: name, purpose, platform, thread id.
- Delivery targets: cron or task notification subscriptions pointing at topics.
- Unknown topics: raw ids or unknown labels when registry lacks data.

Privacy posture:

- No bot token, env values, or message text.
- Chat id can be internal/local-only; later remote mode should prefer label/hash.

### 8. Activity/events

Purpose:

- Give recent chronology and later feed animation.

Event types for MVP:

- task status changed,
- task run started/ended,
- diagnostic warning surfaced,
- cron job last run status,
- session started/ended metadata,
- topic/delivery observed.

Rules:

- Event payloads are summarized/redacted.
- Raw logs/tool output are not shown.
- Live WebSocket animation can wait; polling or snapshot is enough for first MVP.

### 9. Inspector drawer

Purpose:

- Provide precise metadata without cluttering the map.

Inspector modes:

- Room inspector.
- Work item inspector.
- Automation inspector.
- Topic/provenance inspector.
- Data-source error inspector.

Safe detail examples:

- exact task id,
- exact board id,
- status history summary,
- dependency counts,
- linked session id if safe,
- provenance confidence and missing reason,
- redaction notes.

Unsafe default detail:

- raw transcript,
- raw tool JSON,
- full worker log,
- cron prompt/script/output,
- secrets/config values.

## Empty and error states

### No Kanban boards

Show:

- `Kanban source available but no boards/tasks were found` if source is ok and empty.
- `Kanban unavailable` if the source failed.

### No cron jobs

Show:

- `No scheduled automations` only if cron source is ok and job count is zero.
- Do not hide a cron source error.

### Unknown provenance

Show:

- `Unknown source/topic` badge.
- Explanation: current schemas may not yet store first-class topic/session provenance.
- Do not invent topic names.

### Sensitive fields redacted

Show:

- `Details omitted by redaction policy` with a field category, not the sensitive content.

## MVP screen acceptance criteria

1. User can answer what is blocked/running/failing from the first viewport.
2. User can see which data sources are unavailable or partial.
3. User can identify the board/topic/automation associated with safe metadata when known.
4. User sees `unknown` when provenance is missing.
5. User cannot mutate Hermes state from the AI Office MVP.
6. User cannot view raw transcripts/tool args/logs by default.
7. Pixel visualization is not required for MVP success.
