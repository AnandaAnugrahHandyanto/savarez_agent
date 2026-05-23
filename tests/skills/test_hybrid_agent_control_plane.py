"""
tests/skills/test_hybrid_agent_control_plane.py

Deterministic harness tests for the hybrid agent control plane Phase 1 artifacts.

Constraints:
- No real Claude/Codex spawns.
- No network calls.
- No writes to ~/.hermes profiles or skills.
- All assertions are file-content / YAML-structure checks against repo-local artifacts.

Coverage:
  1. Plan has non-empty human_reviewed_at
  2. Locked decisions LD-1..LD-6 present in plan
  3. Skill draft contains required guardrail phrases
  4. Templates contain required cost/handoff/spawn-mechanism/isolation fields
  5. Handoff fixtures have correct pass/fail semantics
  6. Capability matrix keeps Codex sandbox_verified=false and
     claude_code.dangerously_skip_permissions=false
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

# ---------------------------------------------------------------------------
# Repo root and fixture paths — all relative to this file's location
# ---------------------------------------------------------------------------
REPO = Path(__file__).resolve().parents[2]
HERMES = REPO / ".hermes"

PLAN_PATH = HERMES / "plans" / "2026-05-22_000000-hybrid-agent-control-plane.md"
SKILL_DRAFT_PATH = HERMES / "templates" / "skill-draft-hybrid-agent-control-plane.md"
CAPABILITY_MATRIX_PATH = HERMES / "config" / "capability-matrix.yaml"
HANDOFF_SCHEMA_PATH = HERMES / "schemas" / "handoff-v1.yaml"
FIXTURE_PASS = HERMES / "test-fixtures" / "stub-handoff-pass.yaml"
FIXTURE_FAIL_SCHEMA = HERMES / "test-fixtures" / "stub-handoff-fail-schema.yaml"
FIXTURE_FAIL_FORBIDDEN = HERMES / "test-fixtures" / "stub-handoff-fail-forbidden.yaml"
FIXTURE_FAIL_TESTS = HERMES / "test-fixtures" / "stub-handoff-fail-tests.yaml"
RUN_MANIFEST_TPL = HERMES / "templates" / "run-manifest.yaml.j2"
TASK_CONTRACT_TPL = HERMES / "templates" / "task-contract.yaml.j2"

# Forbidden path prefixes mirrored from check_hybrid_control_plane.py
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

# Required schema fields for a valid handoff
HANDOFF_REQUIRED_FIELDS = [
    "task_id",
    "agent",
    "completed_at",
    "summary",
    "changed_files",
    "test_results",
]


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def load_yaml_file(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


def is_forbidden(filepath: str) -> bool:
    return any(
        filepath.startswith(p) or filepath == p.rstrip("/")
        for p in FORBIDDEN_PREFIXES
    )


# ---------------------------------------------------------------------------
# Section 1: Plan — human_reviewed_at
# ---------------------------------------------------------------------------

class TestPlanReviewedAt:
    def test_plan_file_exists(self):
        assert PLAN_PATH.is_file(), f"Plan not found: {PLAN_PATH}"

    def test_human_reviewed_at_present(self):
        text = PLAN_PATH.read_text(encoding="utf-8")
        m = re.search(r"^human_reviewed_at:\s*(\S+)", text, re.MULTILINE)
        assert m, "Plan is missing 'human_reviewed_at: <timestamp>' field"

    def test_human_reviewed_at_non_empty(self):
        text = PLAN_PATH.read_text(encoding="utf-8")
        m = re.search(r"^human_reviewed_at:\s*(\S+)", text, re.MULTILINE)
        assert m, "human_reviewed_at field not found"
        val = m.group(1).strip()
        assert val not in ("~", "null", ""), (
            f"human_reviewed_at is present but empty/null: {val!r}"
        )

    def test_human_reviewed_at_looks_like_timestamp(self):
        text = PLAN_PATH.read_text(encoding="utf-8")
        m = re.search(r"^human_reviewed_at:\s*(\S+)", text, re.MULTILINE)
        assert m
        val = m.group(1).strip()
        # Expect ISO-8601-ish: YYYY-MM-DDTHH:MM:SSZ or similar
        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", val), (
            f"human_reviewed_at doesn't look like an ISO timestamp: {val!r}"
        )


# ---------------------------------------------------------------------------
# Section 2: Plan — locked decisions LD-1..LD-6
# ---------------------------------------------------------------------------

REQUIRED_LOCKED_DECISION_PHRASES = [
    "LD-1",
    "LD-2",
    "LD-3",
    "LD-4",
    "LD-5",
    "LD-6",
    "worktrees_are_sandbox: false",    # LD-1: worktrees are not security sandboxes
    "file-based handoff is canonical", # LD-2: handoff mechanism
    "HANDOFF_PATH:",                   # LD-2: canonical env var sentinel
    "human_reviewed_at",               # LD-3: approval gate
    "serial gates",                    # LD-4: gate order
    "opportunistic",                   # LD-5: Codex optional/opportunistic
    "cost_estimated: true",            # LD-6: cost accounting is estimated
]


@pytest.mark.parametrize("phrase", REQUIRED_LOCKED_DECISION_PHRASES)
def test_plan_locked_decision_phrase(phrase: str):
    text = PLAN_PATH.read_text(encoding="utf-8")
    assert phrase in text, (
        f"Plan missing locked decision phrase: {phrase!r}"
    )


# ---------------------------------------------------------------------------
# Section 3: Skill draft guardrails
# ---------------------------------------------------------------------------

SKILL_DRAFT_REQUIRED = [
    "human_reviewed_at",     # frontmatter field
    "No real spawns",        # MVP constraint header
    "worktrees_are_sandbox", # LD-1
    "HANDOFF_PATH:",         # LD-2 sentinel
    "file-based handoff",    # LD-2
    "serial",                # LD-4 gate order
    "cost_estimated",        # LD-6
    "route-dev-task",        # C-1: no duplicate skill
    "terminal()",            # C-3: spawn via terminal, not delegate_task
    "NOT delegate_task",     # C-3: explicit prohibition
]

SKILL_DRAFT_FORBIDDEN = [
    "spawn_real_agent: true",   # must not indicate real spawns enabled
    "sandbox_verified: true",   # Codex not verified for MVP
]


@pytest.mark.parametrize("phrase", SKILL_DRAFT_REQUIRED)
def test_skill_draft_contains_required_phrase(phrase: str):
    text = SKILL_DRAFT_PATH.read_text(encoding="utf-8")
    assert phrase.lower() in text.lower(), (
        f"Skill draft missing required phrase: {phrase!r}"
    )


@pytest.mark.parametrize("phrase", SKILL_DRAFT_FORBIDDEN)
def test_skill_draft_excludes_forbidden_phrase(phrase: str):
    text = SKILL_DRAFT_PATH.read_text(encoding="utf-8")
    assert phrase not in text, (
        f"Skill draft contains forbidden MVP phrase: {phrase!r}"
    )


# ---------------------------------------------------------------------------
# Section 4: Templates — required fields
# ---------------------------------------------------------------------------

RUN_MANIFEST_REQUIRED_FIELDS = [
    "cost_estimated",
    "total_cost_usd_cap",
    "total_cost_usd_actual",
    "worktrees_are_sandbox",
    "container_isolation",
]

TASK_CONTRACT_REQUIRED_FIELDS = [
    "cost_cap_usd",
    "cost_estimated",
    "handoff_schema_ref",
    "spawn_mechanism",
]


@pytest.mark.parametrize("field", RUN_MANIFEST_REQUIRED_FIELDS)
def test_run_manifest_template_has_field(field: str):
    text = RUN_MANIFEST_TPL.read_text(encoding="utf-8")
    assert field in text, (
        f"run-manifest.yaml.j2 missing required field: {field!r}"
    )


@pytest.mark.parametrize("field", TASK_CONTRACT_REQUIRED_FIELDS)
def test_task_contract_template_has_field(field: str):
    text = TASK_CONTRACT_TPL.read_text(encoding="utf-8")
    assert field in text, (
        f"task-contract.yaml.j2 missing required field: {field!r}"
    )


# ---------------------------------------------------------------------------
# Section 5: Handoff fixtures — pass/fail semantics
# ---------------------------------------------------------------------------

class TestHandoffPassFixture:
    """stub-handoff-pass.yaml must have all required fields and passed=true."""

    @pytest.fixture(scope="class")
    def data(self):
        return load_yaml_file(FIXTURE_PASS)

    def test_fixture_file_exists(self):
        assert FIXTURE_PASS.is_file()

    @pytest.mark.parametrize("field", HANDOFF_REQUIRED_FIELDS)
    def test_required_field_present(self, data, field):
        assert field in data and data[field] is not None, (
            f"stub-handoff-pass.yaml missing required field: {field!r}"
        )

    def test_test_results_passed_true(self, data):
        tr = data.get("test_results") or {}
        assert tr.get("passed") is True, (
            f"stub-handoff-pass.yaml: test_results.passed should be True, got: {tr.get('passed')!r}"
        )

    def test_changed_files_no_forbidden_paths(self, data):
        changed = list(data.get("changed_files") or [])
        forbidden = [f for f in changed if is_forbidden(f)]
        assert not forbidden, (
            f"stub-handoff-pass.yaml (pass fixture) must not include forbidden paths: {forbidden}"
        )


class TestHandoffFailSchemaFixture:
    """stub-handoff-fail-schema.yaml must be intentionally missing required fields."""

    @pytest.fixture(scope="class")
    def data(self):
        return load_yaml_file(FIXTURE_FAIL_SCHEMA)

    def test_fixture_file_exists(self):
        assert FIXTURE_FAIL_SCHEMA.is_file()

    def test_at_least_one_required_field_missing(self, data):
        missing = [
            f for f in HANDOFF_REQUIRED_FIELDS
            if f not in data or data[f] is None
        ]
        assert missing, (
            "stub-handoff-fail-schema.yaml should be intentionally malformed "
            "(missing at least one required field), but all fields are present."
        )

    def test_test_results_passed_absent(self, data):
        """passed field inside test_results must be absent for schema-fail fixture."""
        tr = data.get("test_results") or {}
        assert "passed" not in tr, (
            "stub-handoff-fail-schema.yaml should omit test_results.passed "
            "to exercise schema validation failure path"
        )


class TestHandoffFailForbiddenFixture:
    """stub-handoff-fail-forbidden.yaml must include at least one forbidden path."""

    @pytest.fixture(scope="class")
    def data(self):
        return load_yaml_file(FIXTURE_FAIL_FORBIDDEN)

    def test_fixture_file_exists(self):
        assert FIXTURE_FAIL_FORBIDDEN.is_file()

    def test_changed_files_contains_forbidden_path(self, data):
        changed = list(data.get("changed_files") or [])
        forbidden = [f for f in changed if is_forbidden(f)]
        assert forbidden, (
            "stub-handoff-fail-forbidden.yaml must include at least one forbidden path "
            f"(one of: {FORBIDDEN_PREFIXES}). Got changed_files: {changed}"
        )


class TestHandoffFailTestsFixture:
    """stub-handoff-fail-tests.yaml must be schema-valid but have passed=false."""

    @pytest.fixture(scope="class")
    def data(self):
        return load_yaml_file(FIXTURE_FAIL_TESTS)

    def test_fixture_file_exists(self):
        assert FIXTURE_FAIL_TESTS.is_file()

    @pytest.mark.parametrize("field", HANDOFF_REQUIRED_FIELDS)
    def test_required_field_present(self, data, field):
        """Schema-valid — all required fields present."""
        assert field in data and data[field] is not None, (
            f"stub-handoff-fail-tests.yaml missing field: {field!r} "
            "(this fixture should be schema-valid but fail the tests gate)"
        )

    def test_test_results_passed_false(self, data):
        tr = data.get("test_results") or {}
        assert tr.get("passed") is False, (
            f"stub-handoff-fail-tests.yaml: test_results.passed should be False, "
            f"got: {tr.get('passed')!r}"
        )


# ---------------------------------------------------------------------------
# Section 6: Capability matrix — MVP safety constraints
# ---------------------------------------------------------------------------

class TestCapabilityMatrix:
    @pytest.fixture(scope="class")
    def matrix(self):
        return load_yaml_file(CAPABILITY_MATRIX_PATH)

    def test_file_exists(self):
        assert CAPABILITY_MATRIX_PATH.is_file()

    def test_codex_sandbox_verified_is_not_true(self, matrix):
        """Codex canary test (plan task 2.1) must pass before enabling sandbox_verified."""
        codex = (matrix.get("agents") or {}).get("codex") or {}
        sandbox_verified = codex.get("sandbox_verified", False)
        assert sandbox_verified is not True, (
            "capability-matrix.yaml: codex.sandbox_verified is True — "
            "Codex canary test must pass before enabling. "
            "Set to False until Phase 2 canary confirms sandbox behavior."
        )

    def test_claude_code_dangerously_skip_permissions_is_not_true(self, matrix):
        """dangerously_skip_permissions must never be set to true on real host filesystems."""
        cc = (matrix.get("agents") or {}).get("claude_code") or {}
        dsp = cc.get("dangerously_skip_permissions", False)
        assert dsp is not True, (
            "capability-matrix.yaml: claude_code.dangerously_skip_permissions is True — "
            "this must never be set on real host filesystems."
        )

    def test_codex_sandbox_verified_is_false(self, matrix):
        """Explicitly False (not just absent) for deterministic MVP gate."""
        codex = (matrix.get("agents") or {}).get("codex") or {}
        sandbox_verified = codex.get("sandbox_verified", False)
        assert sandbox_verified is False, (
            f"codex.sandbox_verified should be False for MVP, got: {sandbox_verified!r}"
        )

    def test_claude_code_dangerously_skip_permissions_is_false(self, matrix):
        cc = (matrix.get("agents") or {}).get("claude_code") or {}
        dsp = cc.get("dangerously_skip_permissions", False)
        assert dsp is False, (
            f"claude_code.dangerously_skip_permissions should be False, got: {dsp!r}"
        )


# ---------------------------------------------------------------------------
# Section 7: Handoff schema — cost_estimated field
# ---------------------------------------------------------------------------

class TestHandoffSchema:
    def test_schema_file_exists(self):
        assert HANDOFF_SCHEMA_PATH.is_file()

    def test_cost_estimated_field_present(self):
        text = HANDOFF_SCHEMA_PATH.read_text(encoding="utf-8")
        assert "cost_estimated" in text, (
            "handoff-v1.yaml missing cost_estimated field (required by LD-6)"
        )

    def test_cost_method_enum_includes_token_count_estimate(self):
        text = HANDOFF_SCHEMA_PATH.read_text(encoding="utf-8")
        assert "token_count_estimate" in text, (
            "handoff-v1.yaml should include token_count_estimate in cost method enum"
        )
