---
name: codex-omx-ralplan-ralph-handoff
description: Use the local Codex + oh-my-codex setup to run $ralplan with a detailed grounding document, then execute the approved plan via $ralph and verify the produced artifacts.
version: 1.0.0
author: Orbiracle
license: MIT
metadata:
  hermes:
    tags: [codex, omx, ralplan, ralph, planning, execution, verification]
---

# Codex OMX Ralplan → Ralph Handoff

Use when the user explicitly wants **Codex** to:
1. receive a **very detailed task/context brief**,
2. produce a plan via **`$ralplan`**, and then
3. implement that plan via **`$ralph`**.

This is specifically for the local environment where Codex has **oh-my-codex (OMX)** installed and the `ralplan` / `ralph` skills are available under `~/.codex/skills/`.

## When to use
- User says things like:
  - “codex 이용해서 $ralplan으로 계획 짜고 그대로 $ralph로 구현해”
  - “have Codex plan first, then implement”
  - “use ralplan / ralph, not generic planning”
- The task is substantial enough that a written context artifact improves results.
- The repo is already a git repo and Codex CLI is available.

## Why this works
Codex + OMX can do more than a generic `codex exec` prompt if you give it:
- a **repo-local context doc**,
- the exact **OMX skill names**,
- a request to create the **plan/context artifacts**, and
- a separate **execution pass** after checking the plan output.

In practice, this reduces ambiguity and makes the Codex run produce reusable planning artifacts under `.omx/` before implementation starts.

## Prerequisites
Check these first:
- `codex` CLI is installed and runnable
- repo is a git repository
- OMX skills exist:
  - `~/.codex/skills/ralplan/SKILL.md`
  - `~/.codex/skills/ralph/SKILL.md`
- local Codex config points at the expected model/runtime (`~/.codex/config.toml`)

Useful checks:
```bash
command -v codex
codex --help | head -n 40
find ~/.codex/skills -maxdepth 2 -type f | sed -n '1,120p'
sed -n '1,220p' ~/.codex/skills/ralplan/SKILL.md
sed -n '1,260p' ~/.codex/skills/ralph/SKILL.md
```

## Workflow

### 1. Write a detailed context file first
Create a repo-local markdown brief that includes:
- goal
- current repo/workdir
- important existing files
- what has already been tried
- what failed and why
- user preferences / explicit direction changes
- target architecture or desired deliverables
- verification expectations

Good location pattern:
- `docs/plans/<task-date-or-slug>/codex_<task>_context.md`

Why this mattered:
- Codex followed the brief more reliably when it could read a concrete file first rather than being given one huge inline prompt only.

### 2. Run Codex with `$ralplan` first
Use `codex exec --yolo` and explicitly tell it to:
- read the context file first
- ground itself in the repo state
- use installed `ralplan` semantics
- create the relevant `.omx/context/...` and `.omx/plans/...` artifacts
- include concrete file paths, schema choices, verification steps, risks

Pattern:
```bash
codex exec --yolo '$ralplan "Read <context-file> first, ground yourself in the current repo state, then produce a consensus plan for <task>. Use the installed ralplan skill semantics, create the appropriate plan/context artifacts in the repo, and do not skip concrete file paths, schema decisions, verification steps, or risks."'
```

### 3. Inspect the produced plan artifacts before execution
Do **not** blindly launch `$ralph` without checking that plan files actually exist.

Look for:
- `.omx/context/<slug>-<timestamp>.md`
- `.omx/plans/prd-<slug>.md`
- `.omx/plans/test-spec-<slug>.md`

Read them and confirm:
- the task was understood correctly
- the source-of-truth paths are right
- acceptance criteria are concrete
- verification commands are present

### 4. Launch `$ralph` as a separate Codex execution
Use a second Codex run and pass:
- the approved PRD path
- the test-spec path
- the original context file as extra grounding
- explicit instruction to keep the agreed baseline/source-of-truth
- explicit instruction to deliver generated artifacts + tests + docs + verification

Recommended pattern:
```bash
codex exec --yolo '$ralph "Implement the approved plan in <prd-path> together with <test-spec-path>. Use <context-file> as additional grounding. Deliver the analysis layer / renderer / generated artifacts / tests / documentation. Keep <baseline> as the source art baseline. Run verification commands and do not stop until the implementation is complete and verified."'
```

### 5. Prefer background mode for `$ralph`
For long runs, use background execution and monitor it externally.

Why:
- Ralph can run long enough to hit ordinary foreground timeouts.
- Background mode lets you keep checking progress and verify intermediate outputs.

Recommended Hermes pattern:
- start Codex in background with PTY
- use `process.wait`, `process.poll`, and `process.log`
- watch for key strings like `pytest`, `FAILED`, `ERROR`, generated artifact names, or approval markers

### 6. Treat Codex timeout != failure
A long-running Codex process can still be making progress after Hermes `wait` timeouts.

What worked here:
- inspect files on disk while Codex is still running
- check whether key files/artifacts already exist
- run independent verification yourself once outputs appear
- if Codex appears stuck after implementation is clearly complete, kill the process and proceed with your own verification summary

### 7. Treat watch-pattern notifications as hints, not completion
When running Codex in background with watch patterns, a notification like a generated artifact path or a test filename appearing in logs is only a **mid-run signal**.

It does **not** mean the full Ralph run is complete.

What to do:
- treat watch matches as a trigger to inspect outputs on disk
- verify whether the referenced artifact actually exists
- separately run tests / compile / visual checks yourself
- only mark the run complete after external verification, not because the watch pattern fired

This mattered here because an `ep001_ballooned_longscroll.png` watch-pattern alert appeared while the Codex Ralph process was still running.

### 7b. When one clear regression remains, rerun Ralph with a narrow continuation scope
If a broad Ralph run fixes most of the task but leaves **one clearly identified regression** (for example, a single renderer crash or one failed assertion path), do not restart the whole task with the original wide prompt.

Instead:
- keep the current repo state
- kill any lingering/stuck Codex process once the partial work is safely on disk
- launch a **new Ralph run** that explicitly says it is continuing from the current tree
- name the exact remaining blocker (`RuntimeError`, failing test name, bad predicate, etc.)
- instruct Codex not to undo the already-verified fixes

This reduces drift and worked well for the EP001 overflow/tail run where the first Ralph pass fixed import/test/manifest issues, and the second narrow pass cleanly removed the remaining `l01` placement regression.
## What to verify yourself after Codex runs
Do not rely only on Codex’s self-report.

Check at least:
- expected new files exist
- generated artifacts exist
- tests run and pass
- syntax/compile checks pass
- visual artifact looks plausibly correct when relevant

Example verification commands:
```bash
git status --short -- <paths>
python -m pytest <test-file> -q
python -m compileall <dir>
```

For visual outputs, inspect with vision tooling if available.

## Good report shape afterward
Summarize in this order:
1. context file written
2. `ralplan` artifacts produced
3. `ralph` implementation outputs produced
4. verification results
5. remaining manual-review risks, if any

## Pitfalls
- Don’t assume `ralplan` / `ralph` exist; check `~/.codex/skills` first.
- Don’t skip the context doc; large tasks become under-specified fast.
- Don’t trust a foreground timeout as proof of failure.
- Don’t skip independent verification after Codex says it is done.
- Don’t forget that local Codex may use `.venv` instead of `venv`; verify the repo’s actual Python environment before embedding commands in plans.
- If Codex is still running but all required files and passing tests already exist, it can be correct to stop the lingering process after external verification.

## Reusable outcome from this run
This workflow successfully produced:
- `.omx/context/...` grounding artifacts
- `.omx/plans/prd-...md`
- `.omx/plans/test-spec-...md`
- implementation files
- generated output artifacts
- passing pytest verification

That makes it a good default when the user wants **Codex-native planning first, Codex-native execution second** under OMX.
