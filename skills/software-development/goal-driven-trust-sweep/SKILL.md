---
name: goal-driven-trust-sweep
description: Use when an autonomous agent must complete non-trivial operational, cleanup, verification, or system-state work without prematurely reporting done.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [goals, verification, autonomous-agents, kanban, cleanup, trust]
    related_skills: [requesting-code-review, test-driven-development, systematic-debugging, writing-plans]
---

# Goal-Driven Trust Sweep

Use this skill when a request asks an agent to finish a non-trivial goal, especially cleanup, restart, cron/Kanban/queue work, repo integration, or any system-state task where visible leftovers can contradict a narrow success claim.

Core rule:

```text
DONE = direct evidence + adjacent/global visible-state sweep + stale/conflict classification.
```

If only the direct target was checked, the status is not done yet.

## Trigger phrases

- "finish this to the end"
- "supergoal this"
- "clean up everything"
- "restart/check all failing jobs"
- "make sure nothing is still blocked"
- "verify and report done"
- Broad autonomous tasks with multiple slices, queues, cron jobs, CI, docs, or worker handoffs

## Execution pattern

1. **Classify the request**
   - Chat/simple question: answer normally.
   - Verified action: do the work and provide direct evidence.
   - Operational/system-state: direct evidence plus trust sweep.
   - Broad/multi-phase: create or update a workpack/STATE handoff before deep execution.

2. **Define the completion contract before acting**
   - What is the direct target scope?
   - What adjacent/global state would the user still see?
   - Which stale, conflicting, or superseded artifacts would make a `DONE` claim false?
   - What command/readback/artifact proves the result?

3. **Execute the direct scope**
   - Make the smallest safe change.
   - Prefer tests or deterministic readbacks over visual assumptions.
   - Keep unrelated dirty state out of the slice.

4. **Run the trust sweep**
   - Check the direct target.
   - Check adjacent/global visible state using the user's terms.
   - Search for leftovers: `blocked`, `failed`, `rate limit`, `stale`, `superseded`, old task names, old output folders, dangling PRs, hidden queues.
   - Compare internal state with the user-facing surface.

5. **Close honestly**
   - `DONE` only when direct and adjacent/global checks are clean.
   - `CONDITIONAL` if the direct scope is clean but unrelated or ambiguous leftovers remain.
   - `BLOCKED` if completion requires auth, approval, unavailable service, failing CI, or user decision.

## Trust-sweep checklist

Use the relevant rows for the task class:

| Task class | Direct check | Adjacent/global sweep |
|---|---|---|
| Kanban/queue | Target task status/readback | Global visible blocked/running/failed thematic matches |
| Cron/scheduler | Target job state/logs | Other rate-limited/auth-failed jobs and scheduler health |
| Repo/PR | Focused tests and diff | Unrelated dirty files, stale branch/stack, CI/mergeability |
| Docs/knowledge | Target doc exists/readable | Canonical vs draft/inbox conflicts, steward review state |
| Runtime/service | Target process restarted/healthy | Logs, ports, dependent adapters, visible user channel smoke |

## Status language

Prefer short, explicit status:

```text
DONE: <result>. Evidence: <command/path/id>. Sweep: <direct + adjacent/global clean>.
```

```text
CONDITIONAL: direct target is clean, but <leftover> remains visible. Next: <cleanup or decision>.
```

```text
BLOCKED: <blocker>. Direct evidence: <what was checked>. Needed: <one action/decision>.
```

## Pitfalls

- Do not claim cleanup is done after checking only the new tenant/project/folder while old global items are still visible.
- Do not treat a worker/subagent self-report as final. Read back artifacts and run independent checks.
- Do not bundle unrelated dirty state into the same PR just because it is present in the worktree.
- Do not hide old/superseded artifacts; classify them, archive them, or report them.
- Do not turn transient setup failures into durable negative rules. Capture the fix or blocker instead.

## Verification examples

- `git status --short --branch`, `git diff --stat`, focused tests, and CI status for repo work.
- Queue/list commands plus target `show` readbacks for Kanban.
- Cron list plus job logs for scheduler recovery.
- File existence/readback plus steward/review status for documentation.

## Final report shape

Keep the user-facing report concise:

```text
Erledigt: <one line>
Evidence: <path/command/id>
Sweep: <clean / conditional / blocked + reason>
Nächster Schritt: <none / one action>
```
