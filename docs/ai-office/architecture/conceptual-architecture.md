# Hermes AI Office — Conceptual Architecture

Last updated: 2026-05-08 11:32 KST
Status: Architecture planning artifact. No implementation approved.

## Core principle

Hermes AI Office is a read-only observability sidecar over real Hermes state. It must not become a second task database, second chat UI, or fabricated simulation.

## Source-of-truth layers

```text
Hermes runtime state
  ├─ Kanban boards/tasks/events/runs/comments
  ├─ Cron jobs/runs/delivery targets
  ├─ Gateway platform/session metadata
  ├─ Telegram topic registry/mapping
  ├─ Session metadata/provenance links
  └─ STATUS/NEXT handoff docs
          ↓
Read-only adapters
          ↓
Normalized OfficeState DTO
          ↓
Dashboard APIs
          ↓
React office views
          ├─ Table/card operational view (MVP)
          └─ Pixel-office renderer (later)
```

## Normalized `OfficeState` concept

Candidate shape, not implementation:

```yaml
office_state:
  generated_at: timestamp
  health:
    data_sources:
      kanban: ok | unavailable | error
      cron: ok | unavailable | error
      topics: ok | missing | error
  boards:
    - id: hermes-runtime
      name: Hermes Runtime
      counts:
        blocked: 2
        ready: 0
        running: 0
        done: 3
      tasks: [safe_task_summary]
  tasks:
    - id: string
      title: safe string
      board: string
      status: blocked | ready | running | done | todo | unknown
      assignee: optional string
      source: optional safe provenance summary
      delivery: optional safe destination summary
      timestamps: safe timestamps
      flags: [blocked, needs_user, stale, cron_related]
  cron_jobs:
    - id: string
      name: string
      schedule: string
      status: ok | failed | timed_out | unknown
      last_run: optional timestamp
      next_run: optional timestamp
      delivery_topic: optional safe topic display
  topics:
    - platform: telegram
      chat_id_hash_or_safe_id: string
      thread_id: number
      name: string
      purpose: string
```

## Adapter responsibilities

### Kanban adapter

- List boards and counts.
- List safe task summaries.
- Read dependencies/events if available.
- Do not mutate tasks.

### Cron adapter

- List jobs and statuses.
- Include schedule, last/next run, delivery target.
- Redact prompt/script contents unless explicitly designed safe.

### Topic registry adapter

- Resolve `telegram:chat_id:thread_id` into friendly topic labels.
- Start with known local mapping or config-derived mapping after design approval.
- Do not hardcode user-specific IDs in core code.

### Session/provenance adapter

- Link task/session ids where safe.
- Expose only metadata required for navigation and provenance.
- Do not expose raw transcript content in MVP.

## Dashboard API posture

Candidate endpoints for Stage 5 design, not implementation:

- `GET /api/office/state`
- `GET /api/office/boards`
- `GET /api/office/tasks?board=&status=&assignee=`
- `GET /api/office/tasks/{task_id}`
- `GET /api/office/tasks/{task_id}/events`
- `GET /api/office/cron/jobs`
- `GET /api/office/topics`

Live updates can be deferred. Initial MVP can poll or refresh manually.

## Frontend posture

MVP components, not implementation:

- `OfficePage`
- `OfficeSummaryStrip`
- `BoardRoomList`
- `TaskStatusTable`
- `TaskCard`
- `AutomationPanel`
- `TopicMapPanel`
- `TaskInspectorDrawer`

Later pixel components:

- `PixelOfficeCanvas`
- `RoomLayer`
- `AgentCharacter`
- `TaskDesk`
- `CronRobot`

## Security posture

- Localhost-first.
- Dashboard auth must match existing Hermes dashboard auth model.
- No secrets, `.env`, `auth.json`, credential pools, raw tool arguments, or raw transcripts in MVP.
- Browser mutations are explicitly out of scope until separate security review.

## Testing posture

When implementation is later approved:

- Use `scripts/run_tests.sh`, not direct pytest.
- Add serializer redaction tests first.
- Add API tests for unavailable data sources.
- Add frontend typecheck/build with Linux Node path in WSL if needed.
- Avoid brittle visual snapshot tests.

## Architecture decision recommendation

The first implementation should add a normalized read-only data layer and non-pixel operational view. The pixel renderer should consume the same `OfficeState` DTO later, not reach into Kanban/cron/session internals directly.
