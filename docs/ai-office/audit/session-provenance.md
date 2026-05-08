# Hermes AI Office — Session Provenance Audit

Last updated: 2026-05-08 11:44 KST
Status: Stage 2 read-only audit. No session rows/messages were mutated.

## Scope

Audit Hermes session storage/search/source metadata for a future read-only AI Office provenance layer.

Primary files inspected:

- `hermes_state.py`
- `hermes_cli/web_server.py`
- `web/src/pages/SessionsPage.tsx`
- `gateway/session.py`
- `gateway/platforms/telegram.py`

## Storage

Hermes core sessions are SQLite-backed in:

- `/home/lidises/.hermes/state.db`

`hermes_state.py` design notes:

- WAL mode for concurrent readers and one writer.
- FTS5 full-text search over messages.
- Trigram FTS5 table for CJK substring search.
- Compression-triggered session splitting via `parent_session_id` chains.
- Batch runner and RL trajectories are not stored here.
- Session source tagging records platform/source such as `cli`, `telegram`, `discord`, etc.

Current live counts observed read-only on 2026-05-08 11:44 KST:

- sessions total: 143
- messages total: 10,443
- sessions by source:
  - `cli`: 119
  - `telegram`: 24

## Core schema

`hermes_state.py::SCHEMA_SQL` defines:

### `sessions`

Important columns:

- `id`
- `source`
- `user_id`
- `model`
- `model_config`
- `system_prompt`
- `parent_session_id`
- `started_at`
- `ended_at`
- `end_reason`
- `message_count`
- `tool_call_count`
- token counters: `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`, `reasoning_tokens`
- billing/cost fields: `billing_provider`, `billing_base_url`, `billing_mode`, `estimated_cost_usd`, `actual_cost_usd`, `cost_status`, `cost_source`, `pricing_version`
- `title`
- `api_call_count`

### `messages`

Important columns:

- `id`
- `session_id`
- `role`
- `content`
- `tool_call_id`
- `tool_calls`
- `tool_name`
- `timestamp`
- `token_count`
- `finish_reason`
- reasoning fields: `reasoning`, `reasoning_content`, `reasoning_details`, `codex_reasoning_items`, `codex_message_items`

### FTS tables

- `messages_fts`
- `messages_fts_trigram`

Triggers index message content, tool names, and tool calls.

## Session listing behavior

`SessionDB.list_sessions_rich` returns enriched session rows with:

- `preview`: first user message, truncated.
- `last_active`: latest message timestamp or `started_at` fallback.
- compression projection: roots whose `end_reason='compression'` can be projected to latest continuation tip.
- child/session filtering: subagents and compression continuations are hidden by default unless requested.
- optional sorting by last activity.

Dashboard endpoint `GET /api/sessions` uses this and marks recent active sessions if:

- `ended_at is None`, and
- now minus `last_active`/`started_at` is under roughly 300 seconds.

## Search behavior

`SessionDB.search_messages` supports:

- FTS5 keyword/phrase/boolean/prefix search for non-CJK.
- Trigram FTS5 for CJK queries with at least 3 CJK chars.
- LIKE fallback for 1–2 CJK chars.
- optional source, exclude-source, and role filters.

Returned search rows include:

- message id
- session id
- role
- snippet with `>>>` and `<<<` markers
- timestamp
- tool name
- session source
- model
- session started timestamp
- small surrounding context

Full raw message content is removed from search results before return.

## Dashboard session frontend

`web/src/pages/SessionsPage.tsx` already maps sources to icons for:

- `cli`
- `telegram`
- `discord`
- `slack`
- `whatsapp`
- `cron`

It renders message bubbles and tool-call JSON in detail views. This is valuable for existing session browser, but AI Office should not default to raw transcript display.

## Provenance fit

What exists now:

- `sessions.source` gives platform-level origin (`cli`, `telegram`, etc.).
- `sessions.user_id` can identify the user, depending on caller.
- `messages.tool_name` and `tool_calls` can explain what happened.
- parent/child session chains can represent compression, branches, subagents, or continuations.
- Gateway Telegram runtime source has chat/thread/user metadata before session processing.

What is missing for AI Office:

- No first-class `chat_id`, `thread_id`, `message_id`, `chat_topic`, or `platform_message_url` columns in `sessions`.
- No normalized join from a Kanban task to the session that created/dispatched/completed it.
- No safe public summary table separate from raw messages/tool args.
- Raw `system_prompt`, `tool_calls`, and message content may contain sensitive data.

## Privacy notes

AI Office should treat session DB as sensitive. Default display should use metadata only:

- source platform
- session title/preview after redaction
- model/provider
- started/last active time
- status active/ended
- counts and cost/usage summaries

Avoid showing by default:

- full user prompts
- system prompts
- tool args
- tool outputs
- reasoning fields
- secrets or paths that may reveal credentials

## Recommendation for Stage 4 provenance design

Add a read-only provenance projection, either as a new table or computed API, with rows like:

- `provenance_id`
- `session_id`
- `source_platform`
- `source_user_id`
- `source_chat_id`
- `source_thread_id`
- `source_message_id`
- `source_topic_label`
- `linked_task_ids`
- `linked_cron_job_ids`
- `created_at`, `last_active_at`
- `safe_summary`, optional and redacted

This projection should reference raw session data but not expose raw transcript fields by default.
