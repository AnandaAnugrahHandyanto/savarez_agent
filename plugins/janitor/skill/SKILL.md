---
name: workflow
description: "Run Janitor cleanup workflows inside Hermes with TDD, proof gates, and daily GitHub PR automation."
---

# Janitor workflow

Use this plugin skill when the user mentions Janitor, senior-engineer cleanup, vibe-coded/slop-coded code, first-principles rewrites, or daily repository cleanup sweeps.

## Workflow

1. Start with `janitor_start` or `/janitor start --path ...` for a cleanup workflow.
2. Create cleanup stories with `janitor_story`; every story must have acceptance criteria, preserved invariants, and proof requirements.
3. Use `janitor_run` to produce worker handoff payloads before delegating or executing.
4. Use `janitor_review` or `/janitor review` for cleanup work to apply the Senior Engineer Benchmark scorecard before calling it good.
5. Use `janitor_proof` to record evidence: tests, files, logs, trace/export locations, and known risks.
6. Do not declare Janitor work complete unless the proof gate is satisfied.

## Strict TDD discipline

For production code changes, follow RED-GREEN-REFACTOR:

- **RED:** write or update a focused failing characterization/regression test first and run it to prove it fails for the expected reason.
- **GREEN:** make the smallest cleanup that passes the test.
- **REFACTOR:** simplify only while tests remain green.

The PR body must include the RED/GREEN/REFACTOR evidence and exact test commands/results.

## Daily GitHub sweep

Use `janitor_daily_prompt` or `/janitor daily-prompt --owner crisweber2600 --lookback-hours 24` to generate the self-contained cron prompt for daily sweeps. The prompt targets repositories with charges in the lookback window and requires the agent to explicitly report when direct per-repository charge data is unavailable and it falls back to recent push/commit/workflow activity.

Each repository PR must explain:

- what changed;
- why it was worth doing;
- why the cleanup is safe;
- RED/GREEN/REFACTOR evidence;
- tests run;
- residual risks.

## Senior-engineer janitor mode

Trigger this mode when the user says the codebase is vibe-coded, slop-coded, brittle, full of patches, going down in production, or needs a senior-engineer cleanup. The goal is to optimize for the Senior Engineer Benchmark behavior described in Lenny's interview with Dan Shipper and Every's benchmark notes:

- understand why the system fails before changing code;
- preserve working contracts and product behavior;
- rip out accidental architecture when warranted, instead of adding edge patches;
- rewrite subsystems from first principles only after capturing invariants;
- prove the result with characterization tests, regression tests, logs/traces, and a residual-risk review.

Recommended intake:

```text
/janitor start --path /repo --symptoms "servers go down every 10 minutes" --constraints "keep public API stable" "Stabilize and simplify the app"
```

After `janitor_start`, create stories for reconnaissance, invariant capture, target architecture, seam extraction, rewrite/refactor, migration, and proof. A cleanup story is not ready unless it says what behavior must stay unchanged and what proof will demonstrate the cleanup did not just move the slop around.

### Senior Engineer Benchmark scorecard

Use this as the janitor-mode review rubric:

- **Frame control (20 pts):** don't blindly obey a narrow issue list; decide whether the real job is root-cause cleanup, subsystem rewrite, or targeted patch.
- **System understanding (15 pts):** map data flow, lifecycle, failure modes, ownership boundaries, and hidden coupling before editing.
- **Invariant preservation (15 pts):** capture public API, UX, data, migration, security, and operational invariants with characterization tests/probes.
- **First-principles design (20 pts):** replace accidental architecture with a simpler design when warranted; delete slop rather than wrapping it.
- **Execution depth (15 pts):** carry the rewrite through production-relevant seams, migrations, and call sites instead of stopping at a cosmetic patch.
- **Proof and operability (15 pts):** prove with tests, lint/type checks, logs/traces, load/error-path evidence, rollback notes, and residual-risk review.

Call `/janitor review --evidence "..." "notes"` or `janitor_review` when reviewing a plan or completed cleanup. Missing proof in any dimension is a blocker, not a caveat.

## Hermes-specific rules

- Prefer Hermes tools for actual execution and verification.
- Use `delegate_task` only after `janitor_run` has produced explicit story handoff text.
- Store durable workflow state through the plugin; do not rely on chat history alone.
