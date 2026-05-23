from copy import deepcopy

from agent.memory_human_approval_token_final_confirmation_review_gate import (
    create_human_approval_token_final_confirmation_review_outcome,
)
from agent.memory_human_approval_token_write_execution_plan import (
    MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_EXECUTION_PLAN_KIND,
    MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_EXECUTION_PLAN_LOCKED,
    MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_EXECUTION_PLAN_POLICY,
    MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_EXECUTION_PLAN_REQUIRED,
    MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_EXECUTION_PLAN_ROUTING,
    create_human_approval_token_write_execution_plan,
    explain_human_approval_token_write_execution_plan,
    recommend_human_approval_token_write_execution_plan_action,
    summarize_human_approval_token_write_execution_plans,
    validate_human_approval_token_write_execution_plan,
)
from tests.agent.test_memory_human_approval_token_final_confirmation_review_gate import _request


FORBIDDEN_TRUE_KEYS = (
    "token_issued",
    "approved",
    "persisted",
    "submitted",
    "written",
    "created_real_proposal",
    "created_operation_event",
    "writes_proposal_files",
    "writes_operation_ledger",
    "writes_token_files",
    "writes_approval_audit",
    "converted_to_real_proposal",
)


def _outcome(outcome=None, block_type="procedural_rules", source_pattern_ids=None, source_fact_ids=None):
    return create_human_approval_token_final_confirmation_review_outcome(
        _request(
            block_type=block_type,
            source_pattern_ids=source_pattern_ids,
            source_fact_ids=source_fact_ids,
        ),
        confirmer="final-confirmation-confirmer",
        outcome=outcome,
        rationale=f"Explicit {outcome} outcome." if outcome else None,
    )


def test_confirm_token_write_outcome_creates_manual_token_write_execution_plan_required_plan():
    outcome = _outcome()

    plan = create_human_approval_token_write_execution_plan(outcome, executor="token-write-executor")

    assert plan["plan_kind"] == MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_EXECUTION_PLAN_KIND
    assert plan["plan_status"] == MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_EXECUTION_PLAN_REQUIRED
    assert plan["routing"] == MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_EXECUTION_PLAN_ROUTING
    assert plan["lock_reason"] is None
    assert plan["source_final_confirmation_review_outcome_id"] == outcome["review_outcome_id"]
    assert plan["source_final_confirmation_request_id"] == outcome["source_final_confirmation_request_id"]
    assert plan["source_token_write_lock_gate_id"] == outcome["source_token_write_lock_gate_id"]
    assert plan["source_token_issuance_dry_run_id"] == outcome["source_token_issuance_dry_run_id"]
    assert plan["source_token_issuance_plan_id"] == outcome["source_token_issuance_plan_id"]
    assert plan["source_review_outcome_id"] == outcome["source_review_outcome_id"]
    assert plan["source_request_id"] == outcome["source_request_id"]
    assert plan["source_gate_id"] == outcome["source_gate_id"]
    assert plan["source_dry_run_id"] == outcome["source_dry_run_id"]
    assert plan["source_plan_id"] == outcome["source_plan_id"]
    assert plan["source_outcome_id"] == outcome["source_outcome_id"]
    assert plan["source_packet_id"] == outcome["source_packet_id"]
    assert plan["source_submission_id"] == outcome["source_submission_id"]
    assert plan["source_draft_id"] == outcome["source_draft_id"]
    assert plan["source_decision_id"] == outcome["source_decision_id"]
    assert plan["source_queue_item_id"] == outcome["source_queue_item_id"]
    assert plan["executor"] == "token-write-executor"
    assert plan["outcome"] == "confirm_token_write"
    assert plan["final_confirmation_review_outcome_validation"] == {"valid": True, "errors": []}
    assert plan["plan_validation"] == {"valid": True, "errors": []}
    assert validate_human_approval_token_write_execution_plan(plan) == {"valid": True, "errors": []}
    assert plan["next_step_recommendation"]["action"] == "route_to_manual_token_write_dry_run_without_issuing_token"


def test_request_changes_creates_locked_plan():
    plan = create_human_approval_token_write_execution_plan(_outcome(outcome="request_changes"))

    assert plan["plan_status"] == MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_EXECUTION_PLAN_LOCKED
    assert plan["lock_reason"] == "final_confirmation_requested_changes"
    assert plan["plan_validation"] == {"valid": True, "errors": []}


def test_reject_creates_locked_plan():
    plan = create_human_approval_token_write_execution_plan(_outcome(outcome="reject"))

    assert plan["plan_status"] == MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_EXECUTION_PLAN_LOCKED
    assert plan["lock_reason"] == "final_confirmation_rejected"
    assert plan["plan_validation"] == {"valid": True, "errors": []}


def test_defer_creates_locked_plan():
    plan = create_human_approval_token_write_execution_plan(_outcome(outcome="defer"))

    assert plan["plan_status"] == MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_EXECUTION_PLAN_LOCKED
    assert plan["lock_reason"] == "final_confirmation_deferred"
    assert plan["plan_validation"] == {"valid": True, "errors": []}


def test_invalid_review_outcome_creates_locked_plan():
    outcome = _outcome()
    outcome["outcome"] = "approve_and_issue"

    plan = create_human_approval_token_write_execution_plan(outcome)

    assert plan["plan_status"] == MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_EXECUTION_PLAN_LOCKED
    assert plan["lock_reason"] == "invalid_final_confirmation_review_outcome"
    assert plan["final_confirmation_review_outcome_validation"]["valid"] is False
    assert plan["plan_validation"] == {"valid": True, "errors": []}


def test_missing_approval_token_record_preview_locks_plan():
    outcome = _outcome()
    outcome.pop("approval_token_record_preview")

    plan = create_human_approval_token_write_execution_plan(outcome)

    assert plan["lock_reason"] == "missing_approval_token_record_preview"
    assert plan["plan_status"] == MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_EXECUTION_PLAN_LOCKED
    assert plan["plan_validation"] == {"valid": True, "errors": []}


def test_missing_approval_audit_record_preview_locks_plan():
    outcome = _outcome()
    outcome.pop("approval_audit_record_preview")

    plan = create_human_approval_token_write_execution_plan(outcome)

    assert plan["lock_reason"] == "missing_approval_audit_record_preview"
    assert plan["plan_validation"] == {"valid": True, "errors": []}


def test_missing_token_target_paths_preview_locks_plan():
    outcome = _outcome()
    outcome.pop("token_target_paths_preview")

    plan = create_human_approval_token_write_execution_plan(outcome)

    assert plan["lock_reason"] == "missing_token_target_paths_preview"
    assert plan["plan_validation"] == {"valid": True, "errors": []}


def test_missing_proposal_record_preview_locks_plan():
    outcome = _outcome()
    outcome.pop("proposal_record_preview")

    plan = create_human_approval_token_write_execution_plan(outcome)

    assert plan["lock_reason"] == "missing_proposal_record_preview"
    assert plan["plan_validation"] == {"valid": True, "errors": []}


def test_missing_operation_ledger_preview_locks_plan():
    outcome = _outcome()
    outcome.pop("operation_ledger_preview")

    plan = create_human_approval_token_write_execution_plan(outcome)

    assert plan["lock_reason"] == "missing_operation_ledger_preview"
    assert plan["plan_validation"] == {"valid": True, "errors": []}


def test_missing_target_paths_preview_locks_plan():
    outcome = _outcome()
    outcome.pop("target_paths_preview")

    plan = create_human_approval_token_write_execution_plan(outcome)

    assert plan["lock_reason"] == "missing_target_paths_preview"
    assert plan["plan_validation"] == {"valid": True, "errors": []}


def test_missing_source_evidence_locks_plan():
    outcome = _outcome()
    outcome["source_pattern_ids"] = []
    outcome["source_fact_ids"] = []

    plan = create_human_approval_token_write_execution_plan(outcome)

    assert plan["lock_reason"] == "missing_source_evidence"
    assert plan["plan_status"] == MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_EXECUTION_PLAN_LOCKED
    assert plan["plan_validation"] == {"valid": True, "errors": []}


def test_preview_integrity_failed_locks_plan():
    outcome = _outcome()
    outcome["approval_token_record_preview"]["token_issued"] = True

    plan = create_human_approval_token_write_execution_plan(outcome)

    assert plan["lock_reason"] == "preview_integrity_failed"
    assert plan["plan_status"] == MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_EXECUTION_PLAN_LOCKED
    assert plan["plan_validation"] == {"valid": True, "errors": []}


def test_token_write_execution_steps_and_preflight_checks_are_deterministic():
    plan_a = create_human_approval_token_write_execution_plan(_outcome())
    plan_b = create_human_approval_token_write_execution_plan(_outcome())

    assert plan_a["token_write_execution_steps"] == plan_b["token_write_execution_steps"]
    assert plan_a["token_write_execution_preflight_checks"] == plan_b["token_write_execution_preflight_checks"]
    assert [step["order"] for step in plan_a["token_write_execution_steps"]] == [1, 2, 3, 4]
    assert all(step["writes"] is False for step in plan_a["token_write_execution_steps"])
    assert all(check["required"] is True for check in plan_a["token_write_execution_preflight_checks"])
    assert all(check["blocks_token_write"] is True for check in plan_a["token_write_execution_preflight_checks"])


def test_input_final_confirmation_review_outcome_is_not_mutated():
    outcome = _outcome()
    before = deepcopy(outcome)

    plan = create_human_approval_token_write_execution_plan(outcome)
    plan["source_final_confirmation_review_outcome_snapshot"]["payload_preview"]["content"]["nested"]["value"] = "changed"

    assert outcome == before


def test_policy_proves_no_memory_config_graph_proposal_ledger_token_or_approval_writes(tmp_path, monkeypatch):
    hermes_home = tmp_path / "hermes-home"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    plan = create_human_approval_token_write_execution_plan(_outcome())
    explanation = explain_human_approval_token_write_execution_plan(plan)
    recommendation = recommend_human_approval_token_write_execution_plan_action(plan)

    assert plan["policy"] == MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_EXECUTION_PLAN_POLICY
    assert plan["policy"]["read_only"] is True
    assert plan["policy"]["would_write_memory"] is False
    assert plan["policy"]["would_modify_config"] is False
    assert plan["policy"]["would_write_graph"] is False
    assert plan["policy"]["does_not_create_operation_events"] is True
    assert plan["policy"]["creates_token_write_execution_plan_candidates_only"] is True
    assert plan["policy"]["issues_real_approval_tokens"] is False
    assert plan["policy"]["persists_approvals"] is False
    assert plan["policy"]["creates_real_proposals"] is False
    assert plan["policy"]["writes_proposal_files"] is False
    assert plan["policy"]["writes_operation_ledger"] is False
    assert plan["policy"]["writes_token_files"] is False
    assert plan["policy"]["writes_approval_audit"] is False
    assert plan["policy"]["applies_proposals"] is False
    assert plan["policy"]["submits_to_governance"] is False
    assert plan["policy"]["converts_to_real_proposal"] is False
    assert explanation["token_issued"] is False
    assert explanation["approved"] is False
    assert explanation["persisted"] is False
    assert explanation["submitted"] is False
    assert explanation["written"] is False
    assert explanation["created_real_proposal"] is False
    assert explanation["created_operation_event"] is False
    assert explanation["writes_proposal_files"] is False
    assert explanation["writes_operation_ledger"] is False
    assert explanation["writes_token_files"] is False
    assert explanation["writes_approval_audit"] is False
    assert explanation["converted_to_real_proposal"] is False
    assert recommendation["issues_real_approval_tokens"] is False
    assert recommendation["persists_approvals"] is False
    assert recommendation["creates_real_proposals"] is False
    assert recommendation["writes_proposal_files"] is False
    assert recommendation["writes_operation_ledger"] is False
    assert recommendation["writes_token_files"] is False
    assert recommendation["writes_approval_audit"] is False
    assert not (hermes_home / "memory" / "graph" / "memory_graph.sqlite").exists()
    assert not (hermes_home / "memory" / "audit" / "memory_operation_ledger.jsonl").exists()
    assert not (hermes_home / "memory" / "proposals" / "memory_write_proposals.jsonl").exists()
    assert not (hermes_home / "memory" / "approvals" / "human_approval_tokens.jsonl").exists()
    assert not (hermes_home / "memory" / "audit" / "human_approval_token_audit.jsonl").exists()


def test_plan_must_never_be_marked_as_written_issued_approved_persisted_or_converted():
    for forbidden_key in FORBIDDEN_TRUE_KEYS:
        plan = create_human_approval_token_write_execution_plan(_outcome())
        plan[forbidden_key] = True

        validation = validate_human_approval_token_write_execution_plan(plan)

        assert validation["valid"] is False
        assert f"{forbidden_key}_must_be_false_or_absent" in validation["errors"]


def test_summary_counts_locked_execution_plan_required_candidates_and_by_block_type_status():
    required_plan = create_human_approval_token_write_execution_plan(
        _outcome(block_type="procedural_rules")
    )
    locked_plan = create_human_approval_token_write_execution_plan(
        _outcome(block_type="preference", outcome="request_changes")
    )

    summary = summarize_human_approval_token_write_execution_plans([required_plan, locked_plan])

    assert summary["total"] == 2
    assert summary["valid_count"] == 2
    assert summary["invalid_count"] == 0
    assert summary["execution_plan_required_count"] == 1
    assert summary["locked_count"] == 1
    assert summary["by_block_type"] == {"preference": 1, "procedural_rules": 1}
    assert summary["by_status"] == {
        "locked": 1,
        "manual_token_write_execution_plan_required": 1,
    }
