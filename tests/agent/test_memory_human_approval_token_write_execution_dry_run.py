from copy import deepcopy

from agent.memory_human_approval_token_write_execution_plan import (
    create_human_approval_token_write_execution_plan,
)
from agent.memory_human_approval_token_write_execution_dry_run import (
    MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_EXECUTION_DRY_RUN_FINAL_PREFLIGHT_REQUIRED,
    MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_EXECUTION_DRY_RUN_KIND,
    MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_EXECUTION_DRY_RUN_LOCKED,
    MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_EXECUTION_DRY_RUN_POLICY,
    MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_EXECUTION_DRY_RUN_ROUTING,
    create_human_approval_token_write_execution_dry_run,
    explain_human_approval_token_write_execution_dry_run,
    recommend_human_approval_token_write_execution_dry_run_action,
    summarize_human_approval_token_write_execution_dry_runs,
    validate_human_approval_token_write_execution_dry_run,
)
from tests.agent.test_memory_human_approval_token_write_execution_plan import _outcome


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


def _plan(outcome=None, block_type="procedural_rules"):
    return create_human_approval_token_write_execution_plan(
        _outcome(outcome=outcome, block_type=block_type),
        executor="token-write-executor",
    )


def test_valid_execution_plan_creates_manual_token_write_final_preflight_required_dry_run():
    plan = _plan()

    dry_run = create_human_approval_token_write_execution_dry_run(
        plan,
        operator="token-write-dry-run-operator",
    )

    assert dry_run["dry_run_kind"] == MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_EXECUTION_DRY_RUN_KIND
    assert (
        dry_run["dry_run_status"]
        == MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_EXECUTION_DRY_RUN_FINAL_PREFLIGHT_REQUIRED
    )
    assert dry_run["routing"] == MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_EXECUTION_DRY_RUN_ROUTING
    assert dry_run["lock_reason"] is None
    assert dry_run["source_write_execution_plan_id"] == plan["plan_id"]
    assert dry_run["source_final_confirmation_review_outcome_id"] == plan[
        "source_final_confirmation_review_outcome_id"
    ]
    assert dry_run["source_final_confirmation_request_id"] == plan[
        "source_final_confirmation_request_id"
    ]
    assert dry_run["source_token_write_lock_gate_id"] == plan["source_token_write_lock_gate_id"]
    assert dry_run["source_token_issuance_dry_run_id"] == plan[
        "source_token_issuance_dry_run_id"
    ]
    assert dry_run["source_token_issuance_plan_id"] == plan["source_token_issuance_plan_id"]
    assert dry_run["source_review_outcome_id"] == plan["source_review_outcome_id"]
    assert dry_run["source_request_id"] == plan["source_request_id"]
    assert dry_run["source_gate_id"] == plan["source_gate_id"]
    assert dry_run["source_dry_run_id"] == plan["source_dry_run_id"]
    assert dry_run["source_plan_id"] == plan["source_plan_id"]
    assert dry_run["source_outcome_id"] == plan["source_outcome_id"]
    assert dry_run["source_packet_id"] == plan["source_packet_id"]
    assert dry_run["source_submission_id"] == plan["source_submission_id"]
    assert dry_run["source_draft_id"] == plan["source_draft_id"]
    assert dry_run["source_decision_id"] == plan["source_decision_id"]
    assert dry_run["source_queue_item_id"] == plan["source_queue_item_id"]
    assert dry_run["operator"] == "token-write-dry-run-operator"
    assert dry_run["outcome"] == "confirm_token_write"
    assert dry_run["write_execution_plan_validation"] == {"valid": True, "errors": []}
    assert dry_run["dry_run_validation"] == {"valid": True, "errors": []}
    assert validate_human_approval_token_write_execution_dry_run(dry_run) == {
        "valid": True,
        "errors": [],
    }
    assert dry_run["next_step_recommendation"]["action"] == (
        "route_to_manual_token_write_final_gate_without_issuing_token"
    )


def test_locked_execution_plan_creates_locked_dry_run():
    dry_run = create_human_approval_token_write_execution_dry_run(
        _plan(outcome="request_changes")
    )

    assert dry_run["dry_run_status"] == MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_EXECUTION_DRY_RUN_LOCKED
    assert dry_run["lock_reason"] == "final_confirmation_requested_changes"
    assert dry_run["dry_run_validation"] == {"valid": True, "errors": []}


def test_invalid_execution_plan_creates_locked_dry_run():
    plan = _plan()
    plan["plan_status"] = "unexpected"

    dry_run = create_human_approval_token_write_execution_dry_run(plan)

    assert dry_run["dry_run_status"] == MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_EXECUTION_DRY_RUN_LOCKED
    assert dry_run["lock_reason"] == "invalid_token_write_execution_plan"
    assert dry_run["write_execution_plan_validation"]["valid"] is False
    assert dry_run["dry_run_validation"] == {"valid": True, "errors": []}


def test_missing_approval_token_record_preview_locks_dry_run():
    plan = _plan()
    plan.pop("approval_token_record_preview")

    dry_run = create_human_approval_token_write_execution_dry_run(plan)

    assert dry_run["lock_reason"] == "missing_approval_token_record_preview"
    assert dry_run["dry_run_validation"] == {"valid": True, "errors": []}


def test_missing_approval_audit_record_preview_locks_dry_run():
    plan = _plan()
    plan.pop("approval_audit_record_preview")

    dry_run = create_human_approval_token_write_execution_dry_run(plan)

    assert dry_run["lock_reason"] == "missing_approval_audit_record_preview"
    assert dry_run["dry_run_validation"] == {"valid": True, "errors": []}


def test_missing_token_target_paths_preview_locks_dry_run():
    plan = _plan()
    plan.pop("token_target_paths_preview")

    dry_run = create_human_approval_token_write_execution_dry_run(plan)

    assert dry_run["lock_reason"] == "missing_token_target_paths_preview"
    assert dry_run["dry_run_validation"] == {"valid": True, "errors": []}


def test_missing_proposal_record_preview_locks_dry_run():
    plan = _plan()
    plan.pop("proposal_record_preview")

    dry_run = create_human_approval_token_write_execution_dry_run(plan)

    assert dry_run["lock_reason"] == "missing_proposal_record_preview"
    assert dry_run["dry_run_validation"] == {"valid": True, "errors": []}


def test_missing_operation_ledger_preview_locks_dry_run():
    plan = _plan()
    plan.pop("operation_ledger_preview")

    dry_run = create_human_approval_token_write_execution_dry_run(plan)

    assert dry_run["lock_reason"] == "missing_operation_ledger_preview"
    assert dry_run["dry_run_validation"] == {"valid": True, "errors": []}


def test_missing_target_paths_preview_locks_dry_run():
    plan = _plan()
    plan.pop("target_paths_preview")

    dry_run = create_human_approval_token_write_execution_dry_run(plan)

    assert dry_run["lock_reason"] == "missing_target_paths_preview"
    assert dry_run["dry_run_validation"] == {"valid": True, "errors": []}


def test_missing_source_evidence_locks_dry_run():
    plan = _plan()
    plan["source_pattern_ids"] = []
    plan["source_fact_ids"] = []

    dry_run = create_human_approval_token_write_execution_dry_run(plan)

    assert dry_run["lock_reason"] == "missing_source_evidence"
    assert dry_run["dry_run_status"] == MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_EXECUTION_DRY_RUN_LOCKED
    assert dry_run["dry_run_validation"] == {"valid": True, "errors": []}


def test_missing_token_write_execution_controls_locks_dry_run():
    plan = _plan()
    plan.pop("token_write_execution_steps")

    dry_run = create_human_approval_token_write_execution_dry_run(plan)

    assert dry_run["lock_reason"] == "missing_token_write_execution_controls"
    assert dry_run["dry_run_validation"] == {"valid": True, "errors": []}

    plan = _plan()
    plan.pop("token_write_execution_preflight_checks")
    dry_run = create_human_approval_token_write_execution_dry_run(plan)

    assert dry_run["lock_reason"] == "missing_token_write_execution_controls"
    assert dry_run["dry_run_validation"] == {"valid": True, "errors": []}


def test_preview_integrity_failed_locks_dry_run():
    plan = _plan()
    plan["approval_token_record_preview"]["token_issued"] = True

    dry_run = create_human_approval_token_write_execution_dry_run(plan)

    assert dry_run["lock_reason"] == "preview_integrity_failed"
    assert dry_run["dry_run_status"] == MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_EXECUTION_DRY_RUN_LOCKED
    assert dry_run["dry_run_validation"] == {"valid": True, "errors": []}


def test_write_payload_and_target_path_previews_are_preview_only_and_deterministic():
    plan = _plan()

    dry_run_a = create_human_approval_token_write_execution_dry_run(plan)
    dry_run_b = create_human_approval_token_write_execution_dry_run(plan)

    assert dry_run_a["approval_token_write_payload_preview"] == dry_run_b[
        "approval_token_write_payload_preview"
    ]
    assert dry_run_a["approval_audit_write_payload_preview"] == dry_run_b[
        "approval_audit_write_payload_preview"
    ]
    assert dry_run_a["token_write_target_paths_preview"] == dry_run_b[
        "token_write_target_paths_preview"
    ]
    assert dry_run_a["approval_token_write_payload_preview"]["preview_only"] is True
    assert dry_run_a["approval_token_write_payload_preview"]["token_issued"] is False
    assert dry_run_a["approval_token_write_payload_preview"]["persisted"] is False
    assert dry_run_a["approval_token_write_payload_preview"]["written"] is False
    assert dry_run_a["approval_audit_write_payload_preview"]["preview_only"] is True
    assert dry_run_a["approval_audit_write_payload_preview"]["created_operation_event"] is False
    assert dry_run_a["approval_audit_write_payload_preview"]["writes_approval_audit"] is False
    assert dry_run_a["approval_audit_write_payload_preview"]["writes_operation_ledger"] is False
    assert dry_run_a["token_write_target_paths_preview"]["preview_only"] is True
    assert dry_run_a["token_write_target_paths_preview"]["writes_token_files"] is False
    assert dry_run_a["token_write_target_paths_preview"]["writes_approval_audit"] is False
    assert dry_run_a["token_write_target_paths_preview"]["writes_operation_ledger"] is False


def test_final_token_write_preflight_checklist_is_deterministic():
    dry_run_a = create_human_approval_token_write_execution_dry_run(_plan())
    dry_run_b = create_human_approval_token_write_execution_dry_run(_plan())

    assert dry_run_a["final_token_write_preflight_checklist"] == dry_run_b[
        "final_token_write_preflight_checklist"
    ]
    assert "manual_token_write_final_gate_required_before_any_token_write" in dry_run_a[
        "final_token_write_preflight_checklist"
    ]


def test_input_write_execution_plan_is_not_mutated():
    plan = _plan()
    before = deepcopy(plan)

    dry_run = create_human_approval_token_write_execution_dry_run(plan)
    dry_run["source_write_execution_plan_snapshot"]["payload_preview"]["content"]["nested"][
        "value"
    ] = "changed"

    assert plan == before


def test_policy_proves_no_memory_config_graph_proposal_ledger_token_or_approval_writes(
    tmp_path,
    monkeypatch,
):
    hermes_home = tmp_path / "hermes-home"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    dry_run = create_human_approval_token_write_execution_dry_run(_plan())
    explanation = explain_human_approval_token_write_execution_dry_run(dry_run)
    recommendation = recommend_human_approval_token_write_execution_dry_run_action(dry_run)

    assert dry_run["policy"] == MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_EXECUTION_DRY_RUN_POLICY
    assert dry_run["policy"]["read_only"] is True
    assert dry_run["policy"]["would_write_memory"] is False
    assert dry_run["policy"]["would_modify_config"] is False
    assert dry_run["policy"]["would_write_graph"] is False
    assert dry_run["policy"]["does_not_create_operation_events"] is True
    assert dry_run["policy"]["creates_token_write_execution_dry_run_candidates_only"] is True
    assert dry_run["policy"]["issues_real_approval_tokens"] is False
    assert dry_run["policy"]["persists_approvals"] is False
    assert dry_run["policy"]["creates_real_proposals"] is False
    assert dry_run["policy"]["writes_proposal_files"] is False
    assert dry_run["policy"]["writes_operation_ledger"] is False
    assert dry_run["policy"]["writes_token_files"] is False
    assert dry_run["policy"]["writes_approval_audit"] is False
    assert dry_run["policy"]["applies_proposals"] is False
    assert dry_run["policy"]["submits_to_governance"] is False
    assert dry_run["policy"]["converts_to_real_proposal"] is False
    for forbidden_key in FORBIDDEN_TRUE_KEYS:
        assert explanation[forbidden_key] is False
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


def test_dry_run_must_never_be_marked_as_written_issued_approved_persisted_or_converted():
    for forbidden_key in FORBIDDEN_TRUE_KEYS:
        dry_run = create_human_approval_token_write_execution_dry_run(_plan())
        dry_run[forbidden_key] = True

        validation = validate_human_approval_token_write_execution_dry_run(dry_run)

        assert validation["valid"] is False
        assert f"{forbidden_key}_must_be_false_or_absent" in validation["errors"]


def test_summary_counts_locked_final_preflight_required_candidates_and_by_block_type_status():
    required_dry_run = create_human_approval_token_write_execution_dry_run(
        _plan(block_type="procedural_rules")
    )
    locked_dry_run = create_human_approval_token_write_execution_dry_run(
        _plan(block_type="preference", outcome="request_changes")
    )

    summary = summarize_human_approval_token_write_execution_dry_runs(
        [required_dry_run, locked_dry_run]
    )

    assert summary["total"] == 2
    assert summary["valid_count"] == 2
    assert summary["invalid_count"] == 0
    assert summary["final_preflight_required_count"] == 1
    assert summary["locked_count"] == 1
    assert summary["by_block_type"] == {"preference": 1, "procedural_rules": 1}
    assert summary["by_status"] == {
        "locked": 1,
        "manual_token_write_final_preflight_required": 1,
    }
