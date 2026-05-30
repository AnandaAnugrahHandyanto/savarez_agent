# vibecode-pro-max-kit Absorption Notes

Date: 2026-05-30

Source: `withkynam/vibecode-pro-max-kit`

Decision: do not install the kit wholesale. Treat it as a reference library for Hermes skills, orchestration checks, and diagnostics.

## Why Not Install It Directly

- It ships its own `.claude/`, `.codex/`, `AGENTS.md`, `CLAUDE.md`, and `process/` structure.
- It defines a separate 12-agent RIPER-style workflow.
- Hermes already has a managed Agent roster, model pool, 9119 dashboard, runtime registry, and external Claude/Codex CLI boundaries.
- Installing the kit directly would create a second source of truth for Agent routing and process state.

## First Absorbed Pieces

- `vc-scout` -> `skills/software-development/codebase-scout`
- orchestration status and closeout protocol -> `skills/software-development/hermes-orchestration-closeout`
- `vc-audit-context` concept -> `skills/software-development/context-skill-audit`
- selected `vc-debug` references and `find-polluter.sh` -> `skills/software-development/systematic-debugging`

## Explicitly Not Absorbed

- `.claude/agents/*`
- `.codex/*`
- `CLAUDE.md`
- `AGENTS.md`
- `process/*`
- JavaScript hook code under `.claude/hooks/*`

Hook concepts such as privacy blocking and scout reminders may be reimplemented later as Hermes-native Python preflight checks.

## Agent Mapping

- `deepseek-tui`: codebase scouting, systematic debugging, quick verification scans.
- `claude`: implementation after scout/plan boundaries are clear.
- `codex`: read-only architecture review, context/skill audit, closeout review.
- `hermes-internal`: decomposition, context/skill audit, orchestration closeout.
- `ambrosini`: high-risk closeout and acceptance review.

## Follow-Up Candidates

- STRIDE/OWASP security review from `vc-security`.
- Scenario generation from `vc-scenario`.
- Pre-implementation adversarial review from `vc-predict`.
- Context health analysis from `vc-context-engineering`.
