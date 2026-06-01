# Hermes Heartbeat Research Log

Status: Active
Owner: Codex / Agent Team
Purpose: Record verified findings from the Hermes-agent repository before implementation.

---

# How To Use This Document

Codex should update this file during the discovery phase.

Rules:

- Record only facts verified from the current repository.
- Link or name exact files, classes, functions, and config keys.
- Do not infer behavior from documentation unless source code confirms it.
- Mark uncertain findings as `Unverified`.
- Do not begin production implementation until the Discovery Exit Criteria are complete.

---

# Discovery Summary

## Current Recommendation

Pending.

Choose one after discovery:

- Option A: Pure plugin
- Option B: Plugin plus minor core patch
- Option C: External supervisor service

## Current Risk Level

Pending.

---

# Finding 1: Plugin Lifecycle

## Question

Can a plugin safely start and stop a background scheduler?

## Status

Pending.

## Evidence

```text
File:
Symbol:
Behavior:
```

## Notes

Pending.

## Risk

Pending.

---

# Finding 2: Agent Invocation

## Question

Can a plugin trigger an agent run programmatically?

## Status

Pending.

## Evidence

```text
File:
Symbol:
Behavior:
```

## Notes

Pending.

## Risk

Pending.

---

# Finding 3: Synthetic Messages

## Question

Can Hermes accept a synthetic heartbeat turn without manual user input?

## Status

Pending.

## Evidence

```text
File:
Symbol:
Behavior:
```

## Notes

Pending.

## Risk

Pending.

---

# Finding 4: Memory Access

## Question

Can heartbeat retrieve memory without loading full chat history?

## Status

Pending.

## Evidence

```text
File:
Symbol:
Behavior:
```

## Notes

Pending.

## Risk

Pending.

---

# Finding 5: Tasks / Kanban Access

## Question

Can heartbeat query active tasks, goals, or Kanban state?

## Status

Pending.

## Evidence

```text
File:
Symbol:
Behavior:
```

## Notes

Pending.

## Risk

Pending.

---

# Finding 6: Notification Delivery

## Question

How should heartbeat emit user-visible updates?

## Status

Pending.

## Evidence

```text
File:
Symbol:
Behavior:
```

## Notes

Pending.

## Risk

Pending.

---

# Finding 7: Plugin Configuration

## Question

Can the heartbeat plugin register and validate config?

## Status

Pending.

## Evidence

```text
File:
Symbol:
Behavior:
```

## Notes

Pending.

## Risk

Pending.

---

# Finding 8: Hook Behavior

## Question

Are lifecycle and LLM hooks usable for heartbeat?

## Status

Pending.

## Evidence

```text
File:
Symbol:
Behavior:
```

## Notes

Pending.

## Risk

Pending.

---

# Finding 9: Context / LCM Integration

## Question

Can heartbeat request or construct a lightweight context pack compatible with Hermes-LCM?

## Status

Pending.

## Evidence

```text
File:
Symbol:
Behavior:
```

## Notes

Pending.

## Risk

Pending.

---

# Proposed Directory Structure

Codex should propose the actual structure after repository inspection.

Initial hypothesis:

```text
plugins/heartbeat/
├── plugin.yaml
├── __init__.py
├── config.py
├── scheduler.py
├── engine.py
├── context.py
├── logging.py
├── sources/
│   ├── __init__.py
│   ├── base.py
│   ├── tasks.py
│   └── memory.py
├── policies/
│   ├── __init__.py
│   ├── base.py
│   ├── cooldown.py
│   └── budget.py
└── tests/
    ├── test_config.py
    ├── test_scheduler.py
    ├── test_engine.py
    ├── test_sources.py
    └── test_policies.py
```

---

# Blockers

Use this section for issues that prevent a pure plugin implementation.

| Blocker | Evidence | Severity | Proposed Resolution |
|---|---|---|---|
| Pending | Pending | Pending | Pending |

---

# Implementation Recommendation

Pending.

## Option Chosen

Pending.

## Justification

Pending.

---

# Discovery Exit Criteria

Discovery is complete when all of these are answered:

- Agent invocation path identified
- Scheduler insertion point identified
- Memory retrieval path identified
- Task retrieval path identified
- Notification strategy identified
- Configuration strategy identified
- Hook behavior verified
- LCM/context strategy identified
- Risk assessment completed
- Recommended implementation option selected
