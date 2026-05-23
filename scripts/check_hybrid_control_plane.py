#!/usr/bin/env python3
"""
scripts/check_hybrid_control_plane.py

Conservative MVP verification script for the hybrid agent control plane.
Stdlib-only where possible. Requires PyYAML for YAML parsing.

Checks:
  1. Required files exist.
  2. YAML fixtures load and have expected structure/values.
  3. Plan file contains all required caveat phrases (C-1 through C-6).
  4. .gitignore has correct entries (ignores runtime dirs, not all of .hermes/).

Run: python scripts/check_hybrid_control_plane.py
Exit 0 = all checks pass. Exit 1 = one or more failures.
"""
import sys
import os

# ---------------------------------------------------------------------------
# Attempt to import PyYAML
# ---------------------------------------------------------------------------
try:
    import yaml
except ImportError:
    print("ERROR: PyYAML is not installed.")
    print("Install it: pip install pyyaml   (or: pip install -e '.[dev]')")
    print("PyYAML is required for YAML fixture validation.")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REQUIRED_FILES = [
    # Phase 0 artifacts
    ".hermes/schemas/handoff-v1.yaml",
    ".hermes/config/capability-matrix.yaml",
    ".hermes/config/gate-taxonomy.yaml",
    ".hermes/config/eval-matrix.yaml",
    ".hermes/config/recovery-runbook.md",
    ".hermes/templates/run-manifest.yaml.j2",
    ".hermes/templates/task-contract.yaml.j2",
    ".hermes/templates/locks.yaml.j2",
    ".hermes/test-fixtures/stub-handoff-pass.yaml",
    ".hermes/test-fixtures/stub-handoff-fail-forbidden.yaml",
    ".hermes/test-fixtures/stub-handoff-fail-schema.yaml",
    ".hermes/test-fixtures/stub-handoff-fail-tests.yaml",
    ".hermes/plans/2026-05-22_000000-hybrid-agent-control-plane.md",
    "scripts/check_hybrid_control_plane.py",
    # Phase 1 artifacts
    ".hermes/templates/skill-draft-hybrid-agent-control-plane.md",
    "tests/skills/test_hybrid_agent_control_plane.py",
]

# Caveat phrases that must appear verbatim (or close enough) in the plan.
# These correspond to caveats C-1 through C-6.
REQUIRED_PLAN_PHRASES = [
    # C-1: no duplicate route-dev-task
    "route-dev-task",
    "must NOT create a second route-dev-task",
    # C-2: skill creation deferred; repo-local artifacts
    "repo-local",
    "deferred",
    # C-3: delegate_task does not directly spawn
    "delegate_task does not directly spawn",
    # C-4: CODEX.md TBD
    "CODEX.md",
    "PROVISIONAL",
    # C-5: cost accounting is estimated
    "estimated",
    "cost_usd_actual",
    # C-6: CODEOWNERS insufficient for local workflow; check script is primary
    "CODEOWNERS",
    "local check script",
]

# .gitignore: paths that MUST be present (runtime outputs)
GITIGNORE_MUST_INCLUDE = [
    ".hermes/runs/",
    ".worktrees/",
]
# .gitignore: pattern that must NOT be present (would ignore all .hermes/)
GITIGNORE_MUST_NOT_INCLUDE = [
    ".hermes/\n",   # bare .hermes/ on its own line
    "/.hermes/\n",
]
# Also check that .hermes/handoff/ or .hermes/handoffs/ is ignored
GITIGNORE_SHOULD_INCLUDE_ONE_OF = [
    ".hermes/handoff/",
    ".hermes/handoffs/",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
failures = []
warnings = []


def rel(path):
    return os.path.join(REPO_ROOT, path)


def fail(msg):
    failures.append(msg)
    print(f"  FAIL: {msg}")


def warn(msg):
    warnings.append(msg)
    print(f"  WARN: {msg}")


def ok(msg):
    print(f"  OK:   {msg}")


def load_yaml(path):
    """Load YAML file; return (data, error_string). data=None on error."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        # safe_load returns None for empty files; normalise to dict
        data: dict = raw if isinstance(raw, dict) else {}
        return data, None
    except yaml.YAMLError as e:
        return None, str(e)


# ---------------------------------------------------------------------------
# Check 1: Required files exist
# ---------------------------------------------------------------------------
print("\n=== 1. Required files ===")
for rel_path in REQUIRED_FILES:
    full = rel(rel_path)
    if os.path.isfile(full):
        ok(rel_path)
    else:
        fail(f"Missing required file: {rel_path}")


# ---------------------------------------------------------------------------
# Check 2: stub-handoff-pass — required fields + test_results.passed=true
# ---------------------------------------------------------------------------
print("\n=== 2. Fixture: stub-handoff-pass.yaml ===")
pass_path = rel(".hermes/test-fixtures/stub-handoff-pass.yaml")
if os.path.isfile(pass_path):
    data, err = load_yaml(pass_path)
    if err:
        fail(f"stub-handoff-pass.yaml YAML parse error: {err}")
    else:
        required_fields = ["task_id", "agent", "completed_at", "summary", "changed_files", "test_results"]
        for field in required_fields:
            if field not in data or data[field] is None:  # type: ignore[operator]
                fail(f"stub-handoff-pass.yaml missing required field: {field}")
            else:
                ok(f"field present: {field}")
        # test_results.passed must be true
        tr = data.get("test_results") or {}
        if tr.get("passed") is True:
            ok("test_results.passed = true")
        else:
            fail(f"stub-handoff-pass.yaml: test_results.passed should be true, got: {tr.get('passed')!r}")
else:
    fail("stub-handoff-pass.yaml not found (skipping content checks)")


# ---------------------------------------------------------------------------
# Check 3: stub-handoff-fail-schema — intentionally missing required fields
# ---------------------------------------------------------------------------
print("\n=== 3. Fixture: stub-handoff-fail-schema.yaml ===")
schema_fail_path = rel(".hermes/test-fixtures/stub-handoff-fail-schema.yaml")
if os.path.isfile(schema_fail_path):
    data, err = load_yaml(schema_fail_path)
    if err:
        fail(f"stub-handoff-fail-schema.yaml YAML parse error: {err}")
    else:
        # Must be missing at least one required field
        required_fields = ["task_id", "agent", "completed_at", "summary", "changed_files", "test_results"]
        missing = [f for f in required_fields if f not in data or data[f] is None]  # type: ignore[operator]
        if missing:
            ok(f"stub-handoff-fail-schema.yaml intentionally missing fields: {missing}")
        else:
            fail("stub-handoff-fail-schema.yaml has all required fields — fixture should be intentionally malformed")
        # Also check test_results.passed is missing or not set
        tr = data.get("test_results") or {}
        if "passed" not in tr:
            ok("test_results.passed intentionally absent (correct for schema-fail fixture)")
        else:
            warn("stub-handoff-fail-schema.yaml has test_results.passed set — "
                 "fixture should omit it to test schema failure")
else:
    fail("stub-handoff-fail-schema.yaml not found (skipping content checks)")


# ---------------------------------------------------------------------------
# Check 4: stub-handoff-fail-forbidden — changed_files includes a forbidden path
# ---------------------------------------------------------------------------
print("\n=== 4. Fixture: stub-handoff-fail-forbidden.yaml ===")
forbidden_path = rel(".hermes/test-fixtures/stub-handoff-fail-forbidden.yaml")
FORBIDDEN_PREFIXES = [
    "AGENTS.md",
    "CLAUDE.md",
    "CODEX.md",
    ".hermes/config/",
    ".hermes/schemas/",
    ".hermes/plans/",
    ".claude/",
    ".codex/",
]
if os.path.isfile(forbidden_path):
    data, err = load_yaml(forbidden_path)
    if err:
        fail(f"stub-handoff-fail-forbidden.yaml YAML parse error: {err}")
    else:
        changed = list(data.get("changed_files") or [])
        found_forbidden = [
            f for f in changed
            if any(f.startswith(p) or f == p.rstrip("/") for p in FORBIDDEN_PREFIXES)
        ]
        if found_forbidden:
            ok(f"stub-handoff-fail-forbidden.yaml contains forbidden path(s): {found_forbidden}")
        else:
            fail(
                "stub-handoff-fail-forbidden.yaml: changed_files must include at least one "
                f"forbidden prompt artifact path (one of: {FORBIDDEN_PREFIXES}). "
                f"Got: {changed}"
            )
else:
    fail("stub-handoff-fail-forbidden.yaml not found (skipping content checks)")


# ---------------------------------------------------------------------------
# Check 5: stub-handoff-fail-tests — test_results.passed=false
# ---------------------------------------------------------------------------
print("\n=== 5. Fixture: stub-handoff-fail-tests.yaml ===")
tests_fail_path = rel(".hermes/test-fixtures/stub-handoff-fail-tests.yaml")
if os.path.isfile(tests_fail_path):
    data, err = load_yaml(tests_fail_path)
    if err:
        fail(f"stub-handoff-fail-tests.yaml YAML parse error: {err}")
    else:
        # Schema fields should be present (it's a schema-valid but gate-failing handoff)
        required_fields = ["task_id", "agent", "completed_at", "summary", "changed_files", "test_results"]
        for field in required_fields:
            if field not in data or data[field] is None:  # type: ignore[operator]
                fail(f"stub-handoff-fail-tests.yaml missing field: {field} "
                     "(this fixture should be schema-valid but fail the tests gate)")
        tr = data.get("test_results") or {}
        if tr.get("passed") is False:
            ok("test_results.passed = false")
        else:
            fail(f"stub-handoff-fail-tests.yaml: test_results.passed should be false, got: {tr.get('passed')!r}")
else:
    fail("stub-handoff-fail-tests.yaml not found (skipping content checks)")


# ---------------------------------------------------------------------------
# Check 6: Plan contains required caveat phrases (C-1 through C-6)
# ---------------------------------------------------------------------------
print("\n=== 6. Plan caveat phrases ===")
plan_path = rel(".hermes/plans/2026-05-22_000000-hybrid-agent-control-plane.md")
if os.path.isfile(plan_path):
    with open(plan_path, "r", encoding="utf-8") as f:
        plan_text = f.read()
    for phrase in REQUIRED_PLAN_PHRASES:
        if phrase in plan_text:
            ok(f"Plan contains: {phrase!r}")
        else:
            fail(f"Plan MISSING required phrase: {phrase!r}")
else:
    fail("Plan file not found (skipping phrase checks)")


# ---------------------------------------------------------------------------
# Check 7: .gitignore correctness
# ---------------------------------------------------------------------------
print("\n=== 7. .gitignore ===")
gitignore_path = rel(".gitignore")
if os.path.isfile(gitignore_path):
    with open(gitignore_path, "r", encoding="utf-8") as f:
        gi_text = f.read()
    # Must include runtime output dirs
    for pattern in GITIGNORE_MUST_INCLUDE:
        # Check if the stripped pattern appears as a line
        if any(line.strip() == pattern.strip() for line in gi_text.splitlines()):
            ok(f".gitignore includes: {pattern!r}")
        else:
            fail(f".gitignore missing runtime output pattern: {pattern!r}")

    # Must NOT ignore all of .hermes/
    for bad_pattern in GITIGNORE_MUST_NOT_INCLUDE:
        stripped = bad_pattern.strip()
        if any(line.strip() == stripped for line in gi_text.splitlines()):
            fail(f".gitignore has bare .hermes/ ignore pattern {stripped!r} — "
                 "this would ignore all .hermes/ including committed config files. "
                 "Use specific subdirectory patterns instead.")
        else:
            ok(f".gitignore does NOT have broad ignore: {stripped!r}")

    # Should include at least one of handoff/handoffs
    found_handoff = any(
        any(line.strip() == p.strip() for line in gi_text.splitlines())
        for p in GITIGNORE_SHOULD_INCLUDE_ONE_OF
    )
    if found_handoff:
        ok(".gitignore includes handoff runtime dir")
    else:
        warn(f".gitignore should include one of {GITIGNORE_SHOULD_INCLUDE_ONE_OF} — "
             "add it to prevent handoff payloads being accidentally committed")
else:
    fail(".gitignore not found")


# ---------------------------------------------------------------------------
# Phase 1 Check 8: Plan has human_reviewed_at set and non-empty
# ---------------------------------------------------------------------------
print("\n=== 8. Plan: human_reviewed_at field ===")
plan_path8 = rel(".hermes/plans/2026-05-22_000000-hybrid-agent-control-plane.md")
if os.path.isfile(plan_path8):
    with open(plan_path8, "r", encoding="utf-8") as f:
        plan_text8 = f.read()
    import re as _re
    # Look for machine-checkable field: human_reviewed_at: <non-empty, non-~>
    # Matches the pattern in the MACHINE-CHECKABLE FIELDS comment block
    match = _re.search(r"^human_reviewed_at:\s*(\S+)", plan_text8, _re.MULTILINE)
    if match:
        val = match.group(1).strip()
        if val and val != "~" and val != "null":
            ok(f"human_reviewed_at = {val!r}")
        else:
            fail(
                f"human_reviewed_at is present but empty/null ({val!r}). "
                "Worker execution phases require a non-empty timestamp. "
                "Set it to the approval timestamp (e.g. 2026-05-22T23:27:28Z)."
            )
    else:
        fail(
            "Plan is missing 'human_reviewed_at: <timestamp>' field. "
            "This field is required before any Phase 2+ worker spawn. "
            "Add it in the MACHINE-CHECKABLE FIELDS block at the plan header."
        )
else:
    fail("Plan file not found (skipping human_reviewed_at check)")


# ---------------------------------------------------------------------------
# Phase 1 Check 9: Plan has locked decisions section (LD-1 through LD-6)
# ---------------------------------------------------------------------------
print("\n=== 9. Plan: locked decisions ===")
REQUIRED_LOCKED_DECISIONS = [
    "LD-1",
    "LD-2",
    "LD-3",
    "LD-4",
    "LD-5",
    "LD-6",
    "worktrees_are_sandbox: false",   # LD-1 canonical field
    "file-based handoff is canonical",  # LD-2
    "HANDOFF_PATH:",                  # LD-2 sentinel convention
    "human_reviewed_at",              # LD-3
    "serial gates",                   # LD-4
    "opportunistic",                  # LD-5 (Codex)
    "cost_estimated: true",           # LD-6
]
if os.path.isfile(plan_path8):
    for phrase in REQUIRED_LOCKED_DECISIONS:
        if phrase in plan_text8:
            ok(f"Plan contains locked decision phrase: {phrase!r}")
        else:
            fail(f"Plan missing locked decision phrase: {phrase!r}")
else:
    plan_text8 = ""
    fail("Plan file not found (skipping locked decisions check)")


# ---------------------------------------------------------------------------
# Phase 1 Check 10: Skill draft exists and has required sections
# ---------------------------------------------------------------------------
print("\n=== 10. Skill draft: hybrid-agent-control-plane ===")
skill_draft_path = rel(".hermes/templates/skill-draft-hybrid-agent-control-plane.md")
SKILL_DRAFT_REQUIRED_SECTIONS = [
    "human_reviewed_at",           # frontmatter field
    "No real spawns",              # MVP constraint
    "worktrees_are_sandbox",       # LD-1
    "HANDOFF_PATH:",               # LD-2 sentinel
    "file-based handoff",          # LD-2 (case-insensitive search done below)
    "serial",                      # LD-4 gate order
    "cost_estimated",              # LD-6
    "route-dev-task",              # integration with existing skill (C-1)
    "terminal()",                  # C-3: real spawns use terminal, not delegate_task
    "NOT delegate_task",           # C-3 explicit prohibition
]
SKILL_DRAFT_MUST_NOT_CONTAIN = [
    # MVP must not indicate real spawns are enabled
    "spawn_real_agent: true",
    "sandbox_verified: true",      # Codex not verified yet
]
if os.path.isfile(skill_draft_path):
    with open(skill_draft_path, "r", encoding="utf-8") as f:
        draft_text = f.read()
    for phrase in SKILL_DRAFT_REQUIRED_SECTIONS:
        if phrase.lower() in draft_text.lower():
            ok(f"Skill draft contains: {phrase!r}")
        else:
            fail(f"Skill draft missing required phrase: {phrase!r}")
    for phrase in SKILL_DRAFT_MUST_NOT_CONTAIN:
        if phrase in draft_text:
            fail(
                f"Skill draft contains forbidden phrase for MVP: {phrase!r}. "
                "This would indicate real spawns or unverified Codex are enabled."
            )
        else:
            ok(f"Skill draft correctly absent: {phrase!r}")
else:
    fail("Skill draft not found: .hermes/templates/skill-draft-hybrid-agent-control-plane.md")


# ---------------------------------------------------------------------------
# Phase 1 Check 11: Templates have cost_estimated and handoff_path fields
# ---------------------------------------------------------------------------
print("\n=== 11. Templates: cost_estimated and handoff path fields ===")
TEMPLATE_CHECKS = {
    ".hermes/templates/run-manifest.yaml.j2": [
        "cost_estimated",
        "total_cost_usd_cap",
        "total_cost_usd_actual",
        "worktrees_are_sandbox",
        "container_isolation",
    ],
    ".hermes/templates/task-contract.yaml.j2": [
        "cost_cap_usd",
        "cost_estimated",
        "handoff_schema_ref",
        "spawn_mechanism",
    ],
}
for tpl_path, required_fields in TEMPLATE_CHECKS.items():
    full_tpl = rel(tpl_path)
    if os.path.isfile(full_tpl):
        with open(full_tpl, "r", encoding="utf-8") as f:
            tpl_text = f.read()
        for field in required_fields:
            if field in tpl_text:
                ok(f"{tpl_path} contains field: {field!r}")
            else:
                fail(f"{tpl_path} missing required field: {field!r}")
    else:
        fail(f"Template not found: {tpl_path}")


# ---------------------------------------------------------------------------
# Phase 1 Check 12: Handoff schema has cost_estimated field
# ---------------------------------------------------------------------------
print("\n=== 12. Handoff schema: cost_estimated field ===")
schema_path = rel(".hermes/schemas/handoff-v1.yaml")
if os.path.isfile(schema_path):
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_text = f.read()
    if "cost_estimated" in schema_text:
        ok("handoff-v1.yaml contains cost_estimated field")
    else:
        fail("handoff-v1.yaml missing cost_estimated field (required by LD-6)")
    if "method:" in schema_text and "token_count_estimate" in schema_text:
        ok("handoff-v1.yaml has cost method enum including token_count_estimate")
    else:
        warn("handoff-v1.yaml may be missing cost method enum — check cost_estimated.method field")
else:
    fail("handoff-v1.yaml not found (skipping schema field checks)")


# ---------------------------------------------------------------------------
# Phase 1 Check 13: No real-spawn indicators enabled for MVP
# ---------------------------------------------------------------------------
print("\n=== 13. MVP: no real spawn indicators ===")
# Check capability matrix — Codex sandbox_verified must be false
cap_matrix_path = rel(".hermes/config/capability-matrix.yaml")
if os.path.isfile(cap_matrix_path):
    cap_data, cap_err = load_yaml(cap_matrix_path)
    if cap_err:
        fail(f"capability-matrix.yaml YAML parse error: {cap_err}")
    else:
        codex = (cap_data.get("agents") or {}).get("codex") or {}
        sandbox_verified = codex.get("sandbox_verified", False)
        if sandbox_verified is not False:
            fail(
                "capability-matrix.yaml: codex.sandbox_verified is not false — "
                "Codex canary test (plan task 2.1) must pass before enabling. "
                f"Current value: {sandbox_verified!r}. Set to false until Phase 2 canary confirms."
            )
        else:
            ok(f"codex.sandbox_verified = {sandbox_verified!r} (correctly false for MVP)")

        cc = (cap_data.get("agents") or {}).get("claude_code") or {}
        dsp = cc.get("dangerously_skip_permissions", False)
        if dsp is not False:
            fail(
                "capability-matrix.yaml: claude_code.dangerously_skip_permissions is not false — "
                f"this must never be set on real host filesystems. Current value: {dsp!r}."
            )
        else:
            ok(f"claude_code.dangerously_skip_permissions = {dsp!r} (correctly false)")
else:
    fail("capability-matrix.yaml not found (skipping real-spawn checks)")


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
if failures:
    print(f"RESULT: {len(failures)} failure(s), {len(warnings)} warning(s)")
    for i, f in enumerate(failures, 1):
        print(f"  [{i}] {f}")
    if warnings:
        for w in warnings:
            print(f"  WARN: {w}")
    sys.exit(1)
else:
    if warnings:
        print(f"RESULT: PASS (0 failures, {len(warnings)} warning(s))")
        for w in warnings:
            print(f"  WARN: {w}")
    else:
        print("RESULT: PASS — all checks passed.")
    sys.exit(0)
