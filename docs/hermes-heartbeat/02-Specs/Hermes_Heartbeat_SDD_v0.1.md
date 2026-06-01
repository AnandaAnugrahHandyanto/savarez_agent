# SDD Spec: Hermes Heartbeat Plugin v0.1

## Goal

Implement a lightweight Heartbeat plugin for Hermes-agent that periodically wakes the agent, provides a bounded context pack, asks it to check for actionable items, and suppresses no-op responses.

The goal is proactive awareness, not autonomous action.

## Non-Goals

- Do not modify Hermes core unless required.
- Do not implement full background autonomy.
- Do not perform destructive actions.
- Do not load full chat history.
- Do not notify the user unless there is clear, timely, actionable value.

## User Story

As a Hermes user, I want my agent to periodically check current state, tasks, memory, and configured sources so it can proactively surface important follow-ups while staying silent when nothing matters.

## Configuration

Add plugin config:

```yaml
heartbeat:
  enabled: false
  interval_minutes: 30
  timezone: "Asia/Manila"

  active_hours:
    enabled: true
    start: "08:00"
    end: "22:00"

  jitter_minutes: 5
  suppress_token: "HEARTBEAT_OK"

  max_runtime_seconds: 90
  max_tokens: 4000
  max_notifications_per_day: 6
  cooldown_after_notification_minutes: 60

  context:
    include:
      - current_time
      - heartbeat_instructions
      - active_tasks
      - recent_memory_delta
      - unresolved_promises
    exclude:
      - full_chat_history
      - large_documents
      - archived_context
```

## Required File

Support an optional `HEARTBEAT.md` in the agent workspace.

Default behavior if missing:

```md
Return HEARTBEAT_OK if there is no useful, timely, actionable update.
Never invent urgency.
Never perform irreversible actions without explicit user approval.
Batch related findings.
Keep responses short.
```

## Behavior

On each heartbeat:

1. Check whether heartbeat is enabled.
2. Respect active hours and timezone.
3. Apply jitter to avoid robotic timing.
4. Build a lightweight context pack.
5. Inject a synthetic heartbeat turn into the normal Hermes agent loop.
6. If response equals `HEARTBEAT_OK`, suppress user notification.
7. If response is not suppressed, enforce cooldown and daily notification cap.
8. Log heartbeat result.

## Synthetic Prompt

```text
[HEARTBEAT]

This is a scheduled awareness pulse.

Read HEARTBEAT.md if present.
Use only the provided lightweight context.
Look for timely, useful, actionable items.

If nothing needs user attention, return exactly:
HEARTBEAT_OK

Do not browse or call expensive tools unless explicitly allowed by heartbeat config.
Do not perform destructive actions.
Do not create tasks, send messages, or mutate files without approval.
```

## Context Pack Contract

The heartbeat context pack must be small and explicit.

Required fields:

```json
{
  "event_type": "heartbeat",
  "current_time": "...",
  "timezone": "...",
  "instructions": "...",
  "active_tasks": [],
  "recent_memory_delta": [],
  "unresolved_promises": [],
  "budgets": {
    "max_runtime_seconds": 90,
    "max_tokens": 4000
  }
}
```

If a source is unavailable, include an empty list and a short diagnostic in logs only.

## Notification Policy

Notify only when at least one is true:

- A deadline or scheduled event is approaching.
- A previous user request is blocked or stale.
- A promised follow-up has not happened.
- A watched source changed in a meaningful way.
- The agent detects a concrete risk or opportunity.

Do not notify for:

- Generic status.
- Low-confidence speculation.
- Repeated reminders inside cooldown.
- “Nothing changed.”

## Logging

Each heartbeat run should log:

```json
{
  "timestamp": "...",
  "status": "suppressed|notified|skipped|error",
  "reason": "...",
  "duration_ms": 0,
  "tokens_estimated": 0,
  "notification_sent": false
}
```

## Acceptance Criteria

- Heartbeat can be enabled or disabled via config.
- Heartbeat respects active hours.
- Heartbeat injects a synthetic agent turn without requiring manual user input.
- `HEARTBEAT_OK` responses are suppressed.
- Non-suppressed responses are subject to cooldown and daily caps.
- Heartbeat does not load full chat history.
- Heartbeat runs with bounded runtime and token budget.
- Plugin works without `HEARTBEAT.md` using safe defaults.
- Unit tests cover config parsing, active-hours logic, suppression, cooldown, daily cap, and missing `HEARTBEAT.md`.
- Integration test proves one heartbeat run can execute end-to-end with a fake agent response.

## Implementation Plan

### Phase 1: Skeleton

- Create Hermes plugin named `heartbeat`.
- Add config model and defaults.
- Add scheduler loop.
- Add lifecycle startup/shutdown hooks.

### Phase 2: Execution

- Implement heartbeat event creation.
- Implement context pack builder.
- Inject synthetic prompt into existing agent run mechanism.
- Capture response.

### Phase 3: Suppression and Budgets

- Suppress exact `HEARTBEAT_OK`.
- Add runtime timeout.
- Add cooldown.
- Add max notifications per day.
- Add structured logs.

### Phase 4: Tests and Docs

- Add unit tests.
- Add one fake-agent integration test.
- Add README with config example.
- Add sample `HEARTBEAT.md`.

## Test Matrix

| Case | Expected Result |
|---|---|
| `enabled: false` | no heartbeat scheduled |
| outside active hours | skipped |
| missing `HEARTBEAT.md` | safe default used |
| agent returns `HEARTBEAT_OK` | no notification |
| agent returns useful update | notification emitted |
| cooldown active | notification suppressed |
| daily cap reached | notification suppressed |
| agent timeout | run logged as error |
| unavailable memory/tasks | run continues with empty source |

## Open Questions

- What Hermes API should emit user-visible notifications?
- Should heartbeat run in a fresh session or reuse current session?
- Should expensive tools be opt-in per source?
- Should heartbeat have per-channel delivery rules for Telegram, CLI, Discord, etc.?

## First Codex Task

Explore the Hermes-agent repository and propose the smallest plugin-based implementation plan for this spec.

Return:

1. Relevant plugin APIs and files.
2. Whether synthetic agent turns can be injected from a plugin.
3. Minimal file changes.
4. Any blockers requiring core changes.
5. A revised implementation plan before writing code.
