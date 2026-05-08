# Hermes AI Office — Kanban Data Model Audit

Last updated: 2026-05-08 11:44 KST
Status: Stage 2 read-only audit. No Kanban boards/tasks were created or mutated.

## Scope

Audit current Hermes Kanban data surfaces for a future read-only AI Office view.

Primary files inspected:

- `hermes_cli/kanban_db.py`
- `plugins/kanban/dashboard/plugin_api.py`
- `plugins/kanban/dashboard/manifest.json`
- `tests/plugins/test_kanban_dashboard_plugin.py`

## Storage location and board model

Kanban is SQLite-backed. Current live boards in this WSL runtime are under:

- `/home/lidises/.hermes/kanban/boards/<slug>/kanban.db`

Current board counts observed read-only on 2026-05-08 11:44 KST:

- `hermes-runtime`: blocked=2, done=3, notify_subs=0
- `koreandeer-content`: done=2, ready=1, todo=3, notify_subs=0
- `obsidian-ledger`: blocked=3, notify_subs=0

The old/default board may exist separately, but the inspected live board directory listed the three boards above.

## Core schema

`hermes_cli/kanban_db.py` defines `SCHEMA_SQL` with these important tables:

- `tasks`
- `task_links`
- `task_comments`
- `task_events`
- `task_runs`
- `kanban_notify_subs`
- indices for common task/link/event/run lookups

### `tasks` table fields relevant to AI Office

Key identity/content fields:

- `id`
- `title`
- `body`
- `result`
- `created_by`
- `created_at`, `updated_at`

Workflow/display fields:

- `status`
- `priority`
- `assignee`
- `tenant`
- `workspace_kind`
- `workspace_path`
- `workflow_template_id`
- `current_step_key`
- `skills`

Dispatch/run/failure fields:

- `claim_lock`
- `claim_expires`
- `worker_pid`
- `last_failure_error`
- `consecutive_failures`
- `max_runtime_seconds`
- `last_heartbeat_at`
- `current_run_id`
- `max_retries`

Provenance-adjacent fields:

- `idempotency_key`
- `created_by`
- `tenant`
- `workspace_path`

Current gap: task rows do not appear to have a first-class `source_platform`, `source_chat_id`, `source_thread_id`, `source_message_id`, or `session_id` column. Provenance may need to be derived from comments/events or added later.

## Status columns

Kanban dashboard plugin uses visible columns:

- `triage`
- `todo`
- `ready`
- `running`
- `blocked`
- `done`

`archived` is available through a filter toggle rather than default visible column.

AI Office mapping suggestion:

- `triage` / `todo`: waiting desks/inbox.
- `ready`: queue ready for agent pickup.
- `running`: active agent desk.
- `blocked`: needs attention / red badge.
- `done`: completed shelf/archive feed.

## Dashboard plugin API

Kanban plugin manifest:

- name: `kanban`
- dashboard tab path: `/kanban`
- API file: `plugin_api.py`
- mounted backend prefix: `/api/plugins/kanban`

Read-mostly endpoints useful for AI Office:

- `GET /api/plugins/kanban/board?tenant=&include_archived=&board=`
- `GET /api/plugins/kanban/tasks/{task_id}?board=`
- `GET /api/plugins/kanban/diagnostics?severity=&board=`
- `GET /api/plugins/kanban/config`
- `GET /api/plugins/kanban/home-channels?task_id=&board=`
- `GET /api/plugins/kanban/stats?board=`
- `GET /api/plugins/kanban/assignees?board=`
- `GET /api/plugins/kanban/tasks/{task_id}/log?tail=&board=`
- `GET /api/plugins/kanban/boards?include_archived=`
- `WebSocket /api/plugins/kanban/events?token=&since=&board=`

Mutation/control endpoints to avoid in read-only MVP:

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

## Board response shape

`GET /board` returns:

- `columns`: ordered list of `{name, tasks}`.
- `tenants`: distinct tenant list.
- `assignees`: distinct non-archived assignee list.
- `latest_event_id`: max `task_events.id`.
- `now`: server epoch seconds.

Each task dictionary includes raw task fields plus derived/attached fields:

- `age`
- `latest_summary` preview, truncated to 200 chars on board view
- `link_counts`
- `comment_count`
- `progress` for parent-child completion rollup
- `diagnostics`
- `warnings` summary

`GET /tasks/{task_id}` returns detail:

- `task`
- `comments`
- `events`
- `links`: parents/children
- `runs`

## Events and live updates

Kanban uses append-only `task_events` and a WebSocket tail:

- WebSocket polls SQLite every 0.3s.
- Query returns events where `id > cursor`, ordered ascending, limit 200.
- Payload includes `id`, `task_id`, `run_id`, `kind`, `payload`, `created_at`.

This is the strongest existing feed for AI Office animation and activity bubbles, but messages must be redacted/condensed before display.

## Diagnostics

`plugin_api.py` delegates to `hermes_cli.kanban_diagnostics` and exposes diagnostics on:

- board cards
- task drawer detail
- `/diagnostics`

Known diagnostic/warning concepts include hallucinated card IDs, crashes/spawn failures, and stuck/blocked conditions. This is suitable for AI Office alert badges.

## Notifications/home channels

`kanban_notify_subs` stores per-task notification subscriptions with:

- `task_id`
- `platform`
- `chat_id`
- `thread_id`

`/home-channels` reads gateway home channel config and tells whether a task is subscribed. Current checked boards had zero notify subscriptions.

## Gaps

- No normalized source/provenance columns on `tasks` for Telegram topic/message/session origin.
- Many plugin endpoints mutate state; AI Office must explicitly restrict itself to read-only paths.
- Plugin HTTP API is not token-protected under current dashboard middleware; only the WebSocket checks token.
- `latest_summary` and `result` can contain sensitive content. Office map should show compact status, not full prose by default.
- Worker logs may contain sensitive tool output; avoid exposing logs in office MVP except behind explicit detail view.

## Recommendation for Stage 4 provenance design

Add or derive a separate provenance layer rather than overloading task title/body. Candidate table or event payload fields:

- `task_id`
- `source_platform`
- `source_chat_id`
- `source_thread_id`
- `source_message_id`
- `source_user_id`
- `source_session_id`
- `source_topic_label`
- `created_via`: dashboard / telegram / cli / cron / kanban-worker
- timestamps

Keep raw message text out of the provenance model unless explicitly requested.
