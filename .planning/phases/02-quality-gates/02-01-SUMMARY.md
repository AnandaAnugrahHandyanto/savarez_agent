---
phase: 02-quality-gates
plan: 01
signature:
  role: executor
  harness: claude-code
  platform: claude
  vendor: anthropic
  model: claude-sonnet-4-6
  reasoning_effort: not_available
  profile: not_available
  gsd_version: 1.19.10
  generated_at: "2026-04-25T16:54:07Z"
  session_id: not_available
  provenance_status:
    role: derived
    harness: exposed
    platform: derived_from_harness
    vendor: derived_from_harness
    model: exposed
    reasoning_effort: not_available
    profile: not_available
    gsd_version: not_available
    generated_at: exposed
    session_id: not_available
  provenance_source:
    role: artifact_role
    harness: runtime_context
    platform: derived_from_harness
    vendor: derived_from_harness
    model: runtime_context
    reasoning_effort: not_available
    profile: not_available
    gsd_version: not_available
    generated_at: writer_clock
    session_id: not_available
subsystem: code-quality
tags: [ruff, ty, lint, type-check, measurement, baseline]
requires: []
provides:
  - Empirical ruff violation baseline (6,809 total; 742 actionable non-E501)
  - Per-rule and per-package breakdown for 02-02 planning
  - Format-check scope measurement (249/280 files need reformatting)
  - ty type-check pilot baseline (204 errors in 17 agent/ files; 0 in path_security.py)
  - Reproduction commands for all measurements
affects: [02-02, 02-03, 02-04]
tech-stack:
  added: []
  patterns: [measurement-before-fix, --isolated flag to bypass disabled ruff config]
key-files:
  created:
    - .planning/phases/02-quality-gates/02-01-MEASUREMENT.md
  modified: []
key-decisions:
  - "Exclude E501 from enforced ruleset in 02-03: 89% of violations are line-too-long; enforcing it blocking would make CI unpassable until a mass-reformat phase ships"
  - "Ship ruff format --check as warning-only or per-path excluded in 02-03: 249 of 280 in-scope files (88.9%) need reformatting -- blocking would break every PR"
  - "Ship ty CI step with continue-on-error: true in 02-04: 204 errors > 50 threshold from CONTEXT.md D-F"
  - "Fix [tool.ty.src] exclude = ['**'] in 02-04 before adding CI step: current config silently passes, giving a false green"
  - "02-04 primary target is agent/auxiliary_client.py (116 of 204 errors); dominant pattern is None-vs-typed-param requiring str | None union annotation"
patterns-established:
  - "Measurement-before-fix: run --isolated ruff check to bypass disabled config and get actual baseline numbers before making any changes"
duration: 15min
completed: 2026-04-25
context_used_pct: 25
---

# Phase 02 Plan 01: Measurement Summary

**Empirical ruff + ty baseline: 6,809 violations (89% E501, 742 actionable), 204 ty errors in agent/, 0 in tools/path_security.py**

## Performance
- **Duration:** ~15 minutes
- **Tasks:** 2/2 completed
- **Files modified:** 1 (measurement report created)

## Accomplishments
- Ran ruff with E,F,I ruleset using `--isolated` to bypass the disabled project config; captured 6,809 violations across 8 packages
- Identified that E501 (line-too-long) accounts for 6,067 of 6,809 violations (89.1%) — a critical sizing insight for 02-02 and 02-03
- Quantified 526 auto-fixable violations vs 6,283 manual, with actionable (non-E501) set of 742
- Measured format-check scope: 249 of 280 files need reformatting — codebase is NOT format-clean, blocking format-check would be impractical
- Ran ty 0.0.21 on pilot scope (agent/ + tools/path_security.py); identified 204 errors in 17 files, 0 in path_security.py
- Discovered that the existing `[tool.ty.src] exclude = ["**"]` causes a false-green when checking directories — 02-04 must fix the config first
- Wrote complete measurement report with reproduction commands at `.planning/phases/02-quality-gates/02-01-MEASUREMENT.md`

## Task Commits
1. **Task 1 + 2: Run ruff and ty measurements, write report** - `2eb33425`

## Files Created/Modified
- `.planning/phases/02-quality-gates/02-01-MEASUREMENT.md` - Full measurement report with all 8 required sections, reproduction commands, and implications for downstream plans

## Decisions & Deviations

**Key decisions from measurement findings:**

1. **E501 exclusion recommended for 02-03:** With 6,067 E501 violations (89% of total), enforcing line-length as a blocking CI rule is impractical until a dedicated reformat phase ships. 02-03 should add `ignore = ["E501"]` to the ruff config.

2. **Format-check non-blocking for 02-03:** 249/280 in-scope files need reformatting. Per CONTEXT.md D-D decision, this phase ships format-check with per-path excludes or as a non-blocking annotation — not as a hard gate.

3. **ty CI step with continue-on-error for 02-04:** 204 errors exceeds the 50-error threshold from CONTEXT.md D-F. Ship non-blocking for first merge cycle.

4. **False-green ty config bug:** The `[tool.ty.src] exclude = ["**"]` setting causes `ty check agent/` to silently pass. This is a pre-existing misconfiguration. 02-04 must fix this before the CI step means anything.

**Deviations from plan:**

- **Tool installation:** Plan specified creating a temp venv with `uv venv /tmp/lint-measure`. `uv` was not available in the execution environment (not on PATH). Used the existing hermes-agent venv which already had `ruff 0.15.11` and `ty 0.0.21` installed — both meeting version requirements. Documented in report's "Tool versions" section.

- **ruff --isolated flag:** Plan didn't mention the `exclude = ["*"]` config bypass. Discovered that without `--isolated`, ruff reports "No Python files found" due to the global exclude. Used `--isolated` for all ruff measurements; documented this in reproduction commands.

- **ty config bypass:** Plan assumed ty would check files directly. Discovered that `[tool.ty.src] exclude = ["**"]` causes directory-level checks to silently pass (false green). Created a temporary ty.toml without the global exclude to get real numbers. Documented both the false-green behavior and the measurement method.

## User Setup Required
None - this plan only created a planning document; no external service configuration required.

## Next Phase Readiness

**02-02 (ruff auto-fix):** Ready. The per-package breakdown shows where the 526 auto-fixable violations live. Start with packages that have high I001 counts (hermes_cli: 141, gateway: 109, tools: 79). Each package gets its own commit.

**02-03 (pyproject.toml + CI):** Ready with clear guidance: remove `exclude = ["*"]`, set `select = ["E", "F", "I"]`, add `ignore = ["E501"]`, ship format-check non-blocking.

**02-04 (ty pilot):** Ready. Primary action is fixing `[tool.ty.src] exclude = ["**"]` and then addressing 204 errors in 17 agent/ files. Focus on `auxiliary_client.py` (116 errors) first.

## Self-Check: PASSED
- `.planning/phases/02-quality-gates/02-01-MEASUREMENT.md` exists and is non-empty
- Commit `2eb33425` exists in git log
- All required sections present in measurement report (verified by grep)
- No source files outside .planning/ modified (verified by git status)
