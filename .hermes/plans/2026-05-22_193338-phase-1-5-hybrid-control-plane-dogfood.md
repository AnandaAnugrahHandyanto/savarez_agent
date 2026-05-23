# Phase 1.5: Adversarial-Review Amendments — Hybrid Control-Plane Dogfood Plan

**Status**: In progress (adversarial amendments applied)
**Branch**: feature/hybrid-control-plane-mvp
**Date**: 2026-05-22
**Owner**: Grok-4.3 implementation subagent (via route-dev-task)

## Scope Reminder (from Phase 1 locked decisions LD-1..LD-6)

- file-based handoff is canonical; all spawn logic goes through HANDOFF_PATH
- human_reviewed_at required before worker execution
- serial gates; fail-fast ordering is load-bearing
- cost_estimated only (no real cost ledger in MVP)
- worktrees_are_sandbox: false for MVP
- opportunistic Codex usage only after canary
- No real Claude/Codex spawns in dogfood harness

## Amendment Summary

These amendments close gaps identified during adversarial review of the hybrid agent control-plane checker and fixtures.

### 1. Normalized Forbidden-Path Semantics (replaces naive prefix logic)

**Exact forbidden files** (must match basename exactly after normalization; backups allowed):
- AGENTS.md
- CLAUDE.md
- CODEX.md

**Forbidden directory prefixes** (repo-relative POSIX):
- .hermes/config/
- .hermes/schemas/
- .hermes/plans/
- .claude/
- .codex/

**Normalization rules** (applied to every path in changed_files before policy check):
- Convert to POSIX style (replace `\` with `/`, strip drive letters like `C:`, `D:`)
- Make repo-relative (strip leading `/` or absolute prefix; reject absolute paths)
- Reject empty or whitespace-only paths
- Reject any path containing `..` that would escape the repo root (traversal)
- Reject `./` prefix for prompt artifacts (dotslash AGENTS.md etc.)
- Do NOT treat `AGENTS.md.backup`, `AGENTS.md.bak`, `AGENTS.md~` as forbidden (exact match only on basename before extension)
- `is_forbidden()` must return False for backup variants; True for exact names or under forbidden prefixes

**Rejection examples** (must cause forbidden_path_writes: FAIL and nonzero exit):
- `/home/user/hermes-agent/AGENTS.md` → absolute (reject)
- `C:\\repo\\AGENTS.md` → Windows/drive (reject)
- `../AGENTS.md` → traversal escape (reject)
- `./AGENTS.md` → dotslash prompt artifact (reject)
- `   ` or `` → empty/whitespace (reject)
- `src/../AGENTS.md` → contains traversal semantics after norm (reject)
- `AGENTS.md.backup` → pass (not exact match)

**Pass examples**:
- `src/tools/foo.py`
- `AGENTS.md.backup`
- `docs/AGENTS.md.notes`

The `normalize_path()` and `is_forbidden()` helpers live in `scripts/check_hybrid_control_plane.py` and are mirrored (as constants) in the test file for deterministic assertions.

### 2. Invalid Agent Enum Coverage

New fixture:
`.hermes/test-fixtures/stub-handoff-fail-agent-enum.yaml`

```yaml
task_id: "stub-task-enum-0001"
agent: attacker_bot   # invalid enum value
completed_at: "2026-05-22T10:10:00Z"
summary: "Attempt to use disallowed agent identity"
changed_files:
  - src/foo.py
test_results:
  command_run: "scripts/run_tests.sh"
  exit_code: 0
  passed: true
```

Checker behavior:
- `--handoff stub-handoff-fail-agent-enum.yaml` → nonzero exit
- Gate output contains: `schema_validation: FAIL`
- `agent` field fails enum check against allowed list in handoff-v1 schema (claude_code, codex, ...)

### 3. Absent test_results Behavior

- Missing `test_results` key (or value null) in fixture mode → FAIL
- Output must contain: `unit_tests: SKIP` (or equivalent missing-evidence phrasing)
- Final result: nonzero
- Fixture mode never calls `command_run` / real test execution (deterministic, offline)

Add fixture coverage in `stub-handoff-fail-tests.yaml` style (test_results absent) or a dedicated case.

### 4. Empty changed_files Behavior

New fixture:
`.hermes/test-fixtures/stub-handoff-fail-empty-changed-files.yaml`

```yaml
task_id: "stub-task-empty-0001"
agent: claude_code
completed_at: "2026-05-22T10:15:00Z"
summary: "Empty diff — should fail closed"
changed_files: []
test_results:
  command_run: "scripts/run_tests.sh"
  exit_code: 0
  passed: true
```

Checker: schema/checker validation fails on empty changed_files (fail-closed policy). `schema_validation: FAIL`

### 5. Path-Edge Fixtures / Test Cases (added to test suite)

- `test_forbidden_dotslash()`: `./AGENTS.md` → blocked (normalized to AGENTS.md and exact match triggers)
- `test_forbidden_traversal()`: `../AGENTS.md`, `src/../../AGENTS.md` → blocked (contains `..`)
- `test_backup_filename_allowed()`: `AGENTS.md.backup` → allowed (is_forbidden returns False)
- Corresponding handoff fixtures updated or new edge cases covered via direct is_forbidden() unit tests

### 6. Fixture-Mode Gate Taxonomy Output (mandatory keys)

Every run in `--handoff` / `--all-handoff-fixtures` mode must emit (in machine-readable form):

- `schema_validation: PASS|FAIL`
- `forbidden_path_writes: PASS|FAIL|SKIP`
- `prompt_artifact_unchanged: PASS|FAIL|SKIP`
- `diff_size_limit: SKIP` (always in fixture mode; real git diff unavailable)
- `unit_tests: PASS|FAIL|SKIP` (SKIP when test_results missing or absent evidence)
- `cost_cap: SKIP` (no run manifest / cost ledger in MVP fixture mode)
- `human_review: PENDING` or `RESULT: AUTOMATED_PASS_HUMAN_REVIEW_REQUIRED`

Success result (all automated gates pass):
`RESULT: AUTOMATED_PASS_HUMAN_REVIEW_REQUIRED`

Exit 0 only when the above clear text is present. Nonzero for any FAIL.

### 7. --all-handoff-fixtures Strict Map Enforcement

`--all-handoff-fixtures` maintains an internal expected map of known fixture basenames:
`stub-handoff-pass.yaml`, `stub-handoff-fail-schema.yaml`, `stub-handoff-fail-forbidden.yaml`, `stub-handoff-fail-tests.yaml`, `stub-handoff-fail-agent-enum.yaml`, `stub-handoff-fail-empty-changed-files.yaml`

If any `stub-handoff-*.yaml` exists in `.hermes/test-fixtures/` that is NOT in the map → fail closed with message listing the unknown file and nonzero exit.

This prevents silent addition of untested adversarial fixtures.

### 8. Strengthened Test Assertions (pytest)

- PASS fixture (`stub-handoff-pass.yaml`):
  - `returncode == 0`
  - `stderr == ""` (no noise)
- FAIL fixtures:
  - `returncode != 0`
  - No `Traceback` in stdout/stderr
  - No progression past fail-fast gates (schema fail stops before forbidden_path check; forbidden stops before unit_tests/human_review; missing test_results includes prior static gates but does not emit human approval)
- Explicit ordering tests:
  - schema_validation FAIL → no subsequent gates executed
  - forbidden_path_writes FAIL (after schema) → unit_tests not reached
  - test_results missing/failed → prior static gates shown; no `RESULT: AUTOMATED_PASS...`

### 9. Verification Commands (run before declaring done)

```bash
python -m py_compile scripts/check_hybrid_control_plane.py tests/skills/test_hybrid_agent_control_plane.py
python scripts/check_hybrid_control_plane.py --all-handoff-fixtures
scripts/run_tests.sh tests/skills/test_hybrid_agent_control_plane.py -q
scripts/run_tests.sh tests/skills -q
git diff --check
git diff --cached --check
git status --short
```

**Safer expected-failure shell pattern** (documented in plan):
```bash
if python scripts/check_hybrid_control_plane.py --handoff .hermes/test-fixtures/stub-handoff-fail-*.yaml; then
    echo "ERROR: expected failure but got zero exit"
    exit 1
fi
echo "Correctly failed as expected"
```

Also run both `git diff --check` and `git diff --cached --check` on every verification (catch trailing whitespace, conflict markers).

## Gate Execution Order (fail-fast serial)

1. schema_validation (jsonschema or structural + agent enum)
2. forbidden_path_writes (normalized exact/prefix + traversal/absolute rejection)
3. prompt_artifact_unchanged (if applicable)
4. diff_size_limit (SKIP in fixture)
5. unit_tests (SKIP or evaluate test_results.passed)
6. cost_cap (SKIP)
7. human_review (RESULT text)

No gate after a FAIL is reached. Schema failures short-circuit; protected-path failures short-circuit dynamic gates.

## Dependencies / Optional

- PyYAML remains optional-but-required for checker (existing model preserved)
- jsonschema optional for richer validation (current implementation uses structural checks to keep stdlib-first)
- No network, no new pip installs

## Deferred Items (intentionally out of scope for this amendment)

- Real git diff integration for diff_size_limit (future Phase 2)
- Actual cost ledger from run manifests (MVP uses SKIP)
- Full JSON schema enforcement with strict enum for `agent` field (structural check sufficient for dogfood)
- Windows path normalization in live Windows env (WSL coverage only)

## How to Run the Checker in Dogfood Mode

```bash
# Happy path
python scripts/check_hybrid_control_plane.py --handoff .hermes/test-fixtures/stub-handoff-pass.yaml

# Expected failure (safer pattern)
if python scripts/check_hybrid_control_plane.py --handoff .hermes/test-fixtures/stub-handoff-fail-forbidden.yaml; then echo "unexpected pass"; exit 1; fi

# Exhaustive
python scripts/check_hybrid_control_plane.py --all-handoff-fixtures
```

All changes respect the existing style of the checker (print-based OK/FAIL, separate test file for pytest). No broad rewrites.

---

**End of Phase 1.5 plan**