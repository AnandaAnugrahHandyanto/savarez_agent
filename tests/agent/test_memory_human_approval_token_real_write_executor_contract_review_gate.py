from copy import deepcopy

from agent.memory_human_approval_token_real_write_executor_contract import (
    create_human_approval_token_real_write_executor_contract,
)
from agent.memory_human_approval_token_real_write_executor_contract_review_gate import (
    MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_REVIEW_OUTCOME_KIND,
    MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_REVIEW_OUTCOME_STATUS,
    MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_REVIEW_POLICY,
    MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_REVIEW_ROUTING,
    create_human_approval_token_real_write_executor_contract_review_outcome,
    evaluate_human_approval_token_real_write_executor_contract,
    explain_human_approval_token_real_write_executor_contract_review_outcome,
    recommend_human_approval_token_real_write_executor_contract_review_action,
    summarize_human_approval_token_real_write_executor_contract_review_outcomes,
    validate_human_approval_token_real_write_executor_contract_review_outcome,
)
from tests.agent.test_memory_human_approval_token_real_write_executor_contract import _gate


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


def _contract(outcome=None, block_type="procedural_rules"):
    return create_human_approval_token_real_write_executor_contract(
        _gate(outcome=outcome, block_type=block_type),
        operator="real-write-executor-contract-operator",
    )


def test_valid_contract_creates_approve_executor_contract_review_outcome_candidate():
    contract = _contract()

    outcome = create_human_approval_token_real_write_executor_contract_review_outcome(
        contract,
        reviewer="contract-reviewer",
    )

    assert (
        outcome["review_outcome_kind"]
        == MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_REVIEW_OUTCOME_KIND
    )
    assert (
        outcome["review_outcome_status"]
        == MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_REVIEW_OUTCOME_STATUS
    )
    assert outcome["routing"] == MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_REVIEW_ROUTING
    assert outcome["source_contract_id"] == contract["contract_id"]
    assert outcome["source_write_final_gate_id"] == contract["source_write_final_gate_id"]
    assert outcome["source_write_execution_dry_run_id"] == contract[
        "source_write_execution_dry_run_id"
    ]
    assert outcome["source_write_execution_plan_id"] == contract[
        "source_write_execution_plan_id"
    ]
    assert outcome["source_final_confirmation_review_outcome_id"] == contract[
        "source_final_confirmation_review_outcome_id"
    ]
    assert outcome["source_final_confirmation_request_id"] == contract[
        "source_final_confirmation_request_id"
    ]
    assert outcome["source_token_write_lock_gate_id"] == contract[
        "source_token_write_lock_gate_id"
    ]
    assert outcome["source_token_issuance_dry_run_id"] == contract[
        "source_token_issuance_dry_run_id"
    ]
    assert outcome["source_token_issuance_plan_id"] == contract[
        "source_token_issuance_plan_id"
    ]
    assert outcome["source_review_outcome_id"] == contract["source_review_outcome_id"]
    assert outcome["source_request_id"] == contract["source_request_id"]
    assert outcome["source_gate_id"] == contract["source_gate_id"]
    assert outcome["source_dry_run_id"] == contract["source_dry_run_id"]
    assert outcome["source_plan_id"] == contract["source_plan_id"]
    assert outcome["source_outcome_id"] == contract["source_outcome_id"]
    assert outcome["source_packet_id"] == contract["source_packet_id"]
    assert outcome["source_submission_id"] == contract["source_submission_id"]
    assert outcome["source_draft_id"] == contract["source_draft_id"]
    assert outcome["source_decision_id"] == contract["source_decision_id"]
    assert outcome["source_queue_item_id"] == contract["source_queue_item_id"]
    assert outcome["reviewer"] == "contract-reviewer"
    assert outcome["outcome"] == "approve_executor_contract"
    assert outcome["contract_validation"] == {"valid": True, "errors": []}
    assert outcome["review_outcome_validation"] == {"valid": True, "errors": []}
    assert validate_human_approval_token_real_write_executor_contract_review_outcome(
        outcome
    ) == {"valid": True, "errors": []}
    assert outcome["next_step_recommendation"]["action"] == (
        "route_to_real_token_write_executor_implementation_plan_without_executor_invocation"
    )
    assert outcome["next_step_recommendation"]["invokes_real_token_write_executor"] is False
    assert outcome["next_step_recommendation"]["implements_real_token_write_executor"] is False
    assert outcome["next_step_recommendation"]["issues_real_approval_tokens"] is False
    assert outcome["next_step_recommendation"]["persists_approvals"] is False
    assert outcome["next_step_recommendation"]["writes_token_files"] is False
    assert outcome["next_step_recommendation"]["writes_approval_audit"] is False


def test_review_outcome_id_is_canonical_for_valid_contract_review_outcome():
    outcome = create_human_approval_token_real_write_executor_contract_review_outcome(
        _contract(),
        reviewer="contract-reviewer",
    )

    assert outcome["review_outcome_id"] == (
        "memory-human-approval-token-real-write-executor-contract-review-outcome:"
        "v0.1:62341452751cc123"
    )
    assert (
        create_human_approval_token_real_write_executor_contract_review_outcome(
            _contract(),
            reviewer="contract-reviewer",
        )["review_outcome_id"]
        == outcome["review_outcome_id"]
    )


def test_locked_contract_rejects():
    contract = _contract(outcome="request_changes")

    outcome = create_human_approval_token_real_write_executor_contract_review_outcome(contract)

    assert contract["contract_status"] == "locked"
    assert outcome["outcome"] == "reject_contract"
    assert outcome["review_outcome_validation"] == {"valid": True, "errors": []}


def test_invalid_contract_rejects():
    contract = _contract()
    contract["contract_kind"] = "wrong"

    outcome = create_human_approval_token_real_write_executor_contract_review_outcome(contract)

    assert outcome["outcome"] == "reject_contract"
    assert outcome["contract_validation"]["valid"] is False
    assert outcome["review_outcome_validation"] == {"valid": True, "errors": []}
    assert evaluate_human_approval_token_real_write_executor_contract(contract)["outcome"] == (
        "reject_contract"
    )


def test_missing_approval_token_record_preview_requests_changes():
    contract = _contract()
    contract.pop("approval_token_record_preview")

    outcome = create_human_approval_token_real_write_executor_contract_review_outcome(contract)

    assert outcome["outcome"] == "request_contract_changes"


def test_missing_approval_audit_record_preview_requests_changes():
    contract = _contract()
    contract.pop("approval_audit_record_preview")

    outcome = create_human_approval_token_real_write_executor_contract_review_outcome(contract)

    assert outcome["outcome"] == "request_contract_changes"


def test_missing_token_target_paths_preview_requests_changes():
    contract = _contract()
    contract.pop("token_target_paths_preview")

    outcome = create_human_approval_token_real_write_executor_contract_review_outcome(contract)

    assert outcome["outcome"] == "request_contract_changes"


def test_missing_proposal_record_preview_requests_changes():
    contract = _contract()
    contract.pop("proposal_record_preview")

    outcome = create_human_approval_token_real_write_executor_contract_review_outcome(contract)

    assert outcome["outcome"] == "request_contract_changes"


def test_missing_operation_ledger_preview_requests_changes():
    contract = _contract()
    contract.pop("operation_ledger_preview")

    outcome = create_human_approval_token_real_write_executor_contract_review_outcome(contract)

    assert outcome["outcome"] == "request_contract_changes"


def test_missing_target_paths_preview_requests_changes():
    contract = _contract()
    contract.pop("target_paths_preview")

    outcome = create_human_approval_token_real_write_executor_contract_review_outcome(contract)

    assert outcome["outcome"] == "request_contract_changes"


def test_missing_approval_token_write_payload_preview_requests_changes():
    contract = _contract()
    contract.pop("approval_token_write_payload_preview")

    outcome = create_human_approval_token_real_write_executor_contract_review_outcome(contract)

    assert outcome["outcome"] == "request_contract_changes"


def test_missing_approval_audit_write_payload_preview_requests_changes():
    contract = _contract()
    contract.pop("approval_audit_write_payload_preview")

    outcome = create_human_approval_token_real_write_executor_contract_review_outcome(contract)

    assert outcome["outcome"] == "request_contract_changes"


def test_missing_token_write_target_paths_preview_requests_changes():
    contract = _contract()
    contract.pop("token_write_target_paths_preview")

    outcome = create_human_approval_token_real_write_executor_contract_review_outcome(contract)

    assert outcome["outcome"] == "request_contract_changes"


def test_missing_final_gate_checklist_requests_changes():
    contract = _contract()
    contract.pop("final_gate_checklist")

    outcome = create_human_approval_token_real_write_executor_contract_review_outcome(contract)

    assert outcome["outcome"] == "request_contract_changes"


def test_missing_executor_contract_inputs_requests_changes():
    contract = _contract()
    contract.pop("executor_contract_inputs")

    outcome = create_human_approval_token_real_write_executor_contract_review_outcome(contract)

    assert outcome["outcome"] == "request_contract_changes"


def test_missing_executor_hard_lock_checks_requests_changes():
    contract = _contract()
    contract.pop("executor_hard_lock_checks")

    outcome = create_human_approval_token_real_write_executor_contract_review_outcome(contract)

    assert outcome["outcome"] == "request_contract_changes"


def test_missing_executor_audit_fields_requests_changes():
    contract = _contract()
    contract.pop("executor_audit_fields")

    outcome = create_human_approval_token_real_write_executor_contract_review_outcome(contract)

    assert outcome["outcome"] == "request_contract_changes"


def test_missing_executor_rollback_rules_requests_changes():
    contract = _contract()
    contract.pop("executor_rollback_rules")

    outcome = create_human_approval_token_real_write_executor_contract_review_outcome(contract)

    assert outcome["outcome"] == "request_contract_changes"


def test_missing_executor_forbidden_side_effects_requests_changes():
    contract = _contract()
    contract.pop("executor_forbidden_side_effects")

    outcome = create_human_approval_token_real_write_executor_contract_review_outcome(contract)

    assert outcome["outcome"] == "request_contract_changes"


def test_missing_executor_contract_checklist_requests_changes():
    contract = _contract()
    contract.pop("executor_contract_checklist")

    outcome = create_human_approval_token_real_write_executor_contract_review_outcome(contract)

    assert outcome["outcome"] == "request_contract_changes"


def test_missing_source_evidence_requests_changes():
    contract = _contract()
    contract["source_pattern_ids"] = []
    contract["source_fact_ids"] = []

    outcome = create_human_approval_token_real_write_executor_contract_review_outcome(contract)

    assert outcome["outcome"] == "request_contract_changes"


def test_preview_integrity_failed_requests_changes():
    contract = _contract()
    contract["approval_token_record_preview"]["token_issued"] = True

    outcome = create_human_approval_token_real_write_executor_contract_review_outcome(contract)

    assert outcome["outcome"] == "request_contract_changes"


def test_contract_integrity_failed_requests_changes():
    contract = _contract()
    contract["executor_contract_checklist"].remove("no_real_executor_is_invoked")

    outcome = create_human_approval_token_real_write_executor_contract_review_outcome(contract)

    assert outcome["outcome"] == "request_contract_changes"
    assert outcome["contract_validation"]["valid"] is False


def test_explicit_supported_outcome_override_is_accepted_but_not_written_or_invoked():
    contract = _contract()

    outcome = create_human_approval_token_real_write_executor_contract_review_outcome(
        contract,
        reviewer="contract-reviewer",
        outcome="defer_contract_review",
        rationale="Manual reviewer chose to defer.",
    )
    explanation = explain_human_approval_token_real_write_executor_contract_review_outcome(
        outcome
    )
    recommendation = recommend_human_approval_token_real_write_executor_contract_review_action(
        outcome
    )

    assert outcome["outcome"] == "defer_contract_review"
    assert outcome["rationale"] == "Manual reviewer chose to defer."
    assert outcome["review_outcome_validation"] == {"valid": True, "errors": []}
    for forbidden_key in FORBIDDEN_TRUE_KEYS:
        assert explanation[forbidden_key] is False
    assert recommendation["issues_real_approval_tokens"] is False
    assert recommendation["persists_approvals"] is False
    assert recommendation["creates_real_proposals"] is False
    assert recommendation["writes_proposal_files"] is False
    assert recommendation["writes_operation_ledger"] is False
    assert recommendation["writes_token_files"] is False
    assert recommendation["writes_approval_audit"] is False
    assert recommendation["invokes_real_token_write_executor"] is False
    assert recommendation["implements_real_token_write_executor"] is False
    assert recommendation["applies_proposals"] is False
    assert recommendation["submits_to_governance"] is False


def test_unsupported_outcome_fails_validation():
    outcome = create_human_approval_token_real_write_executor_contract_review_outcome(
        _contract(),
        outcome="approve_and_execute",
    )

    validation = validate_human_approval_token_real_write_executor_contract_review_outcome(
        outcome
    )

    assert validation["valid"] is False
    assert "outcome_must_be_supported" in validation["errors"]
    assert outcome["next_step_recommendation"]["action"] == (
        "do_not_use_real_write_executor_contract_review_outcome_candidate"
    )


def test_contract_review_checklist_is_deterministic():
    outcome_a = create_human_approval_token_real_write_executor_contract_review_outcome(
        _contract()
    )
    outcome_b = create_human_approval_token_real_write_executor_contract_review_outcome(
        _contract()
    )

    assert outcome_a["contract_review_checklist"] == outcome_b["contract_review_checklist"]
    assert "real_token_write_executor_not_invoked" in outcome_a["contract_review_checklist"]
    assert "contract_review_outcome_only" in outcome_a["contract_review_checklist"]


def test_input_contract_is_not_mutated():
    contract = _contract()
    before = deepcopy(contract)

    outcome = create_human_approval_token_real_write_executor_contract_review_outcome(contract)
    outcome["source_contract_snapshot"]["payload_preview"]["content"]["nested"][
        "value"
    ] = "changed"

    assert contract == before


def test_policy_proves_no_memory_config_graph_proposal_ledger_token_or_approval_writes_and_no_executor(
    tmp_path,
    monkeypatch,
):
    hermes_home = tmp_path / "hermes-home"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    outcome = create_human_approval_token_real_write_executor_contract_review_outcome(
        _contract()
    )
    explanation = explain_human_approval_token_real_write_executor_contract_review_outcome(
        outcome
    )
    recommendation = recommend_human_approval_token_real_write_executor_contract_review_action(
        outcome
    )

    assert outcome["policy"] == MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_REVIEW_POLICY
    assert outcome["policy"]["read_only"] is True
    assert outcome["policy"]["would_write_memory"] is False
    assert outcome["policy"]["would_modify_config"] is False
    assert outcome["policy"]["would_write_graph"] is False
    assert outcome["policy"]["does_not_create_operation_events"] is True
    assert outcome["policy"]["creates_real_write_executor_contract_review_outcomes_only"] is True
    assert outcome["policy"]["invokes_real_token_write_executor"] is False
    assert outcome["policy"]["implements_real_token_write_executor"] is False
    assert outcome["policy"]["issues_real_approval_tokens"] is False
    assert outcome["policy"]["persists_approvals"] is False
    assert outcome["policy"]["creates_real_proposals"] is False
    assert outcome["policy"]["writes_proposal_files"] is False
    assert outcome["policy"]["writes_operation_ledger"] is False
    assert outcome["policy"]["writes_token_files"] is False
    assert outcome["policy"]["writes_approval_audit"] is False
    assert outcome["policy"]["applies_proposals"] is False
    assert outcome["policy"]["submits_to_governance"] is False
    assert outcome["policy"]["converts_to_real_proposal"] is False
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


def test_outcome_candidate_must_never_be_marked_written_issued_approved_or_executor_invoked():
    outcome = create_human_approval_token_real_write_executor_contract_review_outcome(
        _contract()
    )

    for forbidden_key in FORBIDDEN_TRUE_KEYS:
        mutated = deepcopy(outcome)
        mutated[forbidden_key] = True

        validation = validate_human_approval_token_real_write_executor_contract_review_outcome(
            mutated
        )

        assert validation["valid"] is False
        assert f"{forbidden_key}_must_be_false_or_absent" in validation["errors"]


def test_summary_counts_by_outcome_block_type_and_status():
    outcomes = [
        create_human_approval_token_real_write_executor_contract_review_outcome(
            _contract(block_type="procedural_rules")
        ),
        create_human_approval_token_real_write_executor_contract_review_outcome(
            _contract(block_type="project_context")
        ),
        create_human_approval_token_real_write_executor_contract_review_outcome(
            _contract(block_type="procedural_rules", outcome="request_changes")
        ),
    ]

    summary = summarize_human_approval_token_real_write_executor_contract_review_outcomes(
        outcomes
    )

    assert summary["total"] == 3
    assert summary["valid_count"] == 3
    assert summary["invalid_count"] == 0
    assert summary["by_outcome"] == {"approve_executor_contract": 2, "reject_contract": 1}
    assert summary["by_block_type"] == {"procedural_rules": 2, "project_context": 1}
    assert summary["by_status"] == {
        "real_write_executor_contract_review_outcome_candidate": 3
    }
    assert summary["policy"] == MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_REVIEW_POLICY


def test_evaluate_exposes_same_deterministic_decision_without_creating_writes():
    evaluation = evaluate_human_approval_token_real_write_executor_contract(
        _contract(),
        reviewer="contract-reviewer",
    )

    assert evaluation["reviewer"] == "contract-reviewer"
    assert evaluation["outcome"] == "approve_executor_contract"
    assert evaluation["validation"] == {"valid": True, "errors": []}
    assert evaluation["policy"]["issues_real_approval_tokens"] is False
    assert evaluation["policy"]["writes_token_files"] is False
    assert evaluation["policy"]["invokes_real_token_write_executor"] is False
    assert evaluation["policy"]["implements_real_token_write_executor"] is False
