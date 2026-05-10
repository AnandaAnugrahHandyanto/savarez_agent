# Long-task control doc template

Use this template for long-running, autonomous, multi-agent, or session-continuity-sensitive work. The goal is that a fresh human or agent can resume from this file plus the linked evidence without reading chat history.

## Metadata

- Project:
- Mode: plan / implement / debug / review / operate
- Owner / approver:
- Primary issue / ticket:
- PRD / implementation plan:
- Control doc path:
- Created:
- Last updated:
- Current status: not_started / in_progress / blocked / validating / ready_for_review / complete / paused

## Resume capsule

This is the first section to update before handoff, context compression, pausing, or delegation.

- Active task:
- Last completed task:
- Next action:
- Current blocker:
- Decision needed from human:
- Critical files / handles:
- Latest validation evidence:
- Safe stopping point:

## Scope and success criteria

### Goal


### Non-goals / out of scope


### Acceptance criteria

- [ ]

### Authorization boundaries

- Approved actions:
- Requires explicit approval:
- Not authorized:
- Rollback / stop conditions:

## Current working state

- Repository:
- Base branch:
- Active branch:
- Worktree path:
- Pull request:
- Related run ledger:
- Latest run capsule:
- Evidence manifest:
- Deployment / environment target:

## Critical path and dependencies

| ID | Dependency / task | Owner | Status | Blocks | Notes |
| --- | --- | --- | --- | --- | --- |
| CP-001 |  |  | pending |  |  |

## Task ledger

Append new rows rather than rewriting history. Keep entries terse and evidence-backed.

| Time (UTC) | Actor | Task | Status | Evidence / handles | Notes |
| --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |

## Worker registry

Use for delegated agents, humans, background tasks, or scheduled jobs.

| Worker ID | Role | Scope | Started | Status | Stop conditions | Required handoff evidence |
| --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |  |

## Decision log

| Time (UTC) | Decision | Rationale | Alternatives considered | Approved by | Evidence |
| --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |

## Evidence index

Link to files, command outputs, CI runs, screenshots, logs, run-ledger events/capsules, and review results. Prefer immutable or hashable artifacts.

| Evidence ID | Type | Location | Summary | Safe to publish | Related task / criterion |
| --- | --- | --- | --- | --- | --- |
| EV-001 |  |  |  | unknown |  |

## Validation plan

### Planned RED tests / failing checks

- [ ]

### GREEN / focused validation

- [ ]

### Regression / integration validation

- [ ]

### Independent review

- [ ] Spec review:
- [ ] Code / quality review:
- [ ] External model review:

## Risk register

| Risk | Probability | Impact | Mitigation | Owner | Status |
| --- | --- | --- | --- | --- | --- |
|  |  |  |  |  | open |

## Operational notes

- Config / migration impact:
- Storage / retention impact:
- Privacy / redaction impact:
- Cross-platform impact:
- Observability / alerting impact:
- Rollback procedure:

## Handoff checklist

Before pausing, compressing context, or asking another worker to continue:

- [ ] Resume capsule is current.
- [ ] Active branch, worktree, PR, and latest commit are recorded.
- [ ] Next action is specific and executable.
- [ ] Blockers and authorization boundaries are explicit.
- [ ] Evidence index and manifest include the latest validation/review artifacts.
- [ ] Temporary files/worktrees/processes are either cleaned up or listed with owners.
