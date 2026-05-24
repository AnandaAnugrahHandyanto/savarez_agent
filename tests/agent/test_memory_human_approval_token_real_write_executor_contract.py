from copy import deepcopy

from agent.memory_human_approval_token_real_write_executor_contract import (
    MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_KIND,
    MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_LOCKED,
    MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_POLICY,
    MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_REQUIRED,
    MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_ROUTING,
    create_human_approval_token_real_write_executor_contract,
    explain_human_approval_token_real_write_executor_contract,
    recommend_human_approval_token_real_write_executor_contract_action,
    summarize_human_approval_token_real_write_executor_contracts,
    validate_human_approval_token_real_write_executor_contract,
)
from agent.memory_human_approval_token_write_final_gate import (
    create_human_approval_token_write_final_gate,
)
from tests.agent.test_memory_human_approval_token_write_final_gate import _dry_run


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
    "invokes_real_token_write_executor",
    "implements_real_token_write_executor",
    "converted_to_real_proposal",
)


def _gate(outcome=None, block_type="procedural_rules"):
    return create_human_approval_token_write_final_gate(
        _dry_run(outcome=outcome, block_type=block_type),
        operator="token-write-final-gate-operator",
    )


def test_valid_write_final_gate_creates_real_token_write_executor_contract_required():
    gate = _gate()

    contract = create_human_approval_token_real_write_executor_contract(
        gate,
        operator="real-write-executor-contract-operator",
    )

    assert contract["contract_kind"] == MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_KIND
    assert (
        contract["contract_status"]
        == MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_REQUIRED
    )
    assert contract["routing"] == MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_ROUTING
    assert contract["lock_reason"] is None
    assert contract["source_write_final_gate_id"] == gate["gate_id"]
    assert contract["source_write_execution_dry_run_id"] == gate[
        "source_write_execution_dry_run_id"
    ]
    assert contract["source_write_execution_plan_id"] == gate["source_write_execution_plan_id"]
    assert contract["source_final_confirmation_review_outcome_id"] == gate[
        "source_final_confirmation_review_outcome_id"
    ]
    assert contract["source_final_confirmation_request_id"] == gate[
        "source_final_confirmation_request_id"
    ]
    assert contract["source_token_write_lock_gate_id"] == gate[
        "source_token_write_lock_gate_id"
    ]
    assert contract["source_token_issuance_dry_run_id"] == gate[
        "source_token_issuance_dry_run_id"
    ]
    assert contract["source_token_issuance_plan_id"] == gate[
        "source_token_issuance_plan_id"
    ]
    assert contract["source_review_outcome_id"] == gate["source_review_outcome_id"]
    assert contract["source_request_id"] == gate["source_request_id"]
    assert contract["source_gate_id"] == gate["source_gate_id"]
    assert contract["source_dry_run_id"] == gate["source_dry_run_id"]
    assert contract["source_plan_id"] == gate["source_plan_id"]
    assert contract["source_outcome_id"] == gate["source_outcome_id"]
    assert contract["source_packet_id"] == gate["source_packet_id"]
    assert contract["source_submission_id"] == gate["source_submission_id"]
    assert contract["source_draft_id"] == gate["source_draft_id"]
    assert contract["source_decision_id"] == gate["source_decision_id"]
    assert contract["source_queue_item_id"] == gate["source_queue_item_id"]
    assert contract["operator"] == "real-write-executor-contract-operator"
    assert contract["outcome"] == "confirm_token_write"
    assert contract["write_final_gate_validation"] == {"valid": True, "errors": []}
    assert contract["contract_validation"] == {"valid": True, "errors": []}
    assert validate_human_approval_token_real_write_executor_contract(contract) == {
        "valid": True,
        "errors": [],
    }
    assert contract["next_step_recommendation"]["action"] == (
        "route_to_real_token_write_executor_contract_review_without_implementation"
    )


def test_locked_write_final_gate_creates_locked_contract():
    contract = create_human_approval_token_real_write_executor_contract(
        _gate(outcome="request_changes")
    )

    assert (
        contract["contract_status"] == MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_LOCKED
    )
    assert contract["lock_reason"] == "final_confirmation_requested_changes"
    assert contract["contract_validation"] == {"valid": True, "errors": []}


def test_invalid_write_final_gate_creates_locked_contract():
    gate = _gate()
    gate["gate_status"] = "unexpected"

    contract = create_human_approval_token_real_write_executor_contract(gate)

    assert (
        contract["contract_status"] == MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_LOCKED
    )
    assert contract["lock_reason"] == "invalid_token_write_final_gate"
    assert contract["write_final_gate_validation"]["valid"] is False
    assert contract["contract_validation"] == {"valid": True, "errors": []}


def test_missing_approval_token_record_preview_locks_contract():
    gate = _gate()
    gate.pop("approval_token_record_preview")

    contract = create_human_approval_token_real_write_executor_contract(gate)

    assert contract["lock_reason"] == "missing_approval_token_record_preview"
    assert contract["contract_validation"] == {"valid": True, "errors": []}


def test_missing_approval_audit_record_preview_locks_contract():
    gate = _gate()
    gate.pop("approval_audit_record_preview")

    contract = create_human_approval_token_real_write_executor_contract(gate)

    assert contract["lock_reason"] == "missing_approval_audit_record_preview"
    assert contract["contract_validation"] == {"valid": True, "errors": []}


def test_missing_token_target_paths_preview_locks_contract():
    gate = _gate()
    gate.pop("token_target_paths_preview")

    contract = create_human_approval_token_real_write_executor_contract(gate)

    assert contract["lock_reason"] == "missing_token_target_paths_preview"
    assert contract["contract_validation"] == {"valid": True, "errors": []}


def test_missing_proposal_record_preview_locks_contract():
    gate = _gate()
    gate.pop("proposal_record_preview")

    contract = create_human_approval_token_real_write_executor_contract(gate)

    assert contract["lock_reason"] == "missing_proposal_record_preview"
    assert contract["contract_validation"] == {"valid": True, "errors": []}


def test_missing_operation_ledger_preview_locks_contract():
    gate = _gate()
    gate.pop("operation_ledger_preview")

    contract = create_human_approval_token_real_write_executor_contract(gate)

    assert contract["lock_reason"] == "missing_operation_ledger_preview"
    assert contract["contract_validation"] == {"valid": True, "errors": []}


def test_missing_target_paths_preview_locks_contract():
    gate = _gate()
    gate.pop("target_paths_preview")

    contract = create_human_approval_token_real_write_executor_contract(gate)

    assert contract["lock_reason"] == "missing_target_paths_preview"
    assert contract["contract_validation"] == {"valid": True, "errors": []}


def test_missing_approval_token_write_payload_preview_locks_contract():
    gate = _gate()
    gate.pop("approval_token_write_payload_preview")

    contract = create_human_approval_token_real_write_executor_contract(gate)

    assert contract["lock_reason"] == "missing_approval_token_write_payload_preview"
    assert contract["contract_validation"] == {"valid": True, "errors": []}


def test_missing_approval_audit_write_payload_preview_locks_contract():
    gate = _gate()
    gate.pop("approval_audit_write_payload_preview")

    contract = create_human_approval_token_real_write_executor_contract(gate)

    assert contract["lock_reason"] == "missing_approval_audit_write_payload_preview"
    assert contract["contract_validation"] == {"valid": True, "errors": []}


def test_missing_token_write_target_paths_preview_locks_contract():
    gate = _gate()
    gate.pop("token_write_target_paths_preview")

    contract = create_human_approval_token_real_write_executor_contract(gate)

    assert contract["lock_reason"] == "missing_token_write_target_paths_preview"
    assert contract["contract_validation"] == {"valid": True, "errors": []}


def test_missing_final_gate_checklist_locks_contract():
    gate = _gate()
    gate.pop("final_gate_checklist")

    contract = create_human_approval_token_real_write_executor_contract(gate)

    assert contract["lock_reason"] == "missing_final_gate_checklist"
    assert contract["contract_validation"] == {"valid": True, "errors": []}


def test_missing_source_evidence_locks_contract():
    gate = _gate()
    gate["source_pattern_ids"] = []
    gate["source_fact_ids"] = []

    contract = create_human_approval_token_real_write_executor_contract(gate)

    assert contract["lock_reason"] == "missing_source_evidence"
    assert (
        contract["contract_status"] == MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_LOCKED
    )
    assert contract["contract_validation"] == {"valid": True, "errors": []}


def test_preview_integrity_failed_locks_contract():
    gate = _gate()
    gate["approval_token_record_preview"]["token_issued"] = True

    contract = create_human_approval_token_real_write_executor_contract(gate)

    assert contract["lock_reason"] == "preview_integrity_failed"
    assert (
        contract["contract_status"] == MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_LOCKED
    )
    assert contract["contract_validation"] == {"valid": True, "errors": []}


def test_final_gate_integrity_failed_locks_contract():
    gate = _gate()
    gate["final_gate_checklist"].remove("real_token_write_executor_required_but_not_invoked")

    contract = create_human_approval_token_real_write_executor_contract(gate)

    assert contract["lock_reason"] == "final_gate_integrity_failed"
    assert (
        contract["contract_status"] == MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_LOCKED
    )
    assert contract["contract_validation"] == {"valid": True, "errors": []}


def test_executor_contract_inputs_are_deterministic():
    contract_a = create_human_approval_token_real_write_executor_contract(_gate())
    contract_b = create_human_approval_token_real_write_executor_contract(_gate())

    assert contract_a["executor_contract_inputs"] == contract_b["executor_contract_inputs"]
    assert (
        contract_a["executor_contract_inputs"]["executor_boundary"]
        == "contract_only_no_executor_implementation_or_invocation"
    )


def test_executor_hard_lock_checks_are_deterministic():
    contract_a = create_human_approval_token_real_write_executor_contract(_gate())
    contract_b = create_human_approval_token_real_write_executor_contract(_gate())

    assert contract_a["executor_hard_lock_checks"] == contract_b["executor_hard_lock_checks"]
    assert "lock_if_any_forbidden_write_or_executor_flag_is_true" in contract_a[
        "executor_hard_lock_checks"
    ]


def test_executor_audit_fields_are_deterministic():
    contract_a = create_human_approval_token_real_write_executor_contract(_gate())
    contract_b = create_human_approval_token_real_write_executor_contract(_gate())

    assert contract_a["executor_audit_fields"] == contract_b["executor_audit_fields"]
    assert "contract_id" in contract_a["executor_audit_fields"]
    assert "source_write_final_gate_id" in contract_a["executor_audit_fields"]


def test_executor_rollback_rules_are_deterministic():
    contract_a = create_human_approval_token_real_write_executor_contract(_gate())
    contract_b = create_human_approval_token_real_write_executor_contract(_gate())

    assert contract_a["executor_rollback_rules"] == contract_b["executor_rollback_rules"]
    assert "no_rollback_action_in_v0_1_because_no_write_is_performed" in contract_a[
        "executor_rollback_rules"
    ]


def test_executor_forbidden_side_effects_are_deterministic_and_include_no_writes():
    contract_a = create_human_approval_token_real_write_executor_contract(_gate())
    contract_b = create_human_approval_token_real_write_executor_contract(_gate())

    assert contract_a["executor_forbidden_side_effects"] == contract_b[
        "executor_forbidden_side_effects"
    ]
    for forbidden in (
        "write_proposal_files",
        "write_operation_ledger",
        "write_token_files",
        "write_approval_audit_files",
        "invoke_real_token_write_executor",
        "implement_real_token_write_executor",
    ):
        assert forbidden in contract_a["executor_forbidden_side_effects"]


def test_input_write_final_gate_is_not_mutated():
    gate = _gate()
    before = deepcopy(gate)

    contract = create_human_approval_token_real_write_executor_contract(gate)
    contract["source_write_final_gate_snapshot"]["payload_preview"]["content"]["nested"][
        "value"
    ] = "changed"

    assert gate == before


def test_policy_proves_no_writes_and_no_real_executor_invocation_or_implementation(
    tmp_path,
    monkeypatch,
):
    hermes_home = tmp_path / "hermes-home"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    contract = create_human_approval_token_real_write_executor_contract(_gate())
    explanation = explain_human_approval_token_real_write_executor_contract(contract)
    recommendation = recommend_human_approval_token_real_write_executor_contract_action(contract)

    assert contract["policy"] == MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_POLICY
    assert contract["policy"]["read_only"] is True
    assert contract["policy"]["would_write_memory"] is False
    assert contract["policy"]["would_modify_config"] is False
    assert contract["policy"]["would_write_graph"] is False
    assert contract["policy"]["does_not_create_operation_events"] is True
    assert contract["policy"]["creates_real_write_executor_contract_candidates_only"] is True
    assert contract["policy"]["invokes_real_token_write_executor"] is False
    assert contract["policy"]["implements_real_token_write_executor"] is False
    assert contract["policy"]["issues_real_approval_tokens"] is False
    assert contract["policy"]["persists_approvals"] is False
    assert contract["policy"]["creates_real_proposals"] is False
    assert contract["policy"]["writes_proposal_files"] is False
    assert contract["policy"]["writes_operation_ledger"] is False
    assert contract["policy"]["writes_token_files"] is False
    assert contract["policy"]["writes_approval_audit"] is False
    assert contract["policy"]["applies_proposals"] is False
    assert contract["policy"]["submits_to_governance"] is False
    assert contract["policy"]["converts_to_real_proposal"] is False
    for forbidden_key in FORBIDDEN_TRUE_KEYS:
        assert explanation[forbidden_key] is False
    assert recommendation["invokes_real_token_write_executor"] is False
    assert recommendation["implements_real_token_write_executor"] is False
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


def test_contract_must_never_be_marked_as_written_issued_approved_persisted_or_converted():
    for forbidden_key in FORBIDDEN_TRUE_KEYS:
        contract = create_human_approval_token_real_write_executor_contract(_gate())
        contract[forbidden_key] = True

        validation = validate_human_approval_token_real_write_executor_contract(contract)

        assert validation["valid"] is False
        assert f"{forbidden_key}_must_be_false_or_absent" in validation["errors"]


def test_summary_counts_locked_contract_required_candidates_and_by_block_type_status():
    required_contract = create_human_approval_token_real_write_executor_contract(
        _gate(block_type="procedural_rules")
    )
    locked_contract = create_human_approval_token_real_write_executor_contract(
        _gate(block_type="preference", outcome="request_changes")
    )

    summary = summarize_human_approval_token_real_write_executor_contracts(
        [required_contract, locked_contract]
    )

    assert summary["total"] == 2
    assert summary["valid_count"] == 2
    assert summary["invalid_count"] == 0
    assert summary["real_token_write_executor_contract_required_count"] == 1
    assert summary["locked_count"] == 1
    assert summary["by_block_type"] == {"preference": 1, "procedural_rules": 1}
    assert summary["by_status"] == {
        "locked": 1,
        "real_token_write_executor_contract_required": 1,
    }
