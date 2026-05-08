---
name: prd-phased-codex
description: "Default workflow for user repo work from a task or PRD: Hermes creates/updates a PRD, slices it into phases, uses Kanban for durable orchestration, and runs Codex one phase at a time through the guarded hermes-codex-phase wrapper."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [prd, planning, codex, kanban, orchestration, github, autonomous-coding]
    related_skills: [writing-plans, plan, subagent-driven-development, kanban-orchestrator, kanban-worker, codex, github-repo-management]
---

# PRD Phased Codex

Use this workflow whenever the user gives a repository, product request, PRD,
implementation idea, or asks Hermes to work independently on a code project.
Do this even if the user does not explicitly name this skill.

## Ownership

- Hermes is the orchestrator: clarify, plan, split, schedule, review, and ask the user when risk is high.
- Repo Recon is the first worker: map the target repo with evidence only; no planning, no implementation.
- Codex is the implementation worker: execute exactly one phase in an isolated repo/worktree.
- Kanban is the durable state: tasks, dependencies, blocks, comments, handoffs, and retry history.
- GitHub is the audit trail: private origin, feature branches, commits, draft PRs.

## Scope Disambiguation

Before planning, decide what "the workflow", "the PRD", "the planner", or "the
tool" refers to.

Default assumption for repo tasks: the user is asking about the target
repository, not Hermes's own `prd-phased-codex` workflow.

If the repo itself contains PRD/planner/builder concepts, treat those as
product-domain concepts inside the repo. Do not rewrite Hermes skills, Codex
skills, dashboard services, or global orchestration unless the user explicitly
asks to change Hermes itself.

Bad response pattern:

- User asks for a feature in a cloned repo.
- Hermes asks generic implementation questions about language, script location,
  and interface without first reading the repo.

Correct response pattern:

- Map the repo.
- Identify existing workflow terms from repo docs/code.
- Restate the task using repo-native vocabulary.
- Only then write a PRD/plan.

## Mandatory Phase 0: Repo Map

Do not create or update a PRD, implementation plan, phase files, or Codex prompt
until this file exists and contains repo-specific facts:

```text
.hermes/repo-map.md
```

Repos under `/home/ubuntu/repos/` and `/home/ubuntu/work/hermes-repos/` are
observed by `hermes-repo-watch.service`, which runs the deterministic repo map
in the background after a repo becomes stable. Still verify the artifact exists
and is current before planning; if the user request points to a new subsystem,
regenerate it manually. The watcher also runs a lightweight `project-rag` recon
index for docs/config/workflow files and writes `.hermes/rag-index.json`. Full
code indexing is intentionally manual because it can be expensive.

Preferred context stack:

1. If `project-rag` MCP is available, index the target repo and run semantic
   searches for the user's request, repo-native workflows, PRD/planner/builder
   terms, validation commands, state files, and stop/block mechanisms.
2. If `context-mode` MCP is available, keep the active working context scoped to
   the target repo, user request, repo map, recon brief, and current phase.
3. Always create the deterministic repo map below as the durable source artifact.

Deterministic command:

```bash
/home/ubuntu/.hermes/scripts/hermes-repo-map <repo-path>
```

Treat this as the output of the "Repo Recon" agent. The recon artifact is
evidence, not a plan. It should be regenerated when the repo changes
substantially or when the user's request points at a new area of the codebase.

The repo map must cite concrete files and include:

- purpose of the project
- stack and package manager
- important scripts from `package.json`, `Makefile`, or equivalent
- workflow described in `CLAUDE.md`, `AGENTS.md`, `README.md`, and `docs/`
- existing PRD/planner/builder concepts in the repo
- state files and stop/block mechanisms already present
- where the requested change most likely belongs
- open questions that remain after reading the repo

Minimum orientation commands:

```bash
pwd
git status --short --branch
git remote -v
find . -maxdepth 3 -type f | sort | sed -n '1,240p'
test -f package.json && cat package.json
test -f CLAUDE.md && sed -n '1,220p' CLAUDE.md
test -f AGENTS.md && sed -n '1,220p' AGENTS.md
test -f README.md && sed -n '1,220p' README.md
find docs -maxdepth 2 -type f -name '*.md' -print 2>/dev/null | sort
```

For Node/TS repos, also inspect likely CLI and engine entrypoints:

```bash
find engine scripts src cli -maxdepth 3 -type f 2>/dev/null | sort | sed -n '1,240p'
```

If the repo map is generic or lacks file citations, stop and redo mapping. Do
not ask Codex to "review the plan" until the plan was built from the repo map.

If `project-rag` and deterministic reads disagree, trust concrete repository
files over semantic summaries. Use `project-rag` to find the right files faster,
not as permission to skip file citations.

## Recon Agent Contract

When the user asks for a PRD, enhancement, feature plan, or implementation in a
repo, the first task is always:

```text
Recon: map the target repository for <user request>
```

Recon must produce:

```text
.hermes/repo-map.md
.hermes/recon-brief.md
```

`repo-map.md` is generated by the script and contains raw evidence. `recon-brief.md`
is Hermes's short synthesis from that evidence:

```markdown
# Recon Brief

User request:

Repo-native interpretation:

Relevant existing workflow:

Files/scripts likely involved:

Existing state/block/review mechanisms:

Validation commands:

What NOT to change:

Open questions:
```

The Planner may only start after `recon-brief.md` exists. If the brief cannot
answer where the change belongs, ask targeted questions or run deeper grep/read
passes; do not write a generic PRD.

## External Reviewer Rule: Codex or Claude

Codex is installed on this VPS; Claude CLI may or may not be installed. Treat
Claude as optional. Never require Claude for this workflow.

Before using any external reviewer (Codex, Claude, OpenCode, etc.):

1. Confirm the tool exists (`command -v codex`, `command -v claude`).
2. Provide the reviewer with:
   - the original user request
   - `.hermes/repo-map.md`
   - the draft PRD/plan
   - explicit instruction: "Review the plan against the repo map. Do not infer
     from Hermes's global workflow unless the repo map says so."
3. Ask for findings only, not implementation, unless executing a phase through
   `hermes-codex-phase`.

Reviewer prompt shape:

```text
You are reviewing a plan for the target repository, not Hermes itself.
Source of truth:
1. User request below
2. Repo map below
3. Draft plan below

Find repo-specific gaps, wrong assumptions, missing files/scripts, and
terminology contamination. Do not propose generic implementation questions if
the repo map answers them.
```

If Claude is unavailable, use Codex. If both are unavailable, perform the review
locally from the repo map and say no external reviewer was available.

## Required Workspace Rules

Before autonomous work:

1. The repo must live under `/home/ubuntu/work/hermes-repos/`.
   `/home/ubuntu/repos/` is also allowed as the default Telegram clone/inbox path.
2. The repo must be a Git repo.
3. `origin` must point to `github.com/nicolaregattieri/...`.
4. Work must happen on a feature branch, never `main` or `master`.
5. If the repo came from a third party, use `github-repo-management` to rename/remove the old remote and push to a private repo first.

## Repository Layout

Create these files inside the repo:

```text
PRD.md                         # If user did not provide one, Hermes writes it.
.hermes/repo-map.md            # Required before PRD/planning.
.hermes/recon-brief.md         # Required synthesis before PRD/planning.
.hermes/plans/                 # Implementation plans.
.hermes/phases/                # One phase file per execution unit.
.hermes/events/                # Codex writes phase_complete / needs_input events.
.hermes/codex-logs/            # Wrapper captures Codex logs.
```

## PRD Quality Gate

A PRD is invalid if it could apply to many repositories.

Every repo-derived PRD must include:

- exact existing workflow from repo docs
- exact files/scripts that will change
- current behavior, using repo terminology
- proposed behavior, using repo terminology
- interaction with existing state/block/QA mechanisms
- non-goals, especially what should not change
- validation commands already used by the repo

If the user request mentions "PRD", "planner", "builder", "Figma", "task", or
"review pause", first check whether those terms already exist in repo docs/code.
Use the repo's meaning, not Hermes's meaning.

## Phase Rules

Each phase must be small enough for one Codex run. Prefer 15-45 minutes of work.
Good phases:

- `phase-001-discover-and-run.md`
- `phase-002-data-model.md`
- `phase-003-api-slice.md`
- `phase-004-ui-slice.md`
- `phase-005-tests-and-polish.md`

Every phase file must include:

```markdown
# Phase N: Name

Objective:

Scope:
- In:
- Out:

Acceptance criteria:
- ...

Allowed files:
- ...

Validation:
- Command:
- Expected:

Stop and ask if:
- ...
```

## Execution

Hermes must not call `codex --yolo` directly. Use:

```bash
/home/ubuntu/.hermes/scripts/hermes-codex-phase /home/ubuntu/work/hermes-repos/<repo> .hermes/phases/phase-001-discover-and-run.md 45
```

For repos cloned by Telegram commands, `/home/ubuntu/repos/<repo>` is valid too:

```bash
/home/ubuntu/.hermes/scripts/hermes-codex-phase /home/ubuntu/repos/<repo> .hermes/phases/phase-001-discover-and-run.md 45
```

The wrapper validates path, remote, branch, secret-like strings, timeout, logs,
and event paths before running Codex.

## Event Protocol

Codex writes one of these events under `.hermes/events/`.

Complete:

```json
{
  "type": "phase_complete",
  "phase": "phase-001-discover-and-run",
  "summary": "Project runs locally",
  "changed_files": ["README.md"],
  "commands_run": ["npm install", "npm test"],
  "tests": {"status": "passed", "details": "npm test"},
  "next_request": "review_and_continue"
}
```

Blocked:

```json
{
  "type": "needs_input",
  "phase": "phase-001-discover-and-run",
  "question": "Which database should this project use?",
  "options": ["SQLite for MVP", "Postgres now"],
  "risk": "medium"
}
```

Wrapper failure:

```json
{
  "type": "process_failed",
  "phase": "phase-001-discover-and-run",
  "exit_code": 1,
  "log_path": ".hermes/codex-logs/..."
}
```

## Hermes Review Loop

After every phase:

```bash
git status --short
git diff --stat
find .hermes/events -type f -maxdepth 1 | sort | tail
```

Then:

1. Read the newest event and Codex log.
2. Run the phase validation command or focused tests.
3. If `phase_complete` and validation passes, commit and move to the next phase or open/update a draft PR.
4. If `needs_input`, ask the user through the active channel and block the Kanban task.
5. If `process_failed` or timeout, summarize the last log lines, create a smaller retry phase, or block if risky.

## Risk Gates

Autonomous continuation is allowed for:

- setup discovery
- docs
- tests
- isolated UI/API slices
- refactors with tests

Ask the user before continuing when a phase touches:

- auth, billing, payments, permissions
- deployment, DNS, systemd, firewall, infrastructure
- secrets, `.env`, SSH, GitHub credentials
- destructive migrations or data deletion
- public visibility or license changes

## Kanban Integration

For multi-phase work, create a parent Kanban task for the PRD/project and one
child task per phase. Phase tasks depend on the previous phase unless they are
safe to run in parallel. Use `kanban_block` for user decisions and
`kanban_complete` with metadata containing phase, branch, commit, event path,
tests, and PR URL.
