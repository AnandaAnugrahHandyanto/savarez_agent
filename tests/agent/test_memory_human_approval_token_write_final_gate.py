from copy import deepcopy

from agent.memory_human_approval_token_write_execution_dry_run import (
    create_human_approval_token_write_execution_dry_run,
)
from agent.memory_human_approval_token_write_final_gate import (
    MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_FINAL_GATE_ELIGIBLE,
    MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_FINAL_GATE_KIND,
    MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_FINAL_GATE_LOCKED,
    MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_FINAL_GATE_POLICY,
    MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_FINAL_GATE_ROUTING,
    create_human_approval_token_write_final_gate,
    explain_human_approval_token_write_final_gate,
    recommend_human_approval_token_write_final_gate_action,
    summarize_human_approval_token_write_final_gates,
    validate_human_approval_token_write_final_gate,
)
from tests.agent.test_memory_human_approval_token_write_execution_dry_run import _plan


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


def _dry_run(outcome=None, block_type="procedural_rules"):
    return create_human_approval_token_write_execution_dry_run(
        _plan(outcome=outcome, block_type=block_type),
        operator="token-write-dry-run-operator",
    )


def test_valid_execution_dry_run_creates_eligible_final_gate():
    dry_run = _dry_run()

    gate = create_human_approval_token_write_final_gate(
        dry_run,
        operator="token-write-final-gate-operator",
    )

    assert gate["gate_kind"] == MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_FINAL_GATE_KIND
    assert gate["gate_status"] == MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_FINAL_GATE_ELIGIBLE
    assert gate["routing"] == MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_FINAL_GATE_ROUTING
    assert gate["lock_reason"] is None
    assert gate["source_write_execution_dry_run_id"] == dry_run["dry_run_id"]
    assert gate["source_write_execution_plan_id"] == dry_run["source_write_execution_plan_id"]
    assert gate["source_final_confirmation_review_outcome_id"] == dry_run[
        "source_final_confirmation_review_outcome_id"
    ]
    assert gate["source_final_confirmation_request_id"] == dry_run[
        "source_final_confirmation_request_id"
    ]
    assert gate["source_token_write_lock_gate_id"] == dry_run[
        "source_token_write_lock_gate_id"
    ]
    assert gate["source_token_issuance_dry_run_id"] == dry_run[
        "source_token_issuance_dry_run_id"
    ]
    assert gate["source_token_issuance_plan_id"] == dry_run["source_token_issuance_plan_id"]
    assert gate["source_review_outcome_id"] == dry_run["source_review_outcome_id"]
    assert gate["source_request_id"] == dry_run["source_request_id"]
    assert gate["source_gate_id"] == dry_run["source_gate_id"]
    assert gate["source_dry_run_id"] == dry_run["source_dry_run_id"]
    assert gate["source_plan_id"] == dry_run["source_plan_id"]
    assert gate["source_outcome_id"] == dry_run["source_outcome_id"]
    assert gate["source_packet_id"] == dry_run["source_packet_id"]
    assert gate["source_submission_id"] == dry_run["source_submission_id"]
    assert gate["source_draft_id"] == dry_run["source_draft_id"]
    assert gate["source_decision_id"] == dry_run["source_decision_id"]
    assert gate["source_queue_item_id"] == dry_run["source_queue_item_id"]
    assert gate["operator"] == "token-write-final-gate-operator"
    assert gate["outcome"] == "confirm_token_write"
    assert gate["write_execution_dry_run_validation"] == {"valid": True, "errors": []}
    assert gate["gate_validation"] == {"valid": True, "errors": []}
    assert validate_human_approval_token_write_final_gate(gate) == {
        "valid": True,
        "errors": [],
    }
    assert gate["next_step_recommendation"]["action"] == (
        "route_to_real_token_write_executor_without_invoking_it"
    )


def test_locked_execution_dry_run_creates_locked_gate():
    gate = create_human_approval_token_write_final_gate(_dry_run(outcome="request_changes"))

    assert gate["gate_status"] == MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_FINAL_GATE_LOCKED
    assert gate["lock_reason"] == "final_confirmation_requested_changes"
    assert gate["gate_validation"] == {"valid": True, "errors": []}


def test_invalid_execution_dry_run_creates_locked_gate():
    dry_run = _dry_run()
    dry_run["dry_run_status"] = "unexpected"

    gate = create_human_approval_token_write_final_gate(dry_run)

    assert gate["gate_status"] == MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_FINAL_GATE_LOCKED
    assert gate["lock_reason"] == "invalid_token_write_execution_dry_run"
    assert gate["write_execution_dry_run_validation"]["valid"] is False
    assert gate["gate_validation"] == {"valid": True, "errors": []}


def test_missing_approval_token_record_preview_locks_gate():
    dry_run = _dry_run()
    dry_run.pop("approval_token_record_preview")

    gate = create_human_approval_token_write_final_gate(dry_run)

    assert gate["lock_reason"] == "missing_approval_token_record_preview"
    assert gate["gate_validation"] == {"valid": True, "errors": []}


def test_missing_approval_audit_record_preview_locks_gate():
    dry_run = _dry_run()
    dry_run.pop("approval_audit_record_preview")

    gate = create_human_approval_token_write_final_gate(dry_run)

    assert gate["lock_reason"] == "missing_approval_audit_record_preview"
    assert gate["gate_validation"] == {"valid": True, "errors": []}


def test_missing_token_target_paths_preview_locks_gate():
    dry_run = _dry_run()
    dry_run.pop("token_target_paths_preview")

    gate = create_human_approval_token_write_final_gate(dry_run)

    assert gate["lock_reason"] == "missing_token_target_paths_preview"
    assert gate["gate_validation"] == {"valid": True, "errors": []}


def test_missing_proposal_record_preview_locks_gate():
    dry_run = _dry_run()
    dry_run.pop("proposal_record_preview")

    gate = create_human_approval_token_write_final_gate(dry_run)

    assert gate["lock_reason"] == "missing_proposal_record_preview"
    assert gate["gate_validation"] == {"valid": True, "errors": []}


def test_missing_operation_ledger_preview_locks_gate():
    dry_run = _dry_run()
    dry_run.pop("operation_ledger_preview")

    gate = create_human_approval_token_write_final_gate(dry_run)

    assert gate["lock_reason"] == "missing_operation_ledger_preview"
    assert gate["gate_validation"] == {"valid": True, "errors": []}


def test_missing_target_paths_preview_locks_gate():
    dry_run = _dry_run()
    dry_run.pop("target_paths_preview")

    gate = create_human_approval_token_write_final_gate(dry_run)

    assert gate["lock_reason"] == "missing_target_paths_preview"
    assert gate["gate_validation"] == {"valid": True, "errors": []}


def test_missing_approval_token_write_payload_preview_locks_gate():
    dry_run = _dry_run()
    dry_run.pop("approval_token_write_payload_preview")

    gate = create_human_approval_token_write_final_gate(dry_run)

    assert gate["lock_reason"] == "missing_approval_token_write_payload_preview"
    assert gate["gate_validation"] == {"valid": True, "errors": []}


def test_missing_approval_audit_write_payload_preview_locks_gate():
    dry_run = _dry_run()
    dry_run.pop("approval_audit_write_payload_preview")

    gate = create_human_approval_token_write_final_gate(dry_run)

    assert gate["lock_reason"] == "missing_approval_audit_write_payload_preview"
    assert gate["gate_validation"] == {"valid": True, "errors": []}


def test_missing_token_write_target_paths_preview_locks_gate():
    dry_run = _dry_run()
    dry_run.pop("token_write_target_paths_preview")

    gate = create_human_approval_token_write_final_gate(dry_run)

    assert gate["lock_reason"] == "missing_token_write_target_paths_preview"
    assert gate["gate_validation"] == {"valid": True, "errors": []}


def test_missing_source_evidence_locks_gate():
    dry_run = _dry_run()
    dry_run["source_pattern_ids"] = []
    dry_run["source_fact_ids"] = []

    gate = create_human_approval_token_write_final_gate(dry_run)

    assert gate["lock_reason"] == "missing_source_evidence"
    assert gate["gate_status"] == MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_FINAL_GATE_LOCKED
    assert gate["gate_validation"] == {"valid": True, "errors": []}


def test_missing_final_token_write_preflight_checklist_locks_gate():
    dry_run = _dry_run()
    dry_run.pop("final_token_write_preflight_checklist")

    gate = create_human_approval_token_write_final_gate(dry_run)

    assert gate["lock_reason"] == "missing_final_token_write_preflight_checklist"
    assert gate["gate_validation"] == {"valid": True, "errors": []}


def test_preview_integrity_failed_locks_gate():
    dry_run = _dry_run()
    dry_run["approval_token_record_preview"]["token_issued"] = True

    gate = create_human_approval_token_write_final_gate(dry_run)

    assert gate["lock_reason"] == "preview_integrity_failed"
    assert gate["gate_status"] == MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_FINAL_GATE_LOCKED
    assert gate["gate_validation"] == {"valid": True, "errors": []}


def test_final_preflight_integrity_failed_locks_gate():
    dry_run = _dry_run()
    dry_run["approval_token_write_payload_preview"]["token_issued"] = True

    gate = create_human_approval_token_write_final_gate(dry_run)

    assert gate["lock_reason"] == "final_preflight_integrity_failed"
    assert gate["gate_status"] == MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_FINAL_GATE_LOCKED
    assert gate["gate_validation"] == {"valid": True, "errors": []}


def test_final_gate_checklist_is_deterministic():
    gate_a = create_human_approval_token_write_final_gate(_dry_run())
    gate_b = create_human_approval_token_write_final_gate(_dry_run())

    assert gate_a["final_gate_checklist"] == gate_b["final_gate_checklist"]
    assert "real_token_write_executor_required_but_not_invoked" in gate_a[
        "final_gate_checklist"
    ]


def test_input_write_execution_dry_run_is_not_mutated():
    dry_run = _dry_run()
    before = deepcopy(dry_run)

    gate = create_human_approval_token_write_final_gate(dry_run)
    gate["source_write_execution_dry_run_snapshot"]["payload_preview"]["content"]["nested"][
        "value"
    ] = "changed"

    assert dry_run == before


def test_policy_proves_no_writes_and_does_not_invoke_real_executor(tmp_path, monkeypatch):
    hermes_home = tmp_path / "hermes-home"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    gate = create_human_approval_token_write_final_gate(_dry_run())
    explanation = explain_human_approval_token_write_final_gate(gate)
    recommendation = recommend_human_approval_token_write_final_gate_action(gate)

    assert gate["policy"] == MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_FINAL_GATE_POLICY
    assert gate["policy"]["read_only"] is True
    assert gate["policy"]["would_write_memory"] is False
    assert gate["policy"]["would_modify_config"] is False
    assert gate["policy"]["would_write_graph"] is False
    assert gate["policy"]["does_not_create_operation_events"] is True
    assert gate["policy"]["creates_token_write_final_gate_candidates_only"] is True
    assert gate["policy"]["invokes_real_token_write_executor"] is False
    assert gate["policy"]["issues_real_approval_tokens"] is False
    assert gate["policy"]["persists_approvals"] is False
    assert gate["policy"]["creates_real_proposals"] is False
    assert gate["policy"]["writes_proposal_files"] is False
    assert gate["policy"]["writes_operation_ledger"] is False
    assert gate["policy"]["writes_token_files"] is False
    assert gate["policy"]["writes_approval_audit"] is False
    assert gate["policy"]["applies_proposals"] is False
    assert gate["policy"]["submits_to_governance"] is False
    assert gate["policy"]["converts_to_real_proposal"] is False
    for forbidden_key in FORBIDDEN_TRUE_KEYS:
        assert explanation[forbidden_key] is False
    assert explanation["invokes_real_token_write_executor"] is False
    assert recommendation["invokes_real_token_write_executor"] is False
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


def test_gate_must_never_be_marked_as_written_issued_approved_persisted_or_converted():
    for forbidden_key in FORBIDDEN_TRUE_KEYS:
        gate = create_human_approval_token_write_final_gate(_dry_run())
        gate[forbidden_key] = True

        validation = validate_human_approval_token_write_final_gate(gate)

        assert validation["valid"] is False
        assert f"{forbidden_key}_must_be_false_or_absent" in validation["errors"]


def test_summary_counts_locked_eligible_candidates_and_by_block_type_status():
    eligible_gate = create_human_approval_token_write_final_gate(
        _dry_run(block_type="procedural_rules")
    )
    locked_gate = create_human_approval_token_write_final_gate(
        _dry_run(block_type="preference", outcome="request_changes")
    )

    summary = summarize_human_approval_token_write_final_gates([eligible_gate, locked_gate])

    assert summary["total"] == 2
    assert summary["valid_count"] == 2
    assert summary["invalid_count"] == 0
    assert summary["eligible_for_real_token_write_executor_count"] == 1
    assert summary["locked_count"] == 1
    assert summary["by_block_type"] == {"preference": 1, "procedural_rules": 1}
    assert summary["by_status"] == {
        "eligible_for_real_token_write_executor": 1,
        "locked": 1,
    }
