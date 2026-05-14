---
name: idea-to-execution-lifecycle
description: "Use when turning Tanner's product ideas into specs, technical debt, execution plans, implementation PRs, and archived/validated lifecycle records."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [planning, specs, technical-debt, execution-plans, pull-requests, lifecycle]
    related_skills: [writing-plans, subagent-driven-development, github-pr-workflow, claude-code]
---

# Idea → Spec → Debt/Plan → PR Lifecycle

## Overview

Use this skill to keep Tanner's ideas moving through a durable product-development lifecycle instead of becoming loose chat context. The goal is a clean chain of custody:

```text
idea / observation
  → durable spec update or new spec
  → technical debt item or immediate execution plan
  → active execution plan
  → implementation PR
  → PR merged / closed
  → debt archived, specs validated/refined, plans archived
```

Specs are durable behavior contracts. Technical debt tracks known gaps between current and target behavior. Execution plans are tactical, time-bounded work instructions. PRs prove and land the work. Archive notes preserve what actually happened.

## When to Use

Use when Tanner says things like:

- "turn this idea into specs/plans"
- "add this to technical debt"
- "make exec plans from this gap analysis"
- "execute the next plan"
- "close out the debt after the PR merged"
- "validate/refine the specs after implementation"
- "organize this repo like specs + debt + exec plans"

Also use when a conversation produces a durable product decision, missing capability, discovered issue, or next implementation slice.

Do not use for tiny one-off edits that do not affect product direction, specs, debt, or plan lifecycle.

## Canonical Repository Shape

Prefer an existing repo convention over inventing a new one. If no convention exists, use this shape:

```text
specs/
  README.md                         # index of durable subsystem contracts
  <subsystem>.md                    # behavior-first spec files

docs/
  TECHNICAL_DEBT.md                 # stable debt register with IDs and links
  exec-plans/
    README.md                       # plan lifecycle/current ordering if repo wants it
    active/                         # exactly one or very few current plans
    backlog/                        # not-yet-selected dated plans
    archive/                        # completed/superseded plans with status notes
```

Keep these layers distinct:

- **Idea capture**: raw user intent, sources, hypotheses, alternatives.
- **Spec**: target behavior and invariants; should remain useful after implementation.
- **Technical debt**: explicit current-vs-target gap with stable ID, severity, owner/scope, and links.
- **Execution plan**: exact files, steps, tests, validation, and PR proof for one implementation slice.
- **PR**: concrete branch that changes code/docs and records proof.
- **Archive**: completed plan/debt notes linking to PRs and updated specs.

## Intake: Classify the Idea

Before writing files, inspect disk truth:

```bash
git status --short --branch
find specs docs/exec-plans -maxdepth 2 -type f 2>/dev/null | sort
sed -n '1,220p' docs/TECHNICAL_DEBT.md 2>/dev/null || true
sed -n '1,220p' specs/README.md 2>/dev/null || true
```

Classify the idea into one of four paths:

1. **Spec-first** — the idea changes desired behavior, system contracts, lifecycle semantics, or product philosophy.
2. **Debt-first** — the idea identifies a gap, missing capability, broken invariant, or known compromise.
3. **Plan-first** — the idea is already scoped and ready to execute without broader spec/debt work.
4. **Spike-first** — the idea is plausible but uncertain; create a short research/spike plan before specs or implementation.

Default to **spec-first** when the idea affects durable behavior. Default to **debt-first** when current behavior is known to fall short. Go straight to an execution plan only when target behavior and acceptance criteria are already clear.

## Spec Writing / Refinement

A spec should answer "what must be true?" not "what task do we do today?"

Each spec should include:

- Purpose / subsystem boundary
- Current behavior if relevant
- Target behavior
- Invariants and non-goals
- Lifecycle/state transitions where relevant
- Validation signals or acceptance criteria
- Links to debt IDs and execution plans
- Open questions only if they materially affect implementation

When refining after implementation:

1. Read the merged PR diff and tests, not just the PR summary.
2. Update the spec to match verified behavior, not wishful behavior.
3. If implementation intentionally diverged from old target behavior, either update the target or create a debt item for the remaining gap.
4. Remove stale open questions that were answered by the PR.

## Technical Debt Register

A good debt item is stable and actionable. Use IDs like `TD-001` if the repo already does, otherwise follow the repo's convention.

Debt item template:

```markdown
### TD-XXX — Short title

**Status:** open | active | blocked | resolved | archived  
**Severity:** low | medium | high  
**Area:** subsystem / files / feature area  
**Specs:** [`specs/<subsystem>.md`](../specs/<subsystem>.md)  
**Plans:** [`docs/exec-plans/backlog/YYYY-MM-DD-slice.md`](exec-plans/backlog/YYYY-MM-DD-slice.md)

**Current state:** What exists today.

**Target state:** What should be true.

**Why it matters:** User/product/operator impact.

**Candidate implementation:** Likely implementation path; keep this high level.

**Resolution notes:** Fill when archived/resolved with PR links and validation.
```

Debt rules:

- Link every debt item to at least one spec or explicitly say why no spec exists yet.
- Link execution plans when they are created.
- Do not delete resolved debt casually; mark resolved/archive with PR and date when the repo wants historical traceability.
- If a PR only partially resolves debt, split the remaining work into a new debt item or update the existing item with remaining scope.

## Execution Plan Lifecycle

Execution plans are tactical. They should be concrete enough for a fresh agent to execute.

Plan states:

- **backlog**: valid future work, not selected now.
- **active**: selected current implementation slice.
- **archive**: completed, superseded, or deliberately abandoned.

When promoting a plan:

1. Sync the branch/base first.
2. Move exactly one plan from `backlog/` to `active/` unless parallel work is intentional.
3. Change the plan status line to `active`.
4. Update `docs/exec-plans/README.md` if present.
5. Commit the lifecycle move separately or include it in the implementation PR if that is the repo convention.

Execution plan minimum contents:

```markdown
# <Feature/Slice> Execution Plan

**Status:** backlog | active | archived
**Date:** YYYY-MM-DD
**Specs:** links
**Debt:** links
**Target PR:** optional branch/PR once known

## Goal

## Non-goals

## Context

## Tasks
- [ ] Task 1: exact files, expected behavior, validation
- [ ] Task 2: exact files, expected behavior, validation

## Validation
- targeted tests
- full/local checks
- artifact or behavior proof

## Completion / Archive Notes
```

Prefer several narrow plans over one giant plan. Each plan should map to one coherent PR when possible.

## Executing Plans and Closing PRs

When Tanner asks to execute a plan:

1. Load `writing-plans`, `subagent-driven-development`, and `github-pr-workflow` as relevant.
2. Verify live branch, open PRs, plan location, and dirty state.
3. Create a feature branch from current `main` unless continuing an existing PR branch.
4. Execute the plan task-by-task. Use subagents or Claude Code only when they improve throughput or isolation.
5. Run required validation and capture proof.
6. Update the active plan with status/proof notes.
7. Commit and push.
8. Open or update the PR with:
   - summary
   - spec/debt/plan links
   - validation commands and results
   - screenshots/artifact excerpts when behavior or evidence output changed
9. Watch CI if available; distinguish local validation from CI status.

When a PR is merged or closed:

1. Fetch/sync `main` and verify the PR state.
2. Read the merge commit / PR diff / changed tests.
3. Update affected specs to match landed behavior.
4. Mark linked debt resolved, partially resolved, or still open.
5. Move completed active plans to `archive/` with a short archive note:
   ```markdown
   **Archive status:** Completed by PR #123 on YYYY-MM-DD. Validation: <summary>. Remaining work: <links or none>.
   ```
6. If the PR was closed unmerged, mark the plan superseded/abandoned and keep or revise debt accordingly.
7. Create the next backlog/active plan if obvious; otherwise report the next decision fork.

## Spec Validation After Implementation

After implementation, validate specs against reality:

- Do tests exercise the key invariants named in the spec?
- Does runtime behavior match spec terminology and state transitions?
- Did the PR introduce a new limitation that belongs in technical debt?
- Are old debt links now stale or resolved?
- Does README/project map still point to the right specs, debt, and plans?

If a spec claims a behavior exists but no test/proof covers it, either add validation in the implementation PR or add a debt item for missing proof.

## PR Closure and Debt Archival Checklist

Use this checklist before declaring a lifecycle closed:

- [ ] PR is merged, or closed-unmerged status is explicit.
- [ ] Local `main`/base branch is synced after merge.
- [ ] Specs were read and updated/refined as needed.
- [ ] Debt item status reflects reality: resolved, partial, still open, or superseded.
- [ ] Active plan moved to archive with PR/date/validation note.
- [ ] Next active/backlog plan selected or explicitly deferred.
- [ ] README / specs index / exec-plan index links still resolve.
- [ ] Validation commands and CI state are reported separately.

## Common Pitfalls

1. **Turning every idea straight into tasks.** If the behavior contract is unclear, write/refine the spec first.
2. **Burying durable design in execution plans.** Plans expire; specs survive.
3. **Deleting technical debt after a PR.** Prefer resolved/archive notes with PR links unless the repo explicitly wants pruning.
4. **Letting active plans accumulate.** Keep active small; backlog is for parked work.
5. **Calling local tests CI.** Report local validation and GitHub checks separately.
6. **Archiving without reading the merged diff.** PR bodies can lie or drift; validate against actual landed changes.
7. **Forgetting partial resolution.** If a PR closes 70% of a debt item, keep the remainder visible.

## Minimal Commands

```bash
# Inspect lifecycle state
git status --short --branch
find specs docs/exec-plans -maxdepth 2 -type f 2>/dev/null | sort

# Inspect PR after merge/close
gh pr view <N> --json state,mergedAt,mergeCommit,headRefName,baseRefName,files,url

# Verify docs links with a repo-local checker if present; otherwise run the repo's normal validation
python3 -m pytest
python3 -m compileall src tests
```

## Remember

```text
Ideas become durable when they are linked.
Specs define target truth.
Debt records gaps.
Execution plans move one slice.
PRs prove the slice.
Archive notes close the loop.
```
