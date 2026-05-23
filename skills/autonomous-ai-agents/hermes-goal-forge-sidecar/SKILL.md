---
name: hermes-goal-forge-sidecar
description: "Use when adapting goal-forge style long-running agent contracts to Hermes: creating GOAL/PLAN/ATTEMPTS/NOTES/CONTROL packages, running a main Hermes/Codex/Claude agent, and using a read-only Hermes sidecar reviewer via delegate_task or a separate Hermes process."
version: 0.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [hermes, goal-forge, sidecar, delegation, autonomous-agents]
    related_skills: [hermes-agent, codex, claude-code, opencode, subagent-driven-development]
---

# Hermes Goal Forge Sidecar

Hermes-native adaptation of goal-forge: turn a rough repo objective into a measurable long-running goal package, then run it with a main runner and a separate sidecar reviewer.

This skill is for tests, agent missions, and repo work where the user wants the goal-forge discipline without pretending Hermes has a magic autonomous supervisor loop. Hermes already has useful primitives:

- `delegate_task` for bounded read-only or review subagents.
- `terminal(background=true, notify_on_complete=true)` for long-running agent processes.
- `cronjob` for recurring watchdog/review loops.
- skills and memory for reusable procedures.

## Core Contract

Create or maintain these files in the target repo or task directory:

- `GOAL.md` — executable contract with `<goal>`, `<scorecard>`, `<done_when>`, `<feedback_loop>`, `<workflow>`, `<working_memory>`, `<human_control_surface>`, `<verification_loop>`, and `<output_contract>`.
- `PLAN.md` — current strategy, phases, status, blockers, next action.
- `ATTEMPTS.md` — attempt log with evidence, result, and next adjustment.
- `NOTES.md` — durable discoveries that should survive context compaction.
- `CONTROL.md` — compact operator panel with priorities, scope/resource knobs, decision gates, sidecar inputs, and Latest Human Nudge.

The `scorecard` and fast feedback loop are mandatory for long-running work. If the agent cannot name a fast representative check, it must say that explicitly and use a slower cadence.

## Recommended Hermes Runtime Pattern

1. **Forge the goal package.** Use `templates/goal-package.md` as the starting structure. Ask the user only for product decisions that materially change scope, scorecard, or acceptance criteria.
2. **Run the main runner.** The main runner may be the current Hermes session, a spawned `hermes chat -q` process, Codex, Claude Code, OpenCode, or a Kanban worker. It owns repository edits.
3. **Run a sidecar reviewer.** Use `delegate_task` for bounded reviews or spawn a second Hermes process for long reviews. The sidecar reviewer is read-only by default.
4. **Apply steering deliberately.** Sidecar findings are advice, not success evidence. The task owner decides whether to continue, pause, redirect, or reject.
5. **Verify with tests.** The main runner must report `tests_run`, artifacts, accepted_commits, and any rejected_reason or remaining risk.

## Sidecar Reviewer Rules

Use `templates/sidecar-review-prompt.md` when asking another Hermes instance or `delegate_task` to review a run.

Hard boundaries:

- Do not let the sidecar modify the repository unless the user explicitly promotes it to a fixer role.
- Do not let the sidecar approve its own work.
- Do not treat model judgment as a substitute for commands, diffs, logs, or artifact inspection.
- Do not paste secrets, raw credentials, cookies, or private tokens into a sidecar prompt.
- Do not weaken `done_when`, scorecard thresholds, or safety constraints through `CONTROL.md`; `CONTROL.md` may narrow, pause, or require approval.

The sidecar should inspect logs, diffs, test output, artifacts, `PLAN.md`, `ATTEMPTS.md`, `NOTES.md`, and `CONTROL.md`, then return:

- verdict: `continue | pause | redirect | reject`
- evidence
- suspected failure mode
- concise steering directive
- next verification command

## CONTROL.md Minimum Fields

Keep `CONTROL.md` compact. Include only knobs relevant to the current goal.

Required concepts:

- `status_file: PLAN.md`
- `attempt_log: ATTEMPTS.md`
- `durable_notes: NOTES.md`
- `check_control_before: phase_change, strategic_pivot, expensive_step, sidecar_ingestion`
- `sidecar_apply_cadence`
- protected files / max blast radius if repo edits are involved
- resource limits when tests, model calls, network, GPU, or external APIs are involved
- approval gates for destructive changes, dependency changes, migrations, public API changes, and scope expansion
- `Latest Human Nudge`

## Example delegate_task Call

```python
delegate_task(
    goal="Review the current goal run as a read-only Hermes sidecar reviewer.",
    context="""
    Repo: /path/to/repo
    Read: GOAL.md, PLAN.md, ATTEMPTS.md, NOTES.md, CONTROL.md, git diff, latest test output.
    Do not edit files. Return verdict continue|pause|redirect|reject, evidence, suspected failure mode,
    concise steering directive, and next verification command.
    """,
    toolsets=["terminal", "file"],
)
```

## Output Contract for Main Runner

Every main runner completion report should include:

```json
{
  "result": "accepted | rejected | partial | timed_out",
  "tests_run": ["exact commands"],
  "artifacts": ["paths or URLs"],
  "accepted_commits": ["commit sha or empty"],
  "rejected_reason": "why not accepted, if relevant",
  "sidecar_verdicts": ["summary or paths"],
  "remaining_risks": ["known risks"]
}
```

## Pitfalls

- Sidecar context can drift. Always ground it in current files, diffs, logs, and test output.
- Long-running agents loop when the judge prompt is too strict or lacks a forward-progress rule. A sidecar should identify the smallest safe next step, not only criticize.
- `CONTROL.md` is not a second `GOAL.md`. If it grows large, move stable instructions back into `GOAL.md` and keep only live knobs in `CONTROL.md`.
- For quick linear tasks, skip this ceremony and just run normal TDD.

## Verification Checklist

- [ ] `GOAL.md` has measurable `done_when`, scorecard, fast feedback loop, and final verification.
- [ ] Working memory files exist or the task is short enough to justify skipping them.
- [ ] `CONTROL.md` includes sidecar_apply_cadence and Latest Human Nudge when sidecar review is planned.
- [ ] Sidecar is read-only unless explicitly promoted.
- [ ] Completion report includes tests_run and accepted_commits or rejected_reason.
