# Native Codex Kanban Card Template

Use this shape for Kanban implementation cards assigned to the native Codex lane (`assignee=codex`). The card body is the execution contract: Codex runs non-interactively inside the resolved task workspace, so the card must be scoped enough to execute without live steering.

```markdown
Goal:
<One clear end state. Treat this as the implementation goal.>

Context:
- Repo/workspace: <path, worktree policy, or board workspace expectation>
- Current branch/base: <main/staging/feature branch/etc.>
- Relevant files/surfaces: <paths, routes, commands, jobs, docs>
- Background notes: <brief, only what matters for the task>

Acceptance criteria:
- <observable requirement 1>
- <observable requirement 2>
- <observable requirement 3>

Boundaries / non-goals:
- Stay inside the assigned workspace unless explicitly authorized.
- Do not merge, deploy, force-push, rotate secrets, or touch production data.
- Do not install dependencies unless the task explicitly requires it.
- <task-specific no-go items>

Required working style:
- Investigate first; read repo guidance and relevant existing code before editing.
- Set an internal plan from this card.
- Implement the scoped goal, then self-review the diff.
- Run relevant targeted gates; if a gate is too expensive or unavailable, explain why.

Verification / gates:
- <command 1>
- <command 2>
- <manual/browser/API proof if relevant>

Receipt required in final response:
- Changed files
- Commands/gates run and results
- Verification evidence
- Remaining risks/blockers
- Recommended reviewer action
```

Kanban policy for the native Codex lane:

- Implementation cards use `--assignee codex`.
- A successful Codex process blocks the task as `review-required:` rather than marking it done.
- A failed/missing/timed-out Codex process blocks the task as `codex-failed:`.
- A human or verifier reviews the worker log, metadata, diff, and gates before marking the card done or unblocking with fix instructions.
