# Hermes AI Office — Stage 4 Provenance Backfill Strategy

Last updated: 2026-05-08 12:05 KST
Status: Stage 4 provenance/routing design. Documentation-only; no implementation approved.

## Purpose

Existing Hermes state was not originally designed around AI Office provenance. Stage 4 therefore needs a backfill strategy that improves display usefulness without fabricating source links.

Backfill here means read-only classification/projection first. Writing backfilled metadata into databases/files belongs to a later implementation stage and requires explicit approval.

## Backfill principles

1. Prefer honest `unknown` over plausible but unverified links.
2. Derive only from structural metadata, never from raw prompt/message/log content in MVP.
3. Preserve confidence and missing reason for every backfilled record.
4. Keep source and delivery separate.
5. Do not mutate Kanban, cron, session DB, gateway config, or topic registry during Stage 4.
6. Make legacy gaps visible enough that Stage 7 capture work is well-scoped.

## Confidence levels

| Confidence | Definition | Example |
|---|---|---|
| `observed` | Direct field/runtime metadata exists and maps structurally | cron `deliver=telegram:<chat>:<thread>`; session `source=telegram` for platform only |
| `manual` | User-approved alias/provenance entry exists | future topic alias `70-자동화` |
| `derived` | Structural inference from safe fields, not content | `sessions.source=telegram` means platform is Telegram but topic unknown |
| `unknown` | No reliable metadata or unsafe to expose | legacy Kanban task with no source fields |

`derived` must not imply a topic/session/task link unless the exact key exists.

## Missing reasons

Use stable reason codes instead of prose where possible:

- `legacy_task`: task predates provenance capture.
- `schema_missing_field`: current schema lacks needed source field.
- `not_captured`: runtime had data, but no persistence path was present.
- `source_unavailable`: source DB/file/config could not be read.
- `redacted`: data exists but is unsafe to display.
- `registry_missing`: topic id exists but no label/alias exists.
- `delivery_unparseable`: delivery string could not be normalized.
- `origin_missing`: cron origin is absent or incomplete.
- `unknown`: no specific reason.

## Backfill by source

### Kanban tasks

Current reliable fields:

- board slug/db location,
- task id/title/status/assignee/priority/timestamps,
- `created_by` if present,
- task events/runs/diagnostics,
- notify subscriptions `(platform, chat_id, thread_id)` if present.

Backfill rules:

1. Create `office_work_item` from safe task metadata.
2. If `kanban_notify_subs` has a platform/chat/thread tuple, create a `subscribed_to` or `delivered_to` delivery provenance relation with `confidence=observed` for the destination only.
3. Do not treat notification destination as task origin.
4. If `created_by` is a safe structural value such as `kanban_worker` or `dashboard`, map `created_via` with `confidence=derived`; otherwise keep unknown.
5. If events/runs reference a run id, use it for activity linkage, not source topic inference.
6. Do not inspect task body/result/comments/logs to derive source in MVP.
7. Set `unknown_provenance` flag when no origin relation exists.

Fallback example:

```yaml
provenance:
  subject_kind: kanban_task
  subject_id: "<task_id>"
  relation: created_from
  created_via: unknown
  confidence: unknown
  missing_reason: legacy_task
```

### Sessions

Current reliable fields:

- session id,
- `source` platform,
- `user_id` internal field,
- timestamps/counts/model/title,
- parent session chain.

Backfill rules:

1. Map `sessions.source` to `source_platform` with `confidence=observed` for platform only.
2. If `source=telegram` but no chat/thread fields exist, set topic/message fields unknown with `missing_reason=schema_missing_field`.
3. Use parent/child session ids for `continued_from` only; do not infer Telegram topic from parent title/preview.
4. Titles/previews remain excluded or redacted unless Stage 5 approves a tested redaction policy.
5. Raw messages/tool calls/reasoning are never used for display backfill.

### Cron jobs

Current reliable fields:

- job id/name,
- schedule kind/display,
- enabled/state/last status/error,
- `deliver`,
- `origin` when present,
- output file count/path metadata.

Backfill rules:

1. Parse `deliver` into `office_delivery_target[]`.
2. Link explicit Telegram delivery targets to topic registry by `(platform, chat_id, thread_id)` if available.
3. If registry lacks label, keep destination relation but show unknown/id-safe fallback.
4. For `deliver=origin`, use `origin` only when structured origin exists; otherwise set `origin_missing`.
5. Store/display `last_error_summary` after redaction; do not read raw output content by default.
6. Do not infer job purpose from prompt/script text.

Example for current audited health digest:

```yaml
subject_kind: cron_job
subject_id: "70378c4d2890"
relation: delivered_to
created_via: cron
source:
  platform: cron
delivery:
  targets:
    - platform: telegram
      thread_id_display: "11"
      topic_ref: "if registry resolves it"
confidence: observed
```

The timeout error should surface as automation health, not provenance failure.

### Telegram topics

Current reliable inputs:

- gateway runtime `source` object when observed,
- cron explicit delivery strings,
- home-channel config and Kanban home-channel endpoint,
- known audit/memory examples as planning seeds.

Backfill rules:

1. Cron delivery can identify an unknown topic destination even without a label.
2. Home channel config can identify a known target if read safely by a future implementation.
3. Runtime observed `chat_topic` may update label only if persisted through an approved registry/capture path later.
4. Memory/audit examples must be marked `memory_import` or seed candidates; do not silently treat them as canonical product constants.

## Backfill stages

### Stage 6 read-only MVP backfill

Allowed if implementation is later approved:

- Compute backfill in memory while building `OfficeState`.
- Return confidence/missing_reason in API response.
- Do not write back to source DBs/files.
- Serialize only safe fields.

### Stage 7 provenance capture/backfill implementation

Requires separate approval:

- Add persistence for future provenance capture.
- Optionally write reviewed manual aliases or backfill rows.
- Add migrations/tests.
- Possibly expose a reviewed admin/import path.

## What not to backfill

Do not backfill:

- raw Telegram message text,
- raw user prompts,
- session snippets unless redaction-tested,
- tool arguments/output,
- reasoning/system prompts,
- cron prompt/script/context/output,
- worker logs,
- credentials/tokens,
- source links derived from keyword matching task titles or message text.

## UI behavior for unknown backfill

The MVP should show:

- `Unknown source` for missing origin.
- `Unknown topic` for unregistered topic id.
- `Destination known, origin unknown` when only cron delivery/notify subscription exists.
- `Legacy item — provenance was not captured` for old tasks.
- Per-source warnings rather than zero counts.

## Test expectations for later implementation

Future tests should prove:

1. A task with no provenance fields produces `confidence=unknown` and a missing reason.
2. A cron explicit Telegram delivery parses into a delivery target without exposing raw prompt/script/output.
3. A session with `source=telegram` but no thread field does not invent a topic.
4. A topic id without registry label renders unknown/id-safe fallback.
5. Redacted fields are absent from `OfficeState` serialization.
6. Data-source read failure changes only that source status and does not blank the entire office state.

## Stage 5 decisions needed

1. Should Stage 6 backfill be purely computed, or read from an optional seed registry?
2. Which missing reason codes become part of the public API contract?
3. How much source id detail is allowed in local mode by default?
4. Which backfill outputs should be persisted later in Stage 7?
5. Which fixtures should represent legacy unknown provenance in tests?
