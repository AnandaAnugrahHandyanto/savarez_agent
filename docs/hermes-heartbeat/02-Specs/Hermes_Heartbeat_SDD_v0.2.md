# Hermes Heartbeat SDD v0.2
## Modular Architecture for Proactive Awareness

# Executive Summary

This version separates the system into three independently testable components:

1. Heartbeat Engine
2. Heartbeat Sources
3. Heartbeat Policies

This architecture minimizes coupling, simplifies testing, and allows future expansion without modifying the core heartbeat loop.

---

# Design Goals

- Plugin-first implementation
- Minimal Hermes core changes
- Bounded token usage
- LCM-friendly context generation
- Extensible source system
- Extensible policy system
- Deterministic behavior
- Safe-by-default operation

---

# Architecture

```text
Scheduler
    |
    v
Heartbeat Engine
    |
    +--> Source Registry
    |         |
    |         +--> Tasks
    |         +--> Memory
    |         +--> Calendar
    |         +--> Vault
    |         +--> Git
    |
    v
Context Pack
    |
    v
Agent Review
    |
    v
Policy Engine
    |
    +--> Suppress
    +--> Notify
    +--> Log
```

---

# Component 1: Heartbeat Engine

## Responsibility

The engine manages scheduling and execution.

It does not know anything about tasks, memory, calendars, repositories, or notifications.

## Responsibilities

- Scheduling
- Active hour enforcement
- Runtime budgets
- Token budgets
- Context assembly
- Agent execution
- Result routing

## Inputs

```json
{
  "timestamp": "...",
  "timezone": "...",
  "sources": [...],
  "policies": [...]
}
```

## Outputs

```json
{
  "heartbeat_id": "...",
  "status": "success",
  "response": "...",
  "metrics": {}
}
```

---

# Engine Configuration

```yaml
heartbeat:
  enabled: true
  interval_minutes: 30
  jitter_minutes: 5

  active_hours:
    enabled: true
    start: "08:00"
    end: "22:00"

  budgets:
    max_runtime_seconds: 90
    max_tokens: 4000
```

---

# Component 2: Heartbeat Sources

## Responsibility

Sources gather state.

Sources never decide whether to notify.

Sources only provide observations.

---

## Source Contract

Every source implements:

```python
class HeartbeatSource:

    name: str

    async def collect(self) -> dict:
        pass
```

---

## Example Output

```json
{
  "source": "tasks",
  "items": [
    {
      "type": "overdue",
      "title": "Review proposal",
      "age_hours": 48
    }
  ]
}
```

---

# Initial Sources

## Tasks Source

Provides:

- open tasks
- blocked tasks
- overdue tasks

## Memory Source

Provides:

- recent memory additions
- unresolved commitments
- pending follow-ups

## Calendar Source

Provides:

- upcoming events
- approaching deadlines

## Vault Source

Provides:

- changed files
- watched documents

## Git Source

Provides:

- open pull requests
- failed workflows
- stale branches

---

# Source Registry

```python
registry = [
    TasksSource(),
    MemorySource(),
    CalendarSource(),
    VaultSource(),
]
```

Engine discovers sources automatically.

Sources may be enabled or disabled independently.

---

# Component 3: Policy Engine

## Responsibility

Determines whether the user should be notified.

Policies consume observations.

Policies never gather state.

---

# Policy Contract

```python
class HeartbeatPolicy:

    name: str

    async def evaluate(
        observations
    ) -> PolicyDecision:
        pass
```

---

# Policy Decision

```json
{
  "action": "notify",
  "reason": "deadline approaching",
  "priority": "high"
}
```

Possible actions:

- notify
- suppress
- defer

---

# Initial Policies

## Deadline Policy

Notify when:

- event is within configured window
- task is overdue

## Follow-Up Policy

Notify when:

- promised action is unresolved
- user requested future check-in

## Change Detection Policy

Notify when:

- watched resource changed significantly

## Cooldown Policy

Suppress when:

- recent notification already sent

## Daily Budget Policy

Suppress when:

- daily cap reached

---

# Context Pack

The engine constructs a lightweight context pack.

```json
{
  "event": "heartbeat",
  "time": "...",
  "observations": [...],
  "budgets": {...}
}
```

Explicitly excluded:

- full conversation history
- archived context
- large documents
- raw embeddings

---

# Agent Prompt

```text
[HEARTBEAT REVIEW]

Review the supplied observations.

Determine whether there is useful,
timely, actionable information.

If no action is needed return:

HEARTBEAT_OK

Otherwise provide:

- finding
- reason
- recommended action
```

---

# Notification Pipeline

```text
Agent Response
      |
      v
Policy Validation
      |
      +--> Suppress
      |
      +--> Notify
               |
               v
         Delivery Layer
```

---

# Delivery Layer

Out of scope for v0.2 implementation.

Potential future targets:

- CLI
- Discord
- Telegram
- Slack
- Email
- Mobile Push

---

# Logging

Every heartbeat generates:

```json
{
  "heartbeat_id": "...",
  "timestamp": "...",
  "duration_ms": 0,
  "tokens": 0,
  "sources": [],
  "decision": "notify"
}
```

---

# Acceptance Criteria

## Engine

- Scheduler runs correctly
- Active hours enforced
- Budgets enforced
- Supports source registry

## Sources

- Sources independently testable
- Source failures isolated
- Missing sources do not stop heartbeat

## Policies

- Policies independently testable
- Multiple policies supported
- Policies composable

## Integration

- End-to-end heartbeat run succeeds
- HEARTBEAT_OK suppression works
- Cooldowns enforced
- Notification caps enforced

---

# Codex Phase Plan

## Phase 1

Implement:

- Heartbeat Engine
- Scheduler
- Configuration
- Logging

## Phase 2

Implement:

- Source Registry
- Tasks Source
- Memory Source

## Phase 3

Implement:

- Policy Engine
- Cooldown Policy
- Budget Policy

## Phase 4

Implement:

- End-to-end integration tests
- Documentation
- Sample HEARTBEAT.md

---

# First Codex Task

Determine:

1. Best plugin insertion point
2. Existing scheduler capabilities
3. Existing memory APIs
4. Existing task APIs
5. Whether agent runs can be invoked programmatically from a plugin

Return a proposed directory structure before writing code.
