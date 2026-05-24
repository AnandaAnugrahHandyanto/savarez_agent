# Janitor reference summary

Source inspiration: https://docs.bmad-method.org/llms-full.txt plus Senior Engineer Benchmark janitor-mode cleanup discipline.

Janitor is a Hermes-native cleanup workflow for brittle, vibe-coded, slop-coded, or over-automated codebases. It preserves the useful BMAD idea of progressive context and story/proof gates, but the user-facing product is named Janitor and focuses on senior-engineer cleanup with strict TDD.

## Core phases

1. Triage: reproduce symptoms, inspect logs, map data/control flow, and identify real root causes.
2. Invariants: capture public API, UX, data, migration, security, and operational contracts before risky edits.
3. Target architecture: decide whether the right fix is a targeted patch, subsystem refactor, or first-principles rewrite.
4. Cleanup stories: create small acceptance-testable stories with explicit proof requirements.
5. RED-GREEN-REFACTOR execution: write failing characterization/regression tests first, make minimal cleanup pass, then refactor safely.
6. Proof: record tests, files, logs/traces, residual risks, and PR explanation before declaring success.

## Hermes plugin mapping

- `/janitor start` / `janitor_start`: start a Senior Engineer Benchmark-inspired cleanup workflow.
- `/janitor review` / `janitor_review`: apply the benchmark scorecard (frame control, system understanding, invariants, first-principles design, execution depth, proof/operability) to a cleanup plan or completed rewrite.
- `/janitor story` / `janitor_story`: create acceptance-testable cleanup stories.
- `/janitor run` / `janitor_run`: prepare deterministic worker handoff payloads.
- `/janitor proof` / `janitor_proof`: record evidence and enforce proof gates before declaring completion.
- `/janitor daily-prompt` / `janitor_daily_prompt`: generate the self-contained daily GitHub sweep prompt for repos with charges in the lookback window, including the required activity fallback if direct charge data is unavailable.
- `/janitor status`: inspect current workflow state.
- `/janitor reset`: clear plugin state for a new workflow.
