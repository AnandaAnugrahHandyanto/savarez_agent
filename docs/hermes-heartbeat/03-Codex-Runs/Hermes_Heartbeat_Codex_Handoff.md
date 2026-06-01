# Hermes Heartbeat Codex Handoff

Status: Ready for Codex Discovery
Project: Hermes Heartbeat
Owner: Aaron Lauer
Recommended first branch: `feature/heartbeat-discovery`

---

# Mission

Investigate whether Hermes-agent can support an OpenClaw-style heartbeat system as a plugin-first feature.

The heartbeat system should periodically wake Hermes, build a lightweight context pack, review configured sources, and notify the user only when there is timely, useful, actionable information.

Do not implement production code during the first Codex run.

Complete discovery first.

---

# Required Reading

Read these project files before inspecting code:

```text
01-Discovery/Hermes_Heartbeat_Discovery_Spec_v0.1.md
01-Discovery/Hermes_Heartbeat_Research_Log.md
01-Discovery/Hermes_Heartbeat_Codex_Tasking.md
02-Specs/Hermes_Heartbeat_SDD_v0.1.md
02-Specs/Hermes_Heartbeat_SDD_v0.2.md
```

Use SDD v0.2 as the preferred architecture unless repository evidence disproves it.

---

# First Codex Task

Perform discovery against the current Hermes-agent repository.

Do not write production code.

You may:

- inspect source files
- run tests
- search for plugin APIs
- search for memory APIs
- search for context engine APIs
- search for lifecycle hooks
- create or update discovery documentation

You must not:

- implement the heartbeat engine
- modify existing production behavior
- create a large refactor
- assume behavior from docs without source confirmation
- perform destructive Git operations

---

# Discovery Questions

Answer these with source-backed evidence:

1. Can a plugin start a background scheduler safely?
2. Can a plugin invoke an agent run programmatically?
3. Can Hermes accept synthetic messages or turns?
4. Can heartbeat retrieve memory without full chat history?
5. Can heartbeat access tasks, goals, or Kanban state?
6. How should heartbeat emit user-visible notifications?
7. Can plugins register or validate config?
8. Which hooks are currently operational?
9. Can heartbeat build or request an LCM-friendly context pack?
10. What test strategy fits the repo?

---

# Required Output

Update:

```text
01-Discovery/Hermes_Heartbeat_Research_Log.md
```

Then produce a discovery report containing:

```text
1. Summary recommendation
2. Evidence table
3. Proposed implementation option
4. Proposed directory structure
5. Risks and blockers
6. Minimal implementation plan
7. Files likely to change
8. Test plan
```

---

# Evidence Standard

Every meaningful claim must include:

```text
File:
Symbol:
Observed behavior:
Risk:
```

Example:

```text
Finding:
Plugins support startup hooks.

Evidence:
File: hermes/plugins/manager.py
Symbol: PluginManager.start()
Observed behavior: Iterates loaded plugins and awaits startup hook if present.
Risk: Low.
```

If uncertain, write:

```text
Unverified.
```

Do not guess.

---

# Decision Framework

## Option A: Pure Plugin

Choose if plugins can:

- start background work
- invoke agent runs
- access memory/task state
- emit notifications
- read config

## Option B: Plugin + Minor Core Patch

Choose if most functionality fits in a plugin but one clean extension point is missing.

Possible missing extension points:

- safe agent invocation API
- notification event API
- lifecycle startup hook
- context pack builder API

## Option C: External Supervisor Service

Choose if plugin lifecycle or agent invocation is too constrained.

---

# Preferred Architecture

Preserve this architecture if feasible:

```text
Heartbeat Engine
    |
    +-- Source Registry
    |
    +-- Policy Engine
    |
    +-- Context Builder
```

The engine owns scheduling and execution.

Sources gather observations.

Policies decide notify / suppress / defer.

The context builder keeps heartbeat runs small and LCM-friendly.

---

# Security and Safety Constraints

Heartbeat must be safe by default.

It must not:

- perform destructive actions
- send messages on behalf of the user
- mutate files
- create tasks
- browse the internet
- call expensive tools

unless explicitly configured and approved.

The default no-op response is:

```text
HEARTBEAT_OK
```

Responses equal to this token should be suppressed.

---

# Recommended Repository Layout For Project Docs

If adding docs to the fork, use:

```text
docs/hermes-heartbeat/
├── 01-Discovery/
│   ├── Hermes_Heartbeat_Discovery_Spec_v0.1.md
│   ├── Hermes_Heartbeat_Research_Log.md
│   └── Hermes_Heartbeat_Codex_Tasking.md
├── 02-Specs/
│   ├── Hermes_Heartbeat_SDD_v0.1.md
│   └── Hermes_Heartbeat_SDD_v0.2.md
└── 03-Codex-Runs/
    └── Codex_Handoff.md
```

If the upstream repo has a different docs convention, propose the best matching location before committing.

---

# Suggested Branch

```bash
git checkout -b feature/heartbeat-discovery
```

---

# Suggested Search Commands

```bash
rg "on_session_start|on_session_end|pre_llm_call|post_llm_call" .
rg "Plugin" .
rg "run_agent|Agent" .
rg "memory_provider|MemoryProvider|recall" .
rg "ContextEngine|context engine|LCM" .
rg "Kanban|task|goal" .
rg "notify|notification|emit_event|send" .
```

---

# Completion Criteria

Stop after discovery is complete.

Discovery is complete when the Research Log includes:

- plugin lifecycle answer
- scheduler answer
- agent invocation answer
- synthetic message answer
- memory answer
- tasks/Kanban answer
- notification answer
- config answer
- hook answer
- LCM/context answer
- risk assessment
- selected implementation option
- proposed implementation plan

After that, ask Aaron for approval before implementation.

---

# Handoff Prompt

Use this prompt to start Codex:

```text
Read the Hermes Heartbeat project documents. Do not implement yet. Complete the discovery phase described in Hermes_Heartbeat_Codex_Tasking.md. Inspect the Hermes-agent repository and update Hermes_Heartbeat_Research_Log.md with source-backed findings. Return a concise discovery report and stop before production code.
```
