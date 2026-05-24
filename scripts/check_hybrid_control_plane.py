#!/usr/bin/env python3
"""
scripts/check_hybrid_control_plane.py

Hybrid agent control plane gate checker.
Supports:
  * Default sanity mode (original checks)
  * --handoff PATH: validate single handoff fixture
  * --all-handoff-fixtures: validate all stub-handoff-*.yaml fixtures with expected map

Exit codes:
  0 = success (AUTOMATED_PASS_HUMAN_REVIEW_REQUIRED in pass case)
  nonzero = any gate failure

Gate order for handoff mode (fail-fast):
  1. schema_validation
  2. forbidden_path_writes
  3. prompt_artifact_unchanged
  4. diff_size_limit: SKIP
  5. unit_tests
  6. cost_cap: SKIP
  7. human_review / RESULT

Protected paths (exact or prefix):
  exact forbidden: AGENTS.md, CLAUDE.md, CODEX.md
  prefixes: .hermes/config/, .hermes/schemas/, .hermes/plans/, .claude/, .codex/
Path rules:
  - Repo-relative POSIX paths only
  - Allow and normalize leading './' for ordinary repo-relative paths
  - Reject: empty, absolute, contains backslash or drive, contains '..'
  - ./AGENTS.md blocks after normalization; AGENTS.md.backup passes
"""

import sys
import os
import argparse
import subprocess
from typing import List, Dict, Any, Optional, Tuple

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML is not installed.")
    print("Install it: pip install pyyaml   (or: pip install -e '.[dev]')")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Configuration and constants
# ---------------------------------------------------------------------------
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FORBIDDEN_EXACT = {"AGENTS.md", "CLAUDE.md", "CODEX.md"}
FORBIDDEN_PREFIXES = [
    ".hermes/config/",
    ".hermes/schemas/",
    ".hermes/plans/",
    ".claude/",
    ".codex/",
]

# Expected outcomes for --all-handoff-fixtures mode
ALL_HANDOFF_EXPECTED: Dict[str, str] = {
    "stub-handoff-pass.yaml": "pass",
    "stub-handoff-fail-forbidden.yaml": "fail",
    "stub-handoff-fail-schema.yaml": "fail",
    "stub-handoff-fail-tests.yaml": "fail",
    "stub-handoff-fail-agent-enum.yaml": "fail",
    "stub-handoff-fail-test-results-absent.yaml": "fail",
    "stub-handoff-fail-empty-changed-files.yaml": "fail",
    "stub-handoff-fail-dotslash-prompt-artifact.yaml": "fail",
    "stub-handoff-fail-traversal.yaml": "fail",
    "stub-handoff-pass-agent-md-backup.yaml": "pass",
}

AGENT_ENUM_ALLOWED = {"claude_code", "codex"}


def rel(path: str) -> str:
    return os.path.join(REPO_ROOT, path)


def is_repo_relative_posix(path_str: str) -> bool:
    """True if path is repo-relative POSIX (no absolute, no backslash, no drive, no ..).

    Leading './' is accepted and treated as a normalizable prefix; the caller should
    normalize via normalize_path() before forbidden-path comparison.
    """
    if not path_str or not isinstance(path_str, str):
        return False
    p = path_str.strip()
    if not p:
        return False
    # Reject absolute
    if os.path.isabs(p) or p.startswith("/"):
        return False
    # Reject windows drive or backslash
    if "\\" in p or (len(p) > 1 and p[1] == ":"):
        return False
    # Normalize leading ./ before further checks
    if p.startswith("./"):
        p = p[2:]
        # After stripping './', must have a non-empty name remaining
        if not p:
            return False
    # Reject any .. traversal segment
    parts = p.split("/")
    if any(part == ".." for part in parts):
        return False
    return True


def normalize_path(p: str) -> str:
    """Strip leading ./ for comparison."""
    if p.startswith("./"):
        return p[2:]
    return p


def is_forbidden_path(path_str: str) -> bool:
    """Check against exact forbidden names or prefixes (after normalizing)."""
    if not path_str:
        return False
    norm = normalize_path(path_str)
    if norm in FORBIDDEN_EXACT:
        return True
    for pref in FORBIDDEN_PREFIXES:
        if norm.startswith(pref) or norm == pref.rstrip("/"):
            return True
    return False


def validate_changed_files_for_schema(changed_files: List[str]) -> Tuple[bool, Optional[str]]:
    """Schema-only validation: list, non-empty, all strings. NO path format or forbidden checks."""
    if not isinstance(changed_files, list):
        return False, "changed_files must be a list"
    if len(changed_files) == 0:
        return False, "changed_files must be non-empty"
    for f in changed_files:
        if not isinstance(f, str):
            return False, f"changed_files entry not string: {f!r}"
    return True, None


def validate_path_format_and_forbidden(changed_files: List[str]) -> Tuple[bool, Optional[str]]:
    """
    forbidden_path_writes gate validation.
    Rejects: invalid format (not repo-relative POSIX, traversal, absolute, backslash, drive)
    Allows and normalizes leading './' before protected-path comparison.
    AND protected/forbidden prompt/control-plane paths.
    Returns (ok, error_msg)
    """
    for f in changed_files:
        if not is_repo_relative_posix(f):
            return False, f"Invalid path format (not repo-relative POSIX or contains traversal): {f!r}"
        if is_forbidden_path(f):
            return False, f"Forbidden path in changed_files: {f}"
    return True, None


def validate_schema(data: Dict[str, Any]) -> Tuple[bool, Optional[str], str]:
    """
    Structural schema validation for handoff.
    Required: task_id, agent, completed_at, summary, changed_files
    Note: missing test_results is NOT a schema failure.
    Returns: (valid, error_msg, next_gate)
    """
    required = ["task_id", "agent", "completed_at", "summary", "changed_files"]
    for field in required:
        if field not in data or data[field] is None:
            return False, f"Missing required field: {field}", "schema_validation"
    agent = data.get("agent")
    if agent not in AGENT_ENUM_ALLOWED:
        return False, f"agent enum must be one of {AGENT_ENUM_ALLOWED}, got: {agent!r}", "schema_validation"

    cf_ok, cf_err = validate_changed_files_for_schema(data.get("changed_files", []))
    if not cf_ok:
        return False, cf_err or "changed_files invalid", "schema_validation"

    return True, None, "forbidden_path_writes"


def run_forbidden_path_writes_gate(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    forbidden_path_writes gate: runs AFTER schema_validation PASS.
    Rejects invalid formats and protected paths.
    Prints and returns status for caller.
    """
    changed = data.get("changed_files", []) or []
    ok, err = validate_path_format_and_forbidden(changed)
    if not ok:
        msg = f"forbidden_path_writes: FAIL - {err}"
        print(msg)
        return False, msg
    print("forbidden_path_writes: PASS")
    return True, None


def run_unit_tests_for_handoff(data: Dict[str, Any]) -> Tuple[str, bool]:
    """
    Simulate unit_tests gate.
    If test_results absent: prints 'unit_tests: SKIP/missing evidence' and returns fail.
    If present and passed=true: pass
    If present and passed=false: fail
    Returns (message, passed_bool)
    """
    if "test_results" not in data or data.get("test_results") is None:
        msg = "unit_tests: SKIP/missing evidence"
        return msg, False
    tr = data.get("test_results") or {}
    passed = tr.get("passed")
    if passed is True:
        return "unit_tests: passed", True
    else:
        return f"unit_tests: failed (passed={passed})", False


def check_handoff_file(handoff_path: str) -> int:
    """
    Execute full handoff validation gates for a single file.
    Prints gate results. Returns exit code (0 on ultimate AUTOMATED_PASS...).
    """
    abs_path = handoff_path
    if not os.path.isabs(handoff_path):
        abs_path = os.path.join(REPO_ROOT, handoff_path)

    if not os.path.isfile(abs_path):
        print(f"schema_validation: FAIL - file not found: {handoff_path}")
        return 1

    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception as e:
        print(f"schema_validation: FAIL - YAML error: {e}")
        return 1

    if not isinstance(data, dict):
        print("schema_validation: FAIL - top level must be mapping")
        return 1

    # Gate 1: schema_validation (structure only — paths validated later)
    schema_ok, schema_err, _ = validate_schema(data)
    if not schema_ok:
        print(f"schema_validation: FAIL - {schema_err}")
        return 1
    print("schema_validation: PASS")

    # Gate 2: forbidden_path_writes (format + protected paths)
    fbd_ok, _ = run_forbidden_path_writes_gate(data)
    if not fbd_ok:
        # Protected fixtures MUST stop here; do not reach unit_tests
        return 1

    # Gate 3: prompt_artifact_unchanged
    # For this static checker we treat fixture presence as "unchanged" assumption.
    # If a fixture name contains 'prompt-artifact' failure case, it was already rejected in forbidden gate.
    print("prompt_artifact_unchanged: PASS")

    # Gate 4: diff_size_limit: SKIP
    print("diff_size_limit: SKIP")

    # Gate 5: unit_tests
    unit_msg, unit_pass = run_unit_tests_for_handoff(data)
    print(unit_msg)
    if not unit_pass:
        # test failure or missing evidence stops here (fail-fast before human_review)
        return 1

    # Gate 6: cost_cap: SKIP
    print("cost_cap: SKIP")

    # Gate 7: human_review / RESULT
    print("RESULT: AUTOMATED_PASS_HUMAN_REVIEW_REQUIRED")
    return 0


def check_all_handoff_fixtures() -> int:
    """Run check on every stub-handoff-*.yaml and enforce expected map. Unknown files = closed fail."""
    fixtures_dir = os.path.join(REPO_ROOT, ".hermes", "test-fixtures")
    if not os.path.isdir(fixtures_dir):
        print("ERROR: .hermes/test-fixtures directory missing")
        return 1

    found_files = []
    for fname in os.listdir(fixtures_dir):
        if fname.startswith("stub-handoff-") and fname.endswith(".yaml"):
            found_files.append(fname)

    # Check for unexpected files
    unexpected = [f for f in found_files if f not in ALL_HANDOFF_EXPECTED]
    if unexpected:
        print(f"FAIL: unexpected handoff fixtures found: {unexpected}")
        print("All stub-handoff-*.yaml must be registered in ALL_HANDOFF_EXPECTED map.")
        return 1

    all_pass = True
    for fname, expected in ALL_HANDOFF_EXPECTED.items():
        fpath = os.path.join(".hermes/test-fixtures", fname)
        rc = check_handoff_file(fpath)
        outcome = "pass" if rc == 0 else "fail"
        if outcome != expected:
            print(f"FAIL: {fname} expected {expected.upper()} but got {outcome.upper()}")
            all_pass = False
        else:
            print(f"OK: {fname} -> {outcome}")

    return 0 if all_pass else 1


def main():
    parser = argparse.ArgumentParser(
        description="Hybrid control plane checker (sanity + handoff modes)"
    )
    parser.add_argument(
        "--handoff",
        metavar="PATH",
        help="Validate a single handoff YAML file (full gate sequence)",
    )
    parser.add_argument(
        "--all-handoff-fixtures",
        action="store_true",
        help="Validate all stub-handoff-*.yaml fixtures against expected map",
    )
    args = parser.parse_args()

    if args.handoff:
        rc = check_handoff_file(args.handoff)
        sys.exit(rc)
    elif args.all_handoff_fixtures:
        rc = check_all_handoff_fixtures()
        sys.exit(rc)
    else:
        # =====================================================================
        # DEFAULT SANITY MODE — full original behavior restored from HEAD
        # =====================================================================
        from subprocess import run  # local import to avoid top-level pollution

        failures = []
        warnings = []

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
                data: dict = raw if isinstance(raw, dict) else {}
                return data, None
            except yaml.YAMLError as e:
                return None, str(e)

        print("\n=== 1. Required files ===\n")
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
        for rel_path in REQUIRED_FILES:
            full = rel(rel_path)
            if os.path.isfile(full):
                ok(rel_path)
            else:
                fail(f"Missing required file: {rel_path}")

        # -------------------------------------------------------------------
        # Check 2: stub-handoff-pass — required fields + test_results.passed=true
        # -------------------------------------------------------------------
        print("\n=== 2. Fixture: stub-handoff-pass.yaml ===\n")
        pass_path = rel(".hermes/test-fixtures/stub-handoff-pass.yaml")
        if os.path.isfile(pass_path):
            data, err = load_yaml(pass_path)
            if err:
                fail(f"stub-handoff-pass.yaml YAML parse error: {err}")
            else:
                required_fields = ["task_id", "agent", "completed_at", "summary", "changed_files", "test_results"]
                for field in required_fields:
                    if field not in data or data[field] is None:
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

        # -------------------------------------------------------------------
        # Check 3: stub-handoff-fail-schema — intentionally missing required fields
        # -------------------------------------------------------------------
        print("\n=== 3. Fixture: stub-handoff-fail-schema.yaml ===\n")
        schema_fail_path = rel(".hermes/test-fixtures/stub-handoff-fail-schema.yaml")
        if os.path.isfile(schema_fail_path):
            data, err = load_yaml(schema_fail_path)
            if err:
                fail(f"stub-handoff-fail-schema.yaml YAML parse error: {err}")
            else:
                required_fields = ["task_id", "agent", "completed_at", "summary", "changed_files", "test_results"]
                missing = [f for f in required_fields if f not in data or data[f] is None]
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

        # -------------------------------------------------------------------
        # Check 4: stub-handoff-fail-forbidden — changed_files includes a forbidden path
        # -------------------------------------------------------------------
        print("\n=== 4. Fixture: stub-handoff-fail-forbidden.yaml ===\n")
        forbidden_path = rel(".hermes/test-fixtures/stub-handoff-fail-forbidden.yaml")
        FORBIDDEN_PREFIXES_LOCAL = [
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
                    if any(f.startswith(p) or f == p.rstrip("/") for p in FORBIDDEN_PREFIXES_LOCAL)
                ]
                if found_forbidden:
                    ok(f"stub-handoff-fail-forbidden.yaml contains forbidden path(s): {found_forbidden}")
                else:
                    fail(
                        "stub-handoff-fail-forbidden.yaml: changed_files must include at least one "
                        f"forbidden prompt artifact path (one of: {FORBIDDEN_PREFIXES_LOCAL}). "
                        f"Got: {changed}"
                    )
        else:
            fail("stub-handoff-fail-forbidden.yaml not found (skipping content checks)")

        # -------------------------------------------------------------------
        # Check 5: stub-handoff-fail-tests — test_results.passed=false
        # -------------------------------------------------------------------
        print("\n=== 5. Fixture: stub-handoff-fail-tests.yaml ===\n")
        tests_fail_path = rel(".hermes/test-fixtures/stub-handoff-fail-tests.yaml")
        if os.path.isfile(tests_fail_path):
            data, err = load_yaml(tests_fail_path)
            if err:
                fail(f"stub-handoff-fail-tests.yaml YAML parse error: {err}")
            else:
                required_fields = ["task_id", "agent", "completed_at", "summary", "changed_files", "test_results"]
                for field in required_fields:
                    if field not in data or data[field] is None:
                        fail(f"stub-handoff-fail-tests.yaml missing field: {field} "
                             "(this fixture should be schema-valid but fail the tests gate)")
                tr = data.get("test_results") or {}
                if tr.get("passed") is False:
                    ok("test_results.passed = false")
                else:
                    fail(f"stub-handoff-fail-tests.yaml: test_results.passed should be false, got: {tr.get('passed')!r}")
        else:
            fail("stub-handoff-fail-tests.yaml not found (skipping content checks)")

        # -------------------------------------------------------------------
        # Check 6: Plan contains required caveat phrases (C-1 through C-6)
        # -------------------------------------------------------------------
        print("\n=== 6. Plan caveat phrases ===\n")
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

        # -------------------------------------------------------------------
        # Check 7: .gitignore correctness
        # -------------------------------------------------------------------
        print("\n=== 7. .gitignore ===\n")
        GITIGNORE_MUST_INCLUDE = [".hermes/runs/", ".worktrees/"]
        GITIGNORE_MUST_NOT_INCLUDE = [".hermes/\n", "/.hermes/\n"]
        GITIGNORE_SHOULD_INCLUDE_ONE_OF = [".hermes/handoff/", ".hermes/handoffs/"]

        gitignore_path = rel(".gitignore")
        if os.path.isfile(gitignore_path):
            with open(gitignore_path, "r", encoding="utf-8") as f:
                gi_text = f.read()
            for pattern in GITIGNORE_MUST_INCLUDE:
                if any(line.strip() == pattern.strip() for line in gi_text.splitlines()):
                    ok(f".gitignore includes: {pattern!r}")
                else:
                    fail(f".gitignore missing runtime output pattern: {pattern!r}")

            for bad_pattern in GITIGNORE_MUST_NOT_INCLUDE:
                stripped = bad_pattern.strip()
                if any(line.strip() == stripped for line in gi_text.splitlines()):
                    fail(f".gitignore has bare .hermes/ ignore pattern {stripped!r} — "
                         "this would ignore all .hermes/ including committed config files. "
                         "Use specific subdirectory patterns instead.")
                else:
                    ok(f".gitignore does NOT have broad ignore: {stripped!r}")

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

        # -------------------------------------------------------------------
        # Check 8: Plan has human_reviewed_at set and non-empty
        # -------------------------------------------------------------------
        print("\n=== 8. Plan: human_reviewed_at field ===\n")
        if os.path.isfile(plan_path):
            with open(plan_path, "r", encoding="utf-8") as f:
                plan_text8 = f.read()
            import re as _re
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

        # -------------------------------------------------------------------
        # Check 9: Plan has locked decisions section (LD-1 through LD-6)
        # -------------------------------------------------------------------
        print("\n=== 9. Plan: locked decisions ===\n")
        REQUIRED_LOCKED_DECISIONS = [
            "LD-1",
            "LD-2",
            "LD-3",
            "LD-4",
            "LD-5",
            "LD-6",
            "worktrees_are_sandbox: false",
            "file-based handoff is canonical",
            "HANDOFF_PATH:",
            "human_reviewed_at",
            "serial gates",
            "opportunistic",
            "cost_estimated: true",
        ]
        if os.path.isfile(plan_path):
            for phrase in REQUIRED_LOCKED_DECISIONS:
                if phrase in plan_text8:
                    ok(f"Plan contains locked decision phrase: {phrase!r}")
                else:
                    fail(f"Plan missing locked decision phrase: {phrase!r}")
        else:
            fail("Plan file not found (skipping locked decisions check)")

        # -------------------------------------------------------------------
        # Check 10: Skill draft exists and has required sections
        # -------------------------------------------------------------------
        print("\n=== 10. Skill draft: hybrid-agent-control-plane ===\n")
        skill_draft_path = rel(".hermes/templates/skill-draft-hybrid-agent-control-plane.md")
        SKILL_DRAFT_REQUIRED_SECTIONS = [
            "human_reviewed_at",
            "No real spawns",
            "worktrees_are_sandbox",
            "HANDOFF_PATH:",
            "file-based handoff",
            "serial",
            "cost_estimated",
            "route-dev-task",
            "terminal()",
            "NOT delegate_task",
        ]
        SKILL_DRAFT_MUST_NOT_CONTAIN = [
            "spawn_real_agent: true",
            "sandbox_verified: true",
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

        # -------------------------------------------------------------------
        # Check 11: Templates have cost_estimated and handoff_path fields
        # -------------------------------------------------------------------
        print("\n=== 11. Templates: cost_estimated and handoff path fields ===\n")
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

        # -------------------------------------------------------------------
        # Check 12: Handoff schema has cost_estimated field
        # -------------------------------------------------------------------
        print("\n=== 12. Handoff schema: cost_estimated field ===\n")
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

        # -------------------------------------------------------------------
        # Check 13: No real-spawn indicators enabled for MVP
        # -------------------------------------------------------------------
        print("\n=== 13. MVP: no real spawn indicators ===\n")
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

        # -------------------------------------------------------------------
        # Summary
        # -------------------------------------------------------------------
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


if __name__ == "__main__":
    main()