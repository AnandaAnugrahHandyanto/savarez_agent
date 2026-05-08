# Hermes AI Office — Stage 4 Task/Session/Cron Provenance Metadata

Last updated: 2026-05-08 12:05 KST
Status: Stage 4 provenance/routing design. Documentation-only; no implementation approved.

## Purpose

This document defines the logical provenance metadata needed for `OfficeState` to answer where work came from and where it delivers output, without exposing raw prompts, transcripts, tool calls, logs, or secrets.

The design covers:

- Kanban task origin and delivery/subscription metadata.
- Session origin metadata.
- Cron origin and delivery routing metadata.
- Source/delivery normalization across CLI, Telegram, cron, dashboard, and Kanban worker flows.

## Source basis

Stage 2 audits found:

- Kanban tasks have workflow fields and event/run tables, but no first-class `source_chat_id`, `source_thread_id`, `source_message_id`, or `source_session_id` columns.
- Cron jobs store `deliver`, `origin`, `script`, `no_agent`, `context_from`, state, and error fields in JSON.
- Sessions store `source` and `user_id`, but not normalized chat/thread/message/topic fields.
- Telegram gateway runtime source objects contain rich source metadata before it is normalized into sessions/tasks.

Stage 3 requires missing provenance to render as `unknown`, not inferred.

## Core model

Proposed logical record:

```yaml
office_provenance_record:
  id: "prov:<source_kind>:<source_id>[:<relation>]"
  subject_kind: "kanban_task|session|cron_job|cron_run|automation|unknown"
  subject_id: "source object id"
  relation: "created_from|dispatched_from|continued_from|delivered_to|subscribed_to|triggered_by|reported_to|unknown"
  created_via: "cli|telegram|cron|kanban_worker|dashboard|api|system|unknown"
  source:
    platform: "cli|telegram|cron|dashboard|kanban|unknown"
    user_display: "optional redacted label"
    user_id_display: "optional internal/hash/hidden"
    topic_ref: "optional office_topic id"
    chat_id_display: "optional internal/hash/hidden"
    thread_id_display: "optional internal/hash/hidden"
    message_id_display: "optional internal/hash/hidden"
    session_id: "optional session id"
  delivery:
    targets: [office_delivery_target]
    origin_preserved: true
    warning: "optional safe warning"
  linked:
    session_ids: []
    task_ids: []
    cron_job_ids: []
    cron_run_ids: []
  timestamps:
    created_at: "optional timestamp"
    last_active_at: "optional timestamp"
    last_delivered_at: "optional timestamp"
  confidence: "observed|derived|manual|unknown"
  missing_reason: "optional safe reason code"
  redaction:
    omitted: ["message_text", "tool_args", "cron_prompt"]
```

Only a safe projection should reach the browser.

## Delivery target model

```yaml
office_delivery_target:
  id: "delivery:telegram:<chat_key>:<thread_key>"
  platform: "telegram|discord|slack|local|origin|unknown"
  target_kind: "home|explicit|origin|local|topic|dm|channel|unknown"
  topic_ref: "optional office_topic id"
  chat_id_display: "optional internal/hash/hidden"
  thread_id_display: "optional internal/hash/hidden"
  display_name: "safe label or unknown"
  confidence: "observed|derived|manual|unknown"
  source_field: "cron.deliver|cron.origin|kanban_notify_subs|gateway_source|config_home_channel|unknown"
```

## Source normalization

Normalize every source into this common shape before mapping to `OfficeState`:

```yaml
normalized_source:
  created_via: "cli|telegram|cron|kanban_worker|dashboard|api|system|unknown"
  source_platform: "cli|telegram|cron|dashboard|kanban|unknown"
  source_topic_ref: "optional office_topic id"
  source_session_id: "optional session id"
  source_user_display: "optional redacted"
  source_message_id_display: "optional"
  confidence: "observed|derived|manual|unknown"
```

Rules:

- `observed`: captured directly from runtime metadata or existing explicit field.
- `manual`: user-approved registry/provenance alias.
- `derived`: inferred only from non-content structural fields, e.g. cron `deliver=telegram:<chat>:<thread>` or `sessions.source=telegram`.
- `unknown`: missing or unsafe to expose.

Never derive provenance from raw prompt/message content in MVP.

## Kanban task provenance

### Desired future fields

A future implementation may store task provenance separately from the raw `tasks` table:

```yaml
kanban_task_provenance:
  board_id: "board slug"
  task_id: "task id"
  created_via: "cli|telegram|dashboard|cron|kanban_worker|unknown"
  source_platform: "optional"
  source_session_id: "optional"
  source_topic_ref: "optional"
  source_chat_id_internal: "server-side only"
  source_thread_id_internal: "server-side only"
  source_message_id_internal: "server-side only"
  source_user_id_internal: "server-side only"
  delivery_targets: [office_delivery_target]
  confidence: "observed|derived|manual|unknown"
  missing_reason: "legacy_task|not_captured|redacted|unknown"
  created_at: "timestamp"
  updated_at: "timestamp"
```

### MVP projection before capture exists

For current tasks without provenance:

- Use task id/board/status safely.
- `created_via` may be `unknown` unless `created_by` is a safe structural indicator.
- `source_topic_ref = null`.
- Add `flags: [unknown_provenance]` when useful.
- `missing_reason = legacy_task` or `not_captured`.

Do not place tasks into Telegram rooms based on title/body text.

## Session provenance

Current sessions provide:

- `sessions.id`
- `sessions.source`
- `sessions.user_id`
- timestamps/counts/model/cost/title

Desired safe projection:

```yaml
session_provenance:
  session_id: "id"
  created_via: "cli|telegram|cron|unknown"
  source_platform: "sessions.source"
  source_user_display: "redacted or hidden"
  source_topic_ref: "optional, only if captured separately"
  title_display: "optional, redacted"
  preview_display: "deferred by default"
  started_at: "timestamp"
  last_active_at: "timestamp"
  message_count: 0
  tool_call_count: 0
  confidence: "observed|derived|unknown"
```

Display policy:

- Source platform and timestamps are safe.
- Session id is internal metadata; local mode may show it.
- Title/preview should remain off by default until redaction tests exist.
- Raw messages, system prompts, tool args/output, reasoning, and full snippets are excluded.

## Cron provenance and delivery

Cron jobs should map to automation provenance, not task provenance by default.

```yaml
cron_provenance:
  job_id: "job id"
  name: "safe job name"
  created_via: "cron|cli|unknown"
  origin: normalized_source
  delivery_targets: [office_delivery_target]
  schedule_kind: "cron|interval|once|unknown"
  no_agent: true|false
  last_run_at: "timestamp"
  last_status: "ok|error|unknown"
  last_error_summary: "redacted"
  confidence: "observed|derived|unknown"
```

Delivery parsing rules:

- `local`: target kind `local`; no topic.
- bare platform such as `telegram`: target kind `home`; resolve through home-channel config if available, otherwise unknown delivery target.
- explicit platform target such as `telegram:<chat_id>:<thread_id>`: parse into platform/chat/thread and link topic registry if possible.
- `origin`: copy source topic from job origin when present; if origin had a thread and target loses it, expose a safe warning such as `origin_thread_lost`.
- comma-separated delivery: normalize into multiple `office_delivery_target` records.

Do not display prompt/script/context/output content.

## Relationship types

Use explicit relation names so UI can distinguish origin from destination:

| Relation | Meaning | Example |
|---|---|---|
| `created_from` | subject was created because of source | Telegram message created a task |
| `dispatched_from` | worker/run started from another source | Kanban worker launched task from board |
| `continued_from` | session continuation/compression/branch | parent session chain |
| `delivered_to` | output/report sent to destination | cron health digest delivered to Telegram topic |
| `subscribed_to` | updates for subject go to destination | Kanban notify subscription |
| `triggered_by` | run was caused by actor/source | future manual cron trigger |
| `reported_to` | health/status report target | automation topic |
| `unknown` | no reliable relation | legacy task |

## Storage recommendation for Stage 5

Preferred design direction:

1. Keep provenance as a separate projection/table/file rather than stuffing raw metadata into task body/result/comment fields.
2. Use server-side internal ids for joins, and redacted display ids for browser output.
3. Let Stage 6 read existing data and show unknowns; let Stage 7 implement capture/backfill after separate approval.
4. Keep raw transcripts/logs as references only, never copied into provenance rows.

Candidate physical locations:

| Subject | Candidate storage | Recommendation |
|---|---|---|
| Sessions | `state.db` side table keyed by session id | Strong candidate if adding migrations is acceptable |
| Kanban tasks | per-board `kanban.db` side table keyed by task id, or profile-level provenance DB keyed by board/task | Decide in Stage 5; avoid body/comment overloading |
| Cron jobs | `jobs.json` structured fields or profile-level provenance DB keyed by job id | Prefer projection first; mutate jobs only in Stage 7+ |
| Topics | registry file/table | See topic registry spec |

## Stage 5 decisions needed

1. Which physical store owns `office_provenance`?
2. Does Stage 6 only compute provenance, or can it read a seed registry/provenance file?
3. What migrations are acceptable for Stage 7 provenance capture?
4. Should task/session links be many-to-many from the beginning?
5. Which fields are required vs optional in API responses?
6. Which source fields get tests for unknown/missing behavior?
