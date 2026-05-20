---
name: spec-driven-development
description: "Use when implementing medium or large features with a spec-first lifecycle: constitution, specification, plan, tasks, implementation, and validation. Inspired by GitHub Spec Kit, adapted for Hermes."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [specs, planning, implementation, spec-driven-development, quality-gates]
    related_skills: [methodology-router, writing-plans, subagent-driven-development, test-driven-development, requesting-code-review]
---

# Spec-Driven Development

## Overview

Spec-driven development makes the specification the source of truth. Code is the implementation of an explicit contract, not the place where requirements are discovered accidentally.

This skill adapts the GitHub Spec Kit style for Hermes. Use it when a task is too important or too broad for a direct edit.

## When to Use

Use when:
- A feature affects multiple files or components.
- The user asks for a new capability, integration, protocol, or architecture.
- Acceptance criteria matter.
- Several implementation paths are possible.
- Work may be delegated to subagents or kanban workers.

Don't use when:
- The change is a trivial typo/config tweak.
- A failing test already defines the bug clearly and the fix is local.
- The user explicitly asks for a spike/prototype; use `spike` first, then come back to this skill if building for real.

## Artifact Layout

Prefer project-local artifacts under `.hermes/` when no repo convention exists:

```text
.hermes/
  constitution.md              # standing engineering principles for this repo/project
  specs/
    <feature-slug>/
      spec.md                  # what and why
      plan.md                  # how
      tasks.md                 # bite-sized execution list
      validation.md            # test plan, checks, acceptance evidence
```

If the repo already has `docs/specs/`, `docs/plans/`, `AGENTS.md`, or another convention, follow the repo convention and cross-link from `.hermes/` only when useful.

## Process

### 1. Constitution Gate

Check for durable project rules:

- `AGENTS.md`
- `CLAUDE.md`
- `.hermes/constitution.md`
- existing architecture docs
- package/test/CI conventions

If missing and the feature is large, create a minimal constitution:

```markdown
# Project Constitution

## Principles
- Keep changes testable and reversible.
- Prefer extension points over core rewrites.
- Separate personal memory, project memory, and knowledge-corpus retrieval.

## Quality Gates
- Targeted tests for touched behavior.
- Full relevant suite before merge.
- No secrets in logs, commits, or docs.
```

Gate passes when project constraints are known enough to prevent avoidable design drift.

### 2. Specify Gate

Write `spec.md` before implementation.

Required sections:

```markdown
# <Feature> Specification

## Goal
One paragraph describing the outcome.

## Users / Actors
Who uses this and in what context.

## Requirements
- R1: Observable behavior.
- R2: Integration behavior.
- R3: Failure/edge behavior.

## Non-Goals
- Explicitly excluded scope.

## Acceptance Criteria
- [ ] User-visible or testable outcome.
- [ ] Verification command or manual check.

## Risks
- Security, privacy, cost, compatibility, migration, performance.
```

Gate passes when requirements and non-goals are explicit.

### 3. Plan Gate

Write `plan.md` using `writing-plans` discipline.

Required sections:

```markdown
# <Feature> Implementation Plan

## Architecture
Explain the chosen design and rejected alternatives.

## Files to Change
- Create/modify exact paths.

## Dependency / Config Changes
- New packages, env vars, config keys, migrations.

## Test Strategy
- Unit tests.
- Integration tests.
- Manual verification.

## Rollback Plan
How to disable/revert safely.
```

Gate passes when a competent subagent could implement without guessing.

### 4. Tasks Gate

Write `tasks.md` as small ordered tasks.

Each task should include:

- Objective.
- Exact files.
- RED test or verification-first step.
- GREEN implementation step.
- Refactor/cleanup step if needed.
- Command to verify.
- Commit message suggestion.

Use `subagent-driven-development` when tasks are independent or benefit from fresh context and review.

Gate passes when every task is 2–15 minutes and independently verifiable.

### 5. Implement Gate

Execution rules:

1. Do not implement before spec and plan gates pass unless the user explicitly requests a spike.
2. Use TDD for behavior-producing code.
3. Use `delegate_task` for independent research/review/implementation chunks when it improves quality or speed.
4. Run targeted verification after each meaningful task.
5. Keep commits coherent.

Gate passes when all acceptance criteria have evidence.

### 6. Validation Gate

Write or update `validation.md` with actual evidence:

```markdown
# Validation

## Commands Run
- `pytest tests/foo/test_bar.py -q` — passed
- `python scripts/check_config.py` — passed

## Acceptance Criteria Evidence
- [x] R1 proven by test X.
- [x] R2 proven by command Y.

## Known Gaps
- Any limitation or follow-up.
```

Gate passes when final claims are backed by tests, tool outputs, docs, or explicit assumptions.

## Hermes Integration Notes

- Use `todo` for in-session task control.
- Use `session_search` when prior decisions may exist.
- Use `skill_view` for related methodology skills before execution.
- Use `delegate_task` for parallel research, implementation, or review.
- Use kanban for durable multi-worker execution beyond the current turn.
- Use memory only for stable facts and reusable lessons; do not store task-progress logs.

## Common Pitfalls

1. **Spec as afterthought.** A spec written after code is documentation, not a contract.
2. **No non-goals.** Missing non-goals causes scope creep.
3. **Tasks too large.** If a task needs multiple unrelated files and cannot be verified alone, split it.
4. **No rollback path.** Every integration should have disable/revert instructions.
5. **Validation theater.** Listing planned commands is not evidence. Record actual commands run and outcomes.

## Verification Checklist

- [ ] Constitution/project rules checked.
- [ ] `spec.md` has requirements, non-goals, acceptance criteria, risks.
- [ ] `plan.md` has architecture, file list, dependencies, tests, rollback.
- [ ] `tasks.md` is ordered and bite-sized.
- [ ] Implementation followed TDD where applicable.
- [ ] Validation records actual evidence.
