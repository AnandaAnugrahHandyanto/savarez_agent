# Hermes Heartbeat Codex Tasking

Status: Ready for Discovery
Purpose: Give Codex a precise first assignment for the Hermes Heartbeat project.

---

# Operating Mode

You are Codex working on the Hermes Heartbeat project.

Your first job is discovery, not implementation.

Do not write production code yet.

You may inspect the repository, read files, run tests, and create or update discovery artifacts.

---

# Required Project Documents

Read these documents first:

```text
Hermes_Heartbeat_SDD_v0.1.md
Hermes_Heartbeat_SDD_v0.2.md
Hermes_Heartbeat_Discovery_Spec_v0.1.md
Hermes_Heartbeat_Research_Log.md
Hermes_Heartbeat_Codex_Tasking.md
```

Use v0.2 as the preferred architecture unless repository discovery disproves it.

---

# Primary Objective

Determine whether Hermes Heartbeat can be implemented as:

1. a pure plugin,
2. a plugin plus minor core patch, or
3. an external supervisor service.

Return a recommendation based on source code evidence.

---

# Strict Non-Goals

Do not:

- implement the heartbeat engine yet
- modify production code unless explicitly asked
- create a large refactor
- assume APIs from documentation alone
- load unrelated project areas
- change model configuration
- change user memory behavior
- create autonomous destructive actions

---

# Required Discovery Areas

Investigate and report on:

1. Plugin lifecycle
2. Background task support
3. Agent invocation
4. Synthetic message support
5. Memory access
6. Tasks / Kanban access
7. Notification delivery
8. Plugin configuration
9. Hook behavior
10. Context / LCM integration
11. Test strategy

---

# Required Output

Produce or update:

```text
Hermes_Heartbeat_Research_Log.md
```

Then provide a concise discovery report containing:

```text
1. Summary recommendation
2. Evidence table
3. Proposed directory structure
4. Risks and blockers
5. Minimal implementation plan
6. Files likely to change
7. Test plan
```

---

# Evidence Standard

Every important claim must cite:

- exact file path
- function, class, or symbol name
- short explanation of observed behavior

Example:

```text
Finding:
Plugins support startup hooks.

Evidence:
File: hermes/plugins/manager.py
Symbol: PluginManager.start()
Behavior: Iterates loaded plugins and invokes async startup if present.
```

If the source is unclear, say:

```text
Unverified.
```

Do not guess.

---

# Suggested Investigation Commands

Use commands appropriate to the repository.

Examples:

```bash
find . -iname '*plugin*' -o -iname '*memory*' -o -iname '*context*'
grep -R "on_session_start" -n .
grep -R "pre_llm_call" -n .
grep -R "run_agent" -n .
grep -R "Kanban" -n .
grep -R "memory_provider" -n .
grep -R "ContextEngine" -n .
```

Prefer modern alternatives like `rg` when available.

---

# Decision Framework

## Option A: Pure Plugin

Choose this if:

- plugins can start background tasks,
- plugins can invoke agent runs,
- plugins can access memory/tasks,
- plugins can emit notifications.

## Option B: Plugin + Minor Core Patch

Choose this if:

- most functionality fits in a plugin,
- but one clean extension point is missing.

Examples:

- no safe agent invocation API,
- no notification API,
- no lifecycle startup hook.

## Option C: External Supervisor Service

Choose this if:

- plugins cannot safely manage background work,
- synthetic agent runs are not supported,
- core changes would be invasive.

---

# Preferred Architecture

If feasible, preserve the v0.2 architecture:

```text
Heartbeat Engine
    |
    +-- Source Registry
    |
    +-- Policy Engine
    |
    +-- Context Builder
```

Do not collapse sources and policies into the engine unless repository constraints force it.

---

# First Deliverable

Create a branch:

```text
feature/heartbeat-discovery
```

Then update:

```text
docs/hermes-heartbeat/Hermes_Heartbeat_Research_Log.md
```

If the repository does not have a `docs/` directory, propose the best location before writing.

---

# Completion Criteria

Discovery is complete when the Research Log has:

- all discovery areas filled out,
- one implementation option selected,
- a proposed directory structure,
- known blockers listed,
- minimal implementation plan,
- test strategy.

After that, stop and ask for approval before implementation.
