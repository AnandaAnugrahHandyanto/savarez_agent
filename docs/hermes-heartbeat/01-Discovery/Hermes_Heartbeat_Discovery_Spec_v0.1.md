# Hermes Heartbeat
## Technical Discovery Spec v0.1

Status: Discovery Phase
Purpose: Validate integration points before implementation

---

# Objective

Before implementing the Heartbeat system, determine whether Hermes already exposes the required lifecycle, scheduling, memory, and agent execution primitives.

The goal of this phase is to reduce implementation risk and prevent architecture decisions from being based on assumptions.

No implementation work should begin until this discovery phase is complete.

---

# Key Questions

The implementation depends on five critical capabilities:

1. Plugin background execution
2. Agent invocation from plugins
3. Memory access APIs
4. Notification delivery mechanisms
5. Plugin configuration registration

Each capability must be verified directly from the Hermes codebase.

---

# Discovery Area 1
## Background Tasks

### Question

Can a plugin safely start and manage a long-running scheduler loop?

### Why It Matters

Heartbeat requires recurring execution independent of user messages.

### Required Findings

Determine:

- Where plugin lifecycle starts
- Whether plugins support startup hooks
- Whether plugins can spawn background tasks
- Whether plugins can survive multiple sessions
- Whether scheduler state survives reloads

### Files To Investigate

Potential areas:

```text
plugins/
hermes_cli/plugins.py
gateway/
run_agent.py
```

### Success Criteria

Document:

```text
Plugin startup location
Plugin shutdown location
Recommended scheduler insertion point
Known lifecycle risks
```

---

# Discovery Area 2
## Agent Invocation

### Question

Can a plugin trigger an agent run programmatically?

### Why It Matters

Heartbeat must create a synthetic review turn.

### Required Findings

Determine:

- How Hermes creates agents
- Whether plugins can invoke agent execution
- Whether synthetic messages are supported
- Whether runs require active sessions
- Whether runs can execute without user input

### Success Criteria

Provide:

```python
await run_agent(...)
```

or equivalent entry point.

If unavailable:

Document required core changes.

---

# Discovery Area 3
## Memory Access

### Question

How can heartbeat retrieve memory without loading full conversation history?

### Why It Matters

Heartbeat depends on lightweight context.

### Required Findings

Identify:

- Memory provider interfaces
- Memory retrieval APIs
- Cross-session memory access
- Structured memory access methods
- Memory provider plugin contracts

### Success Criteria

Document:

```python
memory_provider.recall(...)
```

or equivalent APIs.

Identify which memory providers are compatible.

---

# Discovery Area 4
## Tasks And Kanban

### Question

Can heartbeat access active goals, tasks, or Kanban state?

### Why It Matters

Task awareness is a primary heartbeat signal.

### Required Findings

Determine:

- Where tasks are stored
- Whether task APIs exist
- Whether Kanban state is accessible
- Whether plugins can query active work

### Success Criteria

Provide:

```python
get_active_tasks()
```

or equivalent access path.

---

# Discovery Area 5
## Notifications

### Question

How should heartbeat deliver user-visible notifications?

### Why It Matters

The engine should not implement platform-specific messaging.

### Required Findings

Determine:

- Existing notification APIs
- Gateway messaging APIs
- Session output APIs
- Event emission mechanisms
- Cross-platform delivery paths

### Success Criteria

Recommend one abstraction:

```python
notify_user(...)
```

or

```python
emit_event(...)
```

or equivalent.

---

# Discovery Area 6
## Plugin Configuration

### Question

How should heartbeat configuration be registered?

### Why It Matters

The plugin requires configuration, budgets, schedules, and source control.

### Required Findings

Determine:

- Plugin config loading process
- YAML schema support
- Validation system
- Default value patterns

### Success Criteria

Document:

```yaml
heartbeat:
  ...
```

integration strategy.

---

# Discovery Area 7
## Hooks

### Question

Can heartbeat leverage existing hook infrastructure?

### Why It Matters

Hooks may eliminate custom integration work.

### Required Findings

Validate current behavior of:

- pre_llm_call
- post_llm_call
- on_session_start
- on_session_end

Determine:

- Which hooks are operational
- Which hooks are gateway-only
- Which hooks are synchronous
- Performance implications

### Notes

Known historical issues indicate hook behavior changed across releases.

Verification against current source is required.

---

# Discovery Area 8
## Context Compression

### Question

How should heartbeat interact with Hermes-LCM?

### Why It Matters

Heartbeat must remain lightweight.

### Required Findings

Determine:

- Whether plugins can request custom context packs
- Whether LCM can operate on synthetic runs
- Whether context engines can be invoked directly

### Success Criteria

Document:

```python
build_heartbeat_context()
```

strategy.

---

# Deliverables

Codex should return:

## 1. Integration Report

A short report covering all discovery areas.

---

## 2. Directory Proposal

Example:

```text
plugins/heartbeat/
├── plugin.yaml
├── __init__.py
├── scheduler.py
├── engine.py
├── context.py
├── policies/
├── sources/
└── tests/
```

---

## 3. Risk Assessment

For each discovery area:

```text
Low Risk
Medium Risk
High Risk
Requires Core Change
```

---

## 4. Revised Architecture

Update the v0.2 architecture based on actual Hermes capabilities.

---

## 5. Implementation Recommendation

Choose one:

### Option A

Pure plugin

### Option B

Plugin + minor core patch

### Option C

External supervisor service

Provide justification.

---

# Initial Evidence

Current public documentation suggests:

- Hermes supports plugins
- Hermes supports plugin hooks
- Hermes supports memory provider plugins
- Hermes supports context engine plugins
- Hermes supports gateway lifecycle events

However:

Several historical issues indicate lifecycle hook behavior changed across releases.

Therefore no hook behavior should be assumed without source validation.

---

# Exit Criteria

Discovery is complete when:

- Agent invocation path is identified
- Scheduler insertion point is identified
- Memory retrieval path is identified
- Notification strategy is identified
- Configuration strategy is identified
- Risk assessment is completed

Only after these findings should implementation begin.
