# Hermes AI Office — Stage 3 OfficeState Model and Redaction Boundaries

Last updated: 2026-05-08 11:54 KST
Status: Stage 3 architecture/product model. Documentation-only; no implementation approved.

## Purpose

`OfficeState` is the proposed normalized read-only projection that lets a future dashboard render Hermes work as rooms, agents, work items, automation, topics, and events without reaching directly into every source table/file from the browser.

It is not a new source of truth. It is an aggregation/projection over existing Hermes state.

## Source-of-truth inputs

| Source | Current storage/API | MVP posture |
|---|---|---|
| Dashboard backend | FastAPI routes in `hermes_cli/web_server.py` | Reuse existing dashboard/auth/client patterns later |
| Kanban | SQLite boards under `~/.hermes/kanban/boards/<slug>/kanban.db`; plugin API under `/api/plugins/kanban` | Strongest work-state source |
| Cron | `~/.hermes/cron/jobs.json` plus output files | Automation health source |
| Telegram topics | Gateway runtime `source`, cron delivery strings, home-channel config/memory | Needs registry/provenance design |
| Sessions | `~/.hermes/state.db` sessions/messages | Metadata only by default |
| Handoff docs | `docs/ai-office/STATUS.md`, `NEXT.md` | Optional future read-only panel, not startup dependency |

## Top-level object

```yaml
office_state:
  schema_version: 1
  generated_at: "timestamp"
  mode: "read_only"
  data_sources: [office_data_source]
  summary: office_summary
  rooms: [office_room]
  agents: [office_agent]
  work_items: [office_work_item]
  automations: [office_automation]
  topics: [office_topic]
  events: [office_event]
  provenance: [office_provenance]
  redactions: office_redaction_report
```

Field rules:

- `schema_version`: required; lets later frontend/pixel renderer know the DTO contract.
- `generated_at`: required; safe timestamp.
- `mode`: always `read_only` for MVP.
- Arrays may be empty, but unavailable sources must be represented in `data_sources` rather than silently omitted.

## `office_data_source`

```yaml
office_data_source:
  id: "kanban|cron|sessions|topics|handoff_docs"
  status: "ok|partial|missing|unavailable|error"
  checked_at: "timestamp"
  item_count: 0
  warning_count: 0
  error_summary: "optional redacted string"
```

Redaction rules:

- Safe: source id/status/counts/timestamps.
- Redacted: file paths only if they reveal secrets; stack traces truncated; no tokens/env values.

## `office_summary`

```yaml
office_summary:
  running_count: 0
  blocked_count: 0
  ready_count: 0
  todo_count: 0
  done_recent_count: 0
  failed_automation_count: 0
  unknown_provenance_count: 0
  needs_attention_count: 0
```

Computation rules:

- `blocked_count`: Kanban `blocked` plus severe diagnostics.
- `failed_automation_count`: cron jobs where `last_status=error`, `state=error`, or redacted last error exists.
- `unknown_provenance_count`: work items/automations with no normalized topic/session/source link.
- Missing source must produce `unknown`/source warning, not zero.

## `office_room`

Rooms are visible places in the office metaphor. MVP rooms should be list/card concepts, not necessarily pixel rooms yet.

```yaml
office_room:
  id: "string"
  kind: "kanban_board|telegram_topic|system_area|unknown"
  display_name: "safe string"
  purpose: "operations|automation|project|content|runtime|ledger|unknown"
  source_ref: "safe source id"
  counts:
    running: 0
    blocked: 0
    ready: 0
    todo: 0
    done: 0
  topic_ref: "optional office_topic id"
  warnings: ["safe warning code"]
```

Safe examples from audit:

- Kanban board room: `hermes-runtime`.
- Kanban board room: `koreandeer-content`.
- Kanban board room: `obsidian-ledger`.
- Telegram topic room: `00-운영실` / thread `2` when resolved through a future registry.
- Telegram topic room: `70-자동화` / thread `11` when resolved through a future registry.

Do not hardcode these audit examples in product code later; they are planning examples.

## `office_agent`

```yaml
office_agent:
  id: "string"
  kind: "kanban_assignee|cron_automation|gateway|human|unknown"
  display_name: "safe string"
  status: "active|idle|blocked|unknown"
  room_refs: ["office_room id"]
  work_item_refs: ["office_work_item id"]
```

Redaction rules:

- Safe: assignee/profile names already visible in Kanban if not secret-like.
- Redact or hash: user ids, chat ids, process ids if a public/remote mode is ever designed.
- Do not infer an agent's intention beyond actual fields/status.

## `office_work_item`

```yaml
office_work_item:
  id: "string"
  source_kind: "kanban_task|session|unknown"
  source_id: "string"
  title: "safe string"
  status: "triage|todo|ready|running|blocked|done|archived|unknown"
  board_id: "optional string"
  room_ref: "optional office_room id"
  assignee_ref: "optional office_agent id"
  priority: "optional safe string"
  created_at: "optional timestamp"
  updated_at: "optional timestamp"
  last_heartbeat_at: "optional timestamp"
  flags: ["needs_user|stale|diagnostic|has_dependencies|unknown_provenance"]
  diagnostics: [office_diagnostic]
  dependency_counts:
    parents: 0
    children: 0
  provenance_ref: "optional office_provenance id"
```

Default excluded Kanban fields:

- `body`
- `result`
- full `comments`
- worker logs
- raw event payloads
- full `latest_summary`
- stack traces beyond compact diagnostic summaries

Title safety:

- Task titles are probably acceptable for local MVP, but serializers should still pass through a redaction filter for obvious secrets, tokens, emails, phone numbers, and file paths under sensitive directories.

## `office_automation`

```yaml
office_automation:
  id: "string"
  source_kind: "cron_job"
  source_id: "job id"
  name: "safe string"
  enabled: true
  state: "scheduled|running|completed|error|disabled|unknown"
  schedule_kind: "cron|interval|once|unknown"
  schedule_display: "safe string"
  last_run_at: "optional timestamp"
  next_run_at: "optional timestamp"
  last_status: "ok|error|unknown"
  last_error_summary: "optional redacted string"
  last_delivery_error_summary: "optional redacted string"
  delivery_topic_refs: ["office_topic id"]
  output_artifact_count: 0
  flags: ["failed|timed_out|delivery_failed|no_agent|unknown_delivery"]
```

Default excluded cron fields:

- `prompt`
- full script contents
- raw script output
- `context_from` injected content
- model/API settings if they reveal credentials or internal endpoints
- absolute output file contents

Allowed cron display examples:

- `daily-hermes-health-digest`
- schedule `0 8 * * *`
- next run timestamp
- redacted timeout summary such as `Script timed out after 120s`

## `office_topic`

```yaml
office_topic:
  id: "telegram:<chat_hash_or_safe_id>:<thread_id>"
  platform: "telegram"
  chat_id_display: "internal id or hash depending mode"
  thread_id: 0
  display_name: "safe string or unknown"
  purpose: "operations|automation|project|unknown"
  source: "config|home_channel|observed_event|manual_alias|memory_import|unknown"
  last_observed_at: "optional timestamp"
```

MVP display posture:

- Localhost MVP may show internal chat/thread ids if useful, but still label them internal.
- A later remote mode should hash chat ids by default and show names/purposes only.
- Raw Telegram message text is not part of `office_topic`.

## `office_event`

```yaml
office_event:
  id: "string"
  source_kind: "kanban_event|cron_run|session_activity|gateway_event|unknown"
  source_id: "string"
  occurred_at: "timestamp"
  severity: "info|warning|error"
  actor_ref: "optional office_agent id"
  room_ref: "optional office_room id"
  work_item_ref: "optional office_work_item id"
  automation_ref: "optional office_automation id"
  kind: "safe event kind"
  summary: "redacted safe string"
```

Redaction rules:

- Event `kind`, timestamps, ids, status transitions, and compact diagnostic codes are safe.
- Event payloads, tool args, command output, message text, and stack traces are not safe by default.

## `office_provenance`

```yaml
office_provenance:
  id: "string"
  created_via: "cli|telegram|cron|kanban_worker|dashboard|unknown"
  source_platform: "optional string"
  source_user_display: "optional redacted string"
  source_topic_ref: "optional office_topic id"
  source_session_id: "optional string"
  source_message_id_display: "optional string"
  linked_work_item_ids: ["office_work_item id"]
  linked_automation_ids: ["office_automation id"]
  created_at: "optional timestamp"
  last_active_at: "optional timestamp"
  confidence: "observed|derived|manual|unknown"
  missing_reason: "optional safe string"
```

Important: current Stage 2 audits show many provenance fields are missing in existing session/Kanban schemas. MVP must show `unknown` honestly rather than fabricating links.

## Redaction classification

| Data category | Default MVP display | Rationale |
|---|---|---|
| Board id/name | Show | Operational label, already visible in Kanban UI |
| Task id/title/status/assignee | Show after redaction pass | Needed for usefulness |
| Task body/result/comments | Hide by default | May contain prompts/private content |
| Task logs/tool output | Hide by default | High leakage risk |
| Kanban event kind/status transition | Show | Useful safe operational metadata |
| Raw Kanban event payload | Hide/summarize | May contain content/tool output |
| Cron name/schedule/state/last status | Show | Required automation health metadata |
| Cron prompt/script/context/output | Hide by default | May contain sensitive instructions/data |
| Cron last error | Redacted summary | Needed for health, but stack traces/paths may leak |
| Delivery platform/topic label | Show | Needed routing context |
| Chat id/thread id | Local-only internal display or hash | Internal routing metadata |
| Telegram message text | Hide | Private/source content |
| Session id/source/title/timestamps/counts | Show after redaction pass | Useful provenance metadata |
| Session raw messages/tool calls/reasoning/system prompt | Hide | Sensitive by default |
| `.env`, `auth.json`, tokens, credential pools | Never show | Secrets |
| Absolute paths under home/cache/logs | Show only if needed and redacted | Can reveal private structure |

## Redaction report

Every `OfficeState` response should include a lightweight report:

```yaml
office_redaction_report:
  policy_version: 1
  redacted_field_count: 0
  omitted_sections: ["session_messages", "cron_prompt", "task_logs"]
  warnings: ["safe strings"]
```

This makes privacy behavior explicit and testable in Stage 6.

## Stage 4 design questions this model leaves open

1. Where does the topic registry live?
2. Where does normalized task/session provenance live?
3. Should chat ids be shown, hashed, or label-only in localhost mode?
4. Can session titles/previews be safely redacted enough for MVP?
5. Which data-source failures should block the page versus appear as source warnings?
