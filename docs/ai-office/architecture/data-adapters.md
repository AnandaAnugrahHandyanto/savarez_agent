# Hermes AI Office — Stage 5 Data Adapter Architecture

Last updated: 2026-05-08 12:17 KST
Status: Stage 5 technical architecture design. Documentation-only; no implementation approved.

## Purpose

This document defines the data adapter boundaries for the future read-only `OfficeState` API. Adapters isolate source-specific storage quirks from the browser DTO and enforce per-source failure semantics.

## Architecture summary

Recommended Stage 6 backend flow:

```text
OfficeStateService
  ├─ KanbanOfficeAdapter
  ├─ CronOfficeAdapter
  ├─ SessionOfficeAdapter
  ├─ TopicRegistryAdapter
  ├─ ProvenanceProjectionAdapter
  └─ RedactionSerializer
        ↓
  OfficeState DTO under /api/office/state
```

The browser should not call Kanban/Cron/Session raw endpoints and compose its own office model. Cross-source normalization belongs server-side.

## Shared adapter interface

Logical interface for every adapter:

```python
class OfficeAdapterResult(TypedDict):
    source: office_data_source
    rooms: list[office_room]
    agents: list[office_agent]
    work_items: list[office_work_item]
    automations: list[office_automation]
    topics: list[office_topic]
    events: list[office_event]
    provenance: list[office_provenance]
    redaction_notes: list[str]
```

Implementation can use dataclasses or Pydantic models, but all adapters should return the same categories so the aggregator can merge results without source-specific UI logic.

Required source status values:

- `ok`: source readable and fully projected.
- `partial`: source readable but some records omitted/redacted or one board/job failed.
- `missing`: expected source store does not exist yet.
- `unavailable`: dependency absent or source disabled.
- `error`: unexpected read/parsing error.

## Aggregator merge rules

1. Generate `OfficeState.generated_at` once at the aggregator layer.
2. Merge all adapter `data_sources[]` entries even when they fail.
3. De-duplicate by stable DTO ids, not by display names.
4. Compute summary counts after adapter results are merged.
5. Count unavailable/unknown provenance as warnings, not as absent work.
6. Run final redaction serialization on the merged DTO before returning it.

## Kanban adapter

### Source inputs

Current storage/API basis:

```text
~/.hermes/kanban/boards/<slug>/kanban.db
plugins/kanban/dashboard/plugin_api.py
hermes_cli/kanban_db.py
hermes_cli/kanban_diagnostics.py
```

Stage 6 should prefer direct Python/database helper reads over browser calls to unauthenticated plugin HTTP routes. If existing Kanban helper functions are reused, call them server-side and serialize only safe fields.

### Output mappings

Kanban board -> `office_room`:

```yaml
kind: kanban_board
display_name: board slug/name
counts: status counts from triage/todo/ready/running/blocked/done
warnings: compact diagnostic codes
```

Kanban task -> `office_work_item`:

Allowed fields:

- task id,
- title after redaction,
- status,
- board id,
- assignee after redaction,
- priority,
- timestamps,
- heartbeat timestamp,
- dependency counts,
- compact diagnostic badges,
- provenance ref if available.

Excluded fields:

- `body`,
- `result`,
- full `comments`,
- raw `latest_summary`,
- worker logs,
- raw event payloads,
- workspace paths unless redacted and explicitly needed.

Kanban events -> `office_event`:

Allowed:

- event id,
- task id,
- run id,
- kind,
- timestamp,
- safe status transition summary.

Excluded:

- raw event payload,
- command/tool output,
- stack traces beyond redacted code/summary.

Notification subscriptions -> delivery provenance:

- `kanban_notify_subs(platform, chat_id, thread_id)` maps to `subscribed_to` or `delivered_to` relation.
- It must not be treated as task origin.

### Failure behavior

- No board directory: `status=missing`, `item_count=0`, no fake boards.
- One board DB unreadable: `kanban` source becomes `partial` or `error` with a redacted summary; other boards still render if possible.
- Diagnostics read failure: keep tasks/rooms, add source warning and omit diagnostics.

## Cron adapter

### Source inputs

Current storage/API basis:

```text
~/.hermes/cron/jobs.json
~/.hermes/cron/output/<job_id>/*.md
cron/jobs.py
cron/scheduler.py delivery target parsing behavior
```

The Stage 6 adapter reads jobs and output artifact counts only. It must not run scheduler ticks, trigger jobs, pause/resume jobs, or read raw output content by default.

### Output mappings

Cron job -> `office_automation`:

Allowed fields:

- id,
- name after redaction,
- enabled,
- state,
- schedule kind/display,
- next run,
- last run,
- last status,
- redacted last error,
- redacted delivery error,
- output artifact count,
- `no_agent` flag,
- delivery topic refs if normalized.

Excluded fields:

- `prompt`,
- script content,
- raw script stdout/stderr,
- `context_from` injected output,
- model/provider/api settings if sensitive,
- workdir/script absolute paths except redacted short error summaries.

Delivery target -> `office_delivery_target` and provenance relation:

- `local` => local delivery target.
- bare `telegram` => home target if structured home-channel config is available; otherwise unknown home target.
- `telegram:<chat_id>:<thread_id>` => explicit delivery target with topic lookup.
- `origin` => delivery target copied from structured origin if present; otherwise `missing_reason=origin_missing`.
- comma-separated strings => multiple targets.

### Failure behavior

- Missing `jobs.json`: `cron` source `missing`, no automations.
- JSON parse error: `cron` source `error`, other sources still render.
- One malformed job: `cron` source `partial`, include a safe warning event if possible.
- Output directory unreadable: automation still renders with `output_artifact_count=null` and source warning.

## Session adapter

### Source inputs

Current storage/API basis:

```text
~/.hermes/state.db
hermes_state.py SessionDB
GET /api/sessions existing metadata endpoint
```

Stage 6 uses session metadata only. It should not read message bodies to build the default OfficeState. It can use counts and `sessions.source` structural metadata.

### Output mappings

Session metadata -> optional `office_work_item` or `office_event`:

Recommended Stage 6 default:

- represent recent/active sessions as `office_event` entries and provenance records,
- do not show every session as a work item unless it is active/recent enough to matter,
- use `sessions.source` for platform-level provenance only.

Allowed fields:

- session id in localhost/internal mode,
- source platform,
- model/provider if not secret-bearing,
- started/last active/ended timestamps,
- active/ended status,
- message/tool-call counts,
- token/cost summaries if already safe,
- title only if redaction tests are enabled and option allows it.

Excluded fields:

- raw messages,
- previews/snippets by default,
- system prompt,
- reasoning fields,
- tool args/output,
- full `model_config` if it contains internal endpoints/secrets.

### Failure behavior

- Missing `state.db`: `sessions` source `missing`.
- DB locked/unreadable: `sessions` source `error`, no transcript fallback.
- Redaction rejects all titles: keep session metadata and mark title omitted.

## Topic registry adapter

### Source inputs

Stage 5 recommendation for Stage 6:

1. Allow a profile-local, read-only seed registry file if it already exists:
   `~/.hermes/office/topics.json`.
2. Do not create/edit this file in Stage 6 unless separately approved.
3. Also compute unknown topic records from structural delivery/source ids seen in cron/Kanban/session provenance.
4. Treat memory/audit examples as seed candidates only, not code constants.

Recommended file shape if later implemented:

```json
{
  "schema_version": 1,
  "topics": [
    {
      "platform": "telegram",
      "chat_id": "-100...",
      "thread_id": 11,
      "display_name": "70-자동화",
      "purpose": "automation",
      "source": "manual_alias",
      "confidence": "manual"
    }
  ]
}
```

Server-side raw ids should be separated from browser display ids during serialization.

### Output mappings

Topic registry entry -> `office_topic` and `telegram_topic` room:

- known topic label => safe room/topic if label passes redaction,
- unknown topic id => fallback topic with `display_name=unknown` or `Telegram topic <thread>`, depending policy,
- label conflict => warning and `confidence=unknown` until reviewed.

### Failure behavior

- Registry absent: `topics` source `missing` or `partial` if topics were structurally observed elsewhere.
- Registry malformed: `topics` source `error`, but explicit delivery targets still render with unknown labels.
- Label redacted: topic remains with `display_name=redacted` and warning.

## Provenance projection adapter

### Stage 6 posture

Compute provenance in memory only. Do not persist backfilled provenance rows in Stage 6.

Allowed relations:

- `created_from`,
- `dispatched_from`,
- `continued_from`,
- `delivered_to`,
- `subscribed_to`,
- `triggered_by`,
- `reported_to`,
- `unknown`.

### Backfill rules

- Kanban legacy task with no source fields => `confidence=unknown`, `missing_reason=legacy_task` or `schema_missing_field`.
- Cron explicit delivery => `relation=delivered_to`, `confidence=observed` for destination only.
- Session `source=telegram` => source platform observed, topic/message unknown unless separately captured.
- Parent/child session chain => `continued_from`, not Telegram provenance.
- Never infer topic/session links from prompt/title/body/result/log/message content.

### Failure behavior

- Provenance projection should never make the entire API fail unless its code raises before returning a valid DTO.
- If a relation cannot be normalized, use `unknown` with safe `missing_reason`.

## Source health semantics table

| Source | Missing store | Partial read | Error | Browser behavior |
|---|---|---|---|---|
| Kanban | show source `missing`, no board rooms | render readable boards, warn | source `error`, keep other sections | never show board count as zero unless confirmed empty |
| Cron | show `No scheduled automations` only if file exists and empty; otherwise `missing` | render valid jobs, warn malformed ones | source `error` | failed source is not healthy automation count zero |
| Sessions | source `missing` | omit unsafe title/preview, keep metadata | source `error` | no transcript fallback |
| Topics | registry `missing`, but observed ids can become unknown topics | known + unknown labels mixed | registry `error`, explicit ids still unknown | no fabricated labels |
| Provenance | computed unknown | known/unknown mixed | source warning | missing provenance appears as `unknown` |

## Implementation notes for Stage 6

- Keep adapter functions deterministic and easy to unit test with temporary `HERMES_HOME` fixtures.
- Avoid network calls in adapters.
- Avoid service status mutations.
- Prefer small helpers with explicit input dictionaries over broad raw object passthrough.
- Use `get_hermes_home()` for profile-aware paths.
- Redact before returning from every endpoint, even if adapters believe fields are safe.
