from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from agent.memory_human_approval_token_real_write_executor_contract import (
    MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_LOCKED,
    MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_REQUIRED,
    explain_human_approval_token_real_write_executor_contract,
    recommend_human_approval_token_real_write_executor_contract_action,
    validate_human_approval_token_real_write_executor_contract,
)
from agent.memory_read_only_candidate_utils import (
    build_stable_digest,
    deep_copy_mapping,
    summarize_candidates,
    validate_forbidden_true_keys_false_or_absent,
    validate_policy_flags,
)


MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_REVIEW_GATE_VERSION = "0.1"
MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_REVIEW_OUTCOME_KIND = (
    "memory_human_approval_token_real_write_executor_contract_review_outcome_candidate"
)
MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_REVIEW_OUTCOME_STATUS = (
    "real_write_executor_contract_review_outcome_candidate"
)
MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_REVIEW_ROUTING = (
    "real_token_write_executor_implementation_plan_required_after_contract_approval"
)
MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_REVIEW_SUPPORTED_OUTCOMES = {
    "approve_executor_contract",
    "request_contract_changes",
    "reject_contract",
    "defer_contract_review",
}
MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_REVIEW_POLICY = {
    "read_only": True,
    "would_write_memory": False,
    "would_modify_config": False,
    "would_write_graph": False,
    "does_not_create_operation_events": True,
    "creates_real_write_executor_contract_review_outcomes_only": True,
    "invokes_real_token_write_executor": False,
    "implements_real_token_write_executor": False,
    "issues_real_approval_tokens": False,
    "persists_approvals": False,
    "creates_real_proposals": False,
    "writes_proposal_files": False,
    "writes_operation_ledger": False,
    "writes_token_files": False,
    "writes_approval_audit": False,
    "applies_proposals": False,
    "submits_to_governance": False,
    "converts_to_real_proposal": False,
}

_DEFAULT_REVIEWER = (
    "hermes_memory_human_approval_token_real_write_executor_contract_review_gate_v0.1"
)
_FORBIDDEN_TRUE_KEYS = (
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
_PREVIEW_FIELDS = (
    "approval_token_record_preview",
    "approval_audit_record_preview",
    "token_target_paths_preview",
    "proposal_record_preview",
    "operation_ledger_preview",
    "target_paths_preview",
)
_WRITE_PREVIEW_FIELDS = (
    "approval_token_write_payload_preview",
    "approval_audit_write_payload_preview",
    "token_write_target_paths_preview",
)
_EXECUTOR_CONTRACT_FIELD_TYPES = {
    "executor_contract_inputs": Mapping,
    "executor_hard_lock_checks": list,
    "executor_audit_fields": list,
    "executor_rollback_rules": list,
    "executor_forbidden_side_effects": list,
    "executor_contract_checklist": list,
}
_SOURCE_KEYS = (
    "source_write_final_gate_id",
    "source_write_execution_dry_run_id",
    "source_write_execution_plan_id",
    "source_final_confirmation_review_outcome_id",
    "source_final_confirmation_request_id",
    "source_token_write_lock_gate_id",
    "source_token_issuance_dry_run_id",
    "source_token_issuance_plan_id",
    "source_review_outcome_id",
    "source_request_id",
    "source_gate_id",
    "source_dry_run_id",
    "source_plan_id",
    "source_outcome_id",
    "source_packet_id",
    "source_submission_id",
    "source_draft_id",
    "source_decision_id",
    "source_queue_item_id",
    "block_id",
    "block_type",
    "project_scope",
)
_REQUIRED_OUTCOME_KEYS = (
    "review_outcome_id",
    "review_outcome_kind",
    "review_outcome_status",
    "routing",
    "source_contract_id",
) + _SOURCE_KEYS + (
    "reviewer",
    "outcome",
    "rationale",
    "approval_token_record_preview",
    "approval_audit_record_preview",
    "token_target_paths_preview",
    "proposal_record_preview",
    "operation_ledger_preview",
    "target_paths_preview",
    "payload_preview",
    "source_pattern_ids",
    "source_fact_ids",
    "token_write_execution_steps",
    "token_write_execution_preflight_checks",
    "approval_token_write_payload_preview",
    "approval_audit_write_payload_preview",
    "token_write_target_paths_preview",
    "final_token_write_preflight_checklist",
    "final_gate_checklist",
    "executor_contract_inputs",
    "executor_hard_lock_checks",
    "executor_audit_fields",
    "executor_rollback_rules",
    "executor_forbidden_side_effects",
    "executor_contract_checklist",
    "contract_review_checklist",
    "contract_validation",
    "review_outcome_validation",
    "next_step_recommendation",
    "source_contract_snapshot",
    "policy",
)


def create_human_approval_token_real_write_executor_contract_review_outcome(
    contract: Mapping[str, Any],
    reviewer: str | None = None,
    outcome: str | None = None,
    rationale: str | None = None,
) -> dict[str, Any]:
    """Create a deterministic read-only real write executor contract review outcome."""
    source = deepcopy(dict(contract))
    contract_validation = validate_human_approval_token_real_write_executor_contract(source)
    evaluation = evaluate_human_approval_token_real_write_executor_contract(
        source,
        reviewer=reviewer,
    )
    selected_outcome = outcome if outcome is not None else evaluation["outcome"]
    selected_rationale = (
        rationale
        if rationale is not None
        else _outcome_rationale(
            selected_outcome,
            source,
            contract_validation,
            explicit=outcome is not None,
        )
    )

    outcome_candidate = {
        "review_outcome_id": None,
        "review_outcome_kind": (
            MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_REVIEW_OUTCOME_KIND
        ),
        "review_outcome_status": (
            MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_REVIEW_OUTCOME_STATUS
        ),
        "routing": MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_REVIEW_ROUTING,
        "source_contract_id": source.get("contract_id"),
        "source_write_final_gate_id": source.get("source_write_final_gate_id"),
        "source_write_execution_dry_run_id": source.get("source_write_execution_dry_run_id"),
        "source_write_execution_plan_id": source.get("source_write_execution_plan_id"),
        "source_final_confirmation_review_outcome_id": source.get(
            "source_final_confirmation_review_outcome_id"
        ),
        "source_final_confirmation_request_id": source.get(
            "source_final_confirmation_request_id"
        ),
        "source_token_write_lock_gate_id": source.get("source_token_write_lock_gate_id"),
        "source_token_issuance_dry_run_id": source.get("source_token_issuance_dry_run_id"),
        "source_token_issuance_plan_id": source.get("source_token_issuance_plan_id"),
        "source_review_outcome_id": source.get("source_review_outcome_id"),
        "source_request_id": source.get("source_request_id"),
        "source_gate_id": source.get("source_gate_id"),
        "source_dry_run_id": source.get("source_dry_run_id"),
        "source_plan_id": source.get("source_plan_id"),
        "source_outcome_id": source.get("source_outcome_id"),
        "source_packet_id": source.get("source_packet_id"),
        "source_submission_id": source.get("source_submission_id"),
        "source_draft_id": source.get("source_draft_id"),
        "source_decision_id": source.get("source_decision_id"),
        "source_queue_item_id": source.get("source_queue_item_id"),
        "block_id": source.get("block_id"),
        "block_type": source.get("block_type"),
        "project_scope": source.get("project_scope"),
        "reviewer": reviewer if reviewer is not None else _DEFAULT_REVIEWER,
        "outcome": selected_outcome,
        "rationale": selected_rationale,
        "approval_token_record_preview": deepcopy(source.get("approval_token_record_preview")),
        "approval_audit_record_preview": deepcopy(source.get("approval_audit_record_preview")),
        "token_target_paths_preview": deepcopy(source.get("token_target_paths_preview")),
        "proposal_record_preview": deepcopy(source.get("proposal_record_preview")),
        "operation_ledger_preview": deepcopy(source.get("operation_ledger_preview")),
        "target_paths_preview": deepcopy(source.get("target_paths_preview")),
        "payload_preview": deepcopy(source.get("payload_preview")),
        "source_pattern_ids": deepcopy(list(source.get("source_pattern_ids", []) or [])),
        "source_fact_ids": deepcopy(list(source.get("source_fact_ids", []) or [])),
        "token_write_execution_steps": deepcopy(
            list(source.get("token_write_execution_steps", []) or [])
        ),
        "token_write_execution_preflight_checks": deepcopy(
            list(source.get("token_write_execution_preflight_checks", []) or [])
        ),
        "approval_token_write_payload_preview": deepcopy(
            source.get("approval_token_write_payload_preview")
        ),
        "approval_audit_write_payload_preview": deepcopy(
            source.get("approval_audit_write_payload_preview")
        ),
        "token_write_target_paths_preview": deepcopy(source.get("token_write_target_paths_preview")),
        "final_token_write_preflight_checklist": deepcopy(
            source.get("final_token_write_preflight_checklist")
        ),
        "final_gate_checklist": deepcopy(source.get("final_gate_checklist")),
        "executor_contract_inputs": deepcopy(source.get("executor_contract_inputs")),
        "executor_hard_lock_checks": deepcopy(source.get("executor_hard_lock_checks")),
        "executor_audit_fields": deepcopy(source.get("executor_audit_fields")),
        "executor_rollback_rules": deepcopy(source.get("executor_rollback_rules")),
        "executor_forbidden_side_effects": deepcopy(
            source.get("executor_forbidden_side_effects")
        ),
        "executor_contract_checklist": deepcopy(source.get("executor_contract_checklist")),
        "contract_review_checklist": _contract_review_checklist(),
        "contract_validation": deepcopy(contract_validation),
        "review_outcome_validation": {"valid": False, "errors": ["not_validated"]},
        "next_step_recommendation": {},
        "source_contract_snapshot": deepcopy(source),
        "policy": dict(MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_REVIEW_POLICY),
    }
    outcome_candidate["review_outcome_id"] = _review_outcome_id(outcome_candidate)
    outcome_candidate["review_outcome_validation"] = (
        validate_human_approval_token_real_write_executor_contract_review_outcome(
            outcome_candidate
        )
    )
    outcome_candidate["next_step_recommendation"] = (
        recommend_human_approval_token_real_write_executor_contract_review_action(
            outcome_candidate
        )
    )
    return outcome_candidate


def evaluate_human_approval_token_real_write_executor_contract(
    contract: Mapping[str, Any],
    reviewer: str | None = None,
) -> dict[str, Any]:
    validation = validate_human_approval_token_real_write_executor_contract(contract)
    outcome, rationale = _evaluated_outcome(contract, validation)
    return {
        "reviewer": reviewer if reviewer is not None else _DEFAULT_REVIEWER,
        "outcome": outcome,
        "rationale": rationale,
        "validation": validation,
        "contract_explanation": explain_human_approval_token_real_write_executor_contract(
            contract
        ),
        "contract_recommendation": (
            recommend_human_approval_token_real_write_executor_contract_action(contract)
        ),
        "routing": MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_REVIEW_ROUTING,
        "policy": dict(MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_REVIEW_POLICY),
    }


def validate_human_approval_token_real_write_executor_contract_review_outcome(
    outcome_candidate: Mapping[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    policy = _as_dict(outcome_candidate.get("policy"))
    source_snapshot = _as_dict(outcome_candidate.get("source_contract_snapshot"))
    expected_contract_validation = validate_human_approval_token_real_write_executor_contract(
        source_snapshot
    )

    for key in _REQUIRED_OUTCOME_KEYS:
        if key not in outcome_candidate:
            errors.append(f"missing_{key}")
    if (
        outcome_candidate.get("review_outcome_kind")
        != MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_REVIEW_OUTCOME_KIND
    ):
        errors.append(
            "review_outcome_kind_must_be_memory_human_approval_token_real_write_executor_contract_review_outcome_candidate"
        )
    if (
        outcome_candidate.get("review_outcome_status")
        != MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_REVIEW_OUTCOME_STATUS
    ):
        errors.append("review_outcome_status_must_be_real_write_executor_contract_review_outcome_candidate")
    if (
        outcome_candidate.get("routing")
        != MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_REVIEW_ROUTING
    ):
        errors.append("routing_must_require_implementation_plan_after_contract_approval")
    if (
        outcome_candidate.get("outcome")
        not in MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_REVIEW_SUPPORTED_OUTCOMES
    ):
        errors.append("outcome_must_be_supported")
    if not isinstance(outcome_candidate.get("reviewer"), str) or not outcome_candidate.get(
        "reviewer"
    ):
        errors.append("reviewer_must_be_non_empty_string")
    if not isinstance(outcome_candidate.get("rationale"), str) or not outcome_candidate.get(
        "rationale"
    ):
        errors.append("rationale_must_be_non_empty_string")
    if outcome_candidate.get("contract_validation") != expected_contract_validation:
        errors.append("contract_validation_must_match_source_contract_snapshot")
    if outcome_candidate.get("source_contract_id") != source_snapshot.get("contract_id"):
        errors.append("source_contract_id_must_match_source_snapshot")
    for source_key in _SOURCE_KEYS:
        if outcome_candidate.get(source_key) != source_snapshot.get(source_key):
            errors.append(f"{source_key}_must_match_source_snapshot")
    for field in _PREVIEW_FIELDS + _WRITE_PREVIEW_FIELDS + (
        "payload_preview",
        "final_token_write_preflight_checklist",
        "final_gate_checklist",
        "executor_contract_inputs",
        "executor_hard_lock_checks",
        "executor_audit_fields",
        "executor_rollback_rules",
        "executor_forbidden_side_effects",
        "executor_contract_checklist",
    ):
        if (
            field in outcome_candidate
            and field in source_snapshot
            and outcome_candidate.get(field) != source_snapshot.get(field)
        ):
            errors.append(f"{field}_must_match_source_contract_snapshot")
    if not isinstance(outcome_candidate.get("source_pattern_ids"), list):
        errors.append("source_pattern_ids_must_be_list")
    if not isinstance(outcome_candidate.get("source_fact_ids"), list):
        errors.append("source_fact_ids_must_be_list")
    if outcome_candidate.get("source_pattern_ids") != list(
        source_snapshot.get("source_pattern_ids", []) or []
    ):
        errors.append("source_pattern_ids_must_match_source_contract_snapshot")
    if outcome_candidate.get("source_fact_ids") != list(
        source_snapshot.get("source_fact_ids", []) or []
    ):
        errors.append("source_fact_ids_must_match_source_contract_snapshot")
    if outcome_candidate.get("token_write_execution_steps") != list(
        source_snapshot.get("token_write_execution_steps", []) or []
    ):
        errors.append("token_write_execution_steps_must_match_source_contract_snapshot")
    if outcome_candidate.get("token_write_execution_preflight_checks") != list(
        source_snapshot.get("token_write_execution_preflight_checks", []) or []
    ):
        errors.append(
            "token_write_execution_preflight_checks_must_match_source_contract_snapshot"
        )
    if outcome_candidate.get("contract_review_checklist") != _contract_review_checklist():
        errors.append("contract_review_checklist_must_match_v0_1_deterministic_checks")
    errors.extend(
        validate_forbidden_true_keys_false_or_absent(
            outcome_candidate,
            _FORBIDDEN_TRUE_KEYS,
        )
    )
    errors.extend(
        validate_policy_flags(
            policy,
            MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_REVIEW_POLICY,
        )
    )

    return {"valid": not errors, "errors": _dedupe(errors)}


def explain_human_approval_token_real_write_executor_contract_review_outcome(
    outcome_candidate: Mapping[str, Any],
) -> dict[str, Any]:
    validation = validate_human_approval_token_real_write_executor_contract_review_outcome(
        outcome_candidate
    )
    source_snapshot = _as_dict(outcome_candidate.get("source_contract_snapshot"))
    return {
        "review_outcome_id": outcome_candidate.get("review_outcome_id"),
        "review_outcome_kind": outcome_candidate.get("review_outcome_kind"),
        "review_outcome_status": outcome_candidate.get("review_outcome_status"),
        "routing": outcome_candidate.get("routing"),
        "source_contract_id": outcome_candidate.get("source_contract_id"),
        "source_write_final_gate_id": outcome_candidate.get("source_write_final_gate_id"),
        "source_write_execution_dry_run_id": outcome_candidate.get(
            "source_write_execution_dry_run_id"
        ),
        "source_write_execution_plan_id": outcome_candidate.get(
            "source_write_execution_plan_id"
        ),
        "source_final_confirmation_review_outcome_id": outcome_candidate.get(
            "source_final_confirmation_review_outcome_id"
        ),
        "block_id": outcome_candidate.get("block_id"),
        "block_type": outcome_candidate.get("block_type"),
        "project_scope": outcome_candidate.get("project_scope"),
        "reviewer": outcome_candidate.get("reviewer"),
        "outcome": outcome_candidate.get("outcome"),
        "rationale": outcome_candidate.get("rationale"),
        "source_pattern_count": len(outcome_candidate.get("source_pattern_ids", []) or []),
        "source_fact_count": len(outcome_candidate.get("source_fact_ids", []) or []),
        "contract_review_checklist": deepcopy(
            outcome_candidate.get("contract_review_checklist")
        ),
        "validation": validation,
        "contract_explanation": (
            explain_human_approval_token_real_write_executor_contract(source_snapshot)
            if source_snapshot
            else {}
        ),
        "token_issued": False,
        "approved": False,
        "persisted": False,
        "submitted": False,
        "written": False,
        "created_real_proposal": False,
        "created_operation_event": False,
        "writes_proposal_files": False,
        "writes_operation_ledger": False,
        "writes_token_files": False,
        "writes_approval_audit": False,
        "converted_to_real_proposal": False,
        "invokes_real_token_write_executor": False,
        "implements_real_token_write_executor": False,
        "policy": dict(MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_REVIEW_POLICY),
    }


def recommend_human_approval_token_real_write_executor_contract_review_action(
    outcome_candidate: Mapping[str, Any],
) -> dict[str, Any]:
    validation = validate_human_approval_token_real_write_executor_contract_review_outcome(
        outcome_candidate
    )
    source_snapshot = _as_dict(outcome_candidate.get("source_contract_snapshot"))
    outcome = outcome_candidate.get("outcome")
    if not validation["valid"]:
        action = "do_not_use_real_write_executor_contract_review_outcome_candidate"
        reason = "Real write executor contract review outcome candidate failed validation."
    elif outcome == "approve_executor_contract":
        action = "route_to_real_token_write_executor_implementation_plan_without_executor_invocation"
        reason = "Contract review approves a later implementation plan; this review gate does not implement, invoke, issue, persist, submit, or write anything."
    elif outcome == "request_contract_changes":
        action = "request_real_write_executor_contract_changes"
        reason = "Contract review found remediable preview, source evidence, or contract integrity gaps."
    elif outcome == "reject_contract":
        action = "reject_real_write_executor_contract"
        reason = "Contract review rejected the executor contract candidate."
    else:
        action = "defer_real_write_executor_contract_review"
        reason = "Contract review reached an unknown or deferred condition; no implementation plan may proceed."
    return {
        "action": action,
        "reason": reason,
        "routing": MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_REVIEW_ROUTING,
        "validation": validation,
        "contract_recommendation": (
            recommend_human_approval_token_real_write_executor_contract_action(source_snapshot)
            if source_snapshot
            else {}
        ),
        "creates_real_write_executor_contract_review_outcomes_only": True,
        "invokes_real_token_write_executor": False,
        "implements_real_token_write_executor": False,
        "issues_real_approval_tokens": False,
        "persists_approvals": False,
        "creates_real_proposals": False,
        "writes_proposal_files": False,
        "writes_operation_ledger": False,
        "writes_token_files": False,
        "writes_approval_audit": False,
        "applies_proposals": False,
        "submits_to_governance": False,
        "converts_to_real_proposal": False,
        "policy": dict(MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_REVIEW_POLICY),
    }


def summarize_human_approval_token_real_write_executor_contract_review_outcomes(
    outcomes: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
) -> dict[str, Any]:
    candidate_summary = summarize_candidates(
        outcomes,
        "review_outcome_status",
        type_key="outcome",
    )
    valid_count = 0
    invalid_count = 0
    for outcome_candidate in outcomes:
        validation = validate_human_approval_token_real_write_executor_contract_review_outcome(
            outcome_candidate
        )
        if validation["valid"]:
            valid_count += 1
        else:
            invalid_count += 1
    return {
        "total": candidate_summary["total"],
        "valid_count": valid_count,
        "invalid_count": invalid_count,
        "by_block_type": candidate_summary["by_block_type"],
        "by_status": candidate_summary["by_status"],
        "by_outcome": candidate_summary["by_type"],
        "policy": dict(MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_REVIEW_POLICY),
    }


def _evaluated_outcome(
    contract: Mapping[str, Any],
    validation: Mapping[str, Any],
) -> tuple[str, str]:
    if contract.get("contract_status") == MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_LOCKED:
        return "reject_contract", "Real write executor contract candidate is locked."
    for field in _PREVIEW_FIELDS:
        if not isinstance(contract.get(field), Mapping):
            return "request_contract_changes", f"Contract is missing {field}."
    for field in _WRITE_PREVIEW_FIELDS:
        if not isinstance(contract.get(field), Mapping):
            return "request_contract_changes", f"Contract is missing {field}."
    if not isinstance(contract.get("final_gate_checklist"), list):
        return "request_contract_changes", "Contract is missing final_gate_checklist."
    for field, expected_type in _EXECUTOR_CONTRACT_FIELD_TYPES.items():
        if not isinstance(contract.get(field), expected_type):
            return "request_contract_changes", f"Contract is missing {field}."
    if not (contract.get("source_pattern_ids") or contract.get("source_fact_ids")):
        return "request_contract_changes", "Contract is missing source evidence."
    if _preview_integrity_errors(contract):
        return "request_contract_changes", "Contract preview integrity failed."
    if _contract_integrity_errors(contract, validation):
        return "request_contract_changes", "Real write executor contract integrity failed."
    if validation.get("valid") is not True:
        return "reject_contract", "Real write executor contract candidate is invalid."
    if (
        contract.get("contract_status")
        == MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_REQUIRED
    ):
        return (
            "approve_executor_contract",
            "Real write executor contract is valid, required, and intact for a later implementation plan.",
        )
    return "defer_contract_review", "Contract review reached an unknown condition."


def _outcome_rationale(
    outcome: str,
    contract: Mapping[str, Any],
    contract_validation: Mapping[str, Any],
    explicit: bool = False,
) -> str:
    if (
        explicit
        and outcome
        in MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_REVIEW_SUPPORTED_OUTCOMES
    ):
        return "Explicit supported real write executor contract review outcome override recorded as a read-only candidate only."
    evaluated_outcome, evaluated_rationale = _evaluated_outcome(contract, contract_validation)
    if outcome == evaluated_outcome:
        return evaluated_rationale
    if outcome == "approve_executor_contract":
        return "Contract review approves a later implementation plan without issuing, persisting, writing, implementing, invoking, or submitting anything."
    if outcome == "request_contract_changes":
        return "Contract review requests changes before any later implementation plan."
    if outcome == "reject_contract":
        return "Contract review rejects the executor contract candidate."
    if outcome == "defer_contract_review":
        return "Contract review is deferred until the unknown condition is resolved."
    return "Real write executor contract review outcome is unsupported by v0.1."


def _contract_review_checklist() -> list[str]:
    return [
        "source_contract_validation_is_recomputed_read_only",
        "source_contract_status_is_real_token_write_executor_contract_required",
        "approval_token_record_preview_is_present_and_preview_only",
        "approval_audit_record_preview_is_present_and_preview_only",
        "token_target_paths_preview_is_present_and_preview_only",
        "proposal_record_preview_is_present_and_not_written",
        "operation_ledger_preview_is_present_and_not_written",
        "target_paths_preview_is_present_and_preview_only",
        "approval_token_write_payload_preview_is_present_and_preview_only",
        "approval_audit_write_payload_preview_is_present_and_preview_only",
        "token_write_target_paths_preview_is_present_and_preview_only",
        "final_gate_checklist_is_present_and_preserves_no_write_controls",
        "executor_contract_inputs_are_present",
        "executor_hard_lock_checks_are_present",
        "executor_audit_fields_are_present",
        "executor_rollback_rules_are_present",
        "executor_forbidden_side_effects_are_present",
        "executor_contract_checklist_is_present",
        "source_evidence_is_present",
        "no_real_approval_token_issued",
        "no_approval_persisted",
        "no_real_proposal_created",
        "no_operation_ledger_event_created",
        "no_proposal_file_written",
        "no_operation_ledger_written",
        "no_token_file_written",
        "no_approval_audit_written",
        "no_memory_or_graph_or_config_write",
        "real_token_write_executor_not_implemented",
        "real_token_write_executor_not_invoked",
        "contract_review_outcome_only",
    ]


def _preview_integrity_errors(container: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in _PREVIEW_FIELDS + _WRITE_PREVIEW_FIELDS:
        preview = container.get(field)
        if not isinstance(preview, Mapping):
            continue
        if preview.get("preview_only") is not True:
            errors.append(f"{field}_must_be_preview_only")
        for key, value in preview.items():
            if value is True and (
                key in _FORBIDDEN_TRUE_KEYS
                or key in {"created", "written", "token_issued", "approved", "persisted"}
                or "created" in key
                or "written" in key
                or key.startswith("writes_")
            ):
                errors.append(f"{field}_{key}_must_not_be_true")
    return errors


def _contract_integrity_errors(
    contract: Mapping[str, Any],
    validation: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []
    final_gate_checklist = contract.get("final_gate_checklist")
    if isinstance(final_gate_checklist, list):
        required_final_gate_checks = {
            "no_real_approval_token_issued",
            "no_approval_persisted",
            "no_real_proposal_created",
            "no_operation_ledger_event_created",
            "no_token_file_written",
            "no_approval_audit_written",
            "real_token_write_executor_required_but_not_invoked",
        }
        if required_final_gate_checks.difference(final_gate_checklist):
            errors.append("final_gate_checklist_must_preserve_no_write_and_no_executor_checks")
    final_preflight = contract.get("final_token_write_preflight_checklist")
    if isinstance(final_preflight, list) and "no_real_approval_token_issued" not in final_preflight:
        errors.append("final_token_write_preflight_checklist_must_preserve_no_token_write_checks")
    forbidden_side_effects = contract.get("executor_forbidden_side_effects")
    if isinstance(forbidden_side_effects, list):
        required_side_effects = {
            "write_memory",
            "write_memory_graph",
            "write_proposal_files",
            "write_operation_ledger",
            "issue_real_approval_tokens",
            "write_token_files",
            "write_approval_audit_files",
            "persist_approvals",
            "invoke_real_token_write_executor",
            "implement_real_token_write_executor",
            "submit_to_governance",
            "convert_to_real_proposal",
        }
        if required_side_effects.difference(forbidden_side_effects):
            errors.append("executor_forbidden_side_effects_must_preserve_no_write_boundary")
    contract_checklist = contract.get("executor_contract_checklist")
    if isinstance(contract_checklist, list):
        required_contract_checks = {
            "contract_is_read_only_candidate_only",
            "no_real_executor_is_invoked",
            "no_real_executor_is_implemented",
            "no_memory_or_graph_or_config_write",
        }
        if required_contract_checks.difference(contract_checklist):
            errors.append("executor_contract_checklist_must_preserve_no_executor_boundary")
    for error in list(validation.get("errors", []) or []):
        if (
            "_must_match_v0_1_deterministic_contract" in error
            or "_must_match_source_write_final_gate_snapshot" in error
            or error == "lock_reason_must_match_real_write_executor_contract_checks"
            or error.startswith("final_gate_checklist_must_preserve")
            or error.startswith("final_token_write_preflight_checklist_must_preserve")
        ):
            errors.append("contract_validation_integrity_errors")
    return _dedupe(errors)


def _review_outcome_id(outcome_candidate: Mapping[str, Any]) -> str:
    identity = {
        "version": MEMORY_HUMAN_APPROVAL_TOKEN_REAL_WRITE_EXECUTOR_CONTRACT_REVIEW_GATE_VERSION,
        "review_outcome_kind": outcome_candidate.get("review_outcome_kind"),
        "review_outcome_status": outcome_candidate.get("review_outcome_status"),
        "routing": outcome_candidate.get("routing"),
        "source_contract_id": outcome_candidate.get("source_contract_id"),
        "source_write_final_gate_id": outcome_candidate.get("source_write_final_gate_id"),
        "source_write_execution_dry_run_id": outcome_candidate.get(
            "source_write_execution_dry_run_id"
        ),
        "source_write_execution_plan_id": outcome_candidate.get(
            "source_write_execution_plan_id"
        ),
        "source_final_confirmation_review_outcome_id": outcome_candidate.get(
            "source_final_confirmation_review_outcome_id"
        ),
        "source_final_confirmation_request_id": outcome_candidate.get(
            "source_final_confirmation_request_id"
        ),
        "source_token_write_lock_gate_id": outcome_candidate.get(
            "source_token_write_lock_gate_id"
        ),
        "source_token_issuance_dry_run_id": outcome_candidate.get(
            "source_token_issuance_dry_run_id"
        ),
        "source_token_issuance_plan_id": outcome_candidate.get(
            "source_token_issuance_plan_id"
        ),
        "source_review_outcome_id": outcome_candidate.get("source_review_outcome_id"),
        "source_request_id": outcome_candidate.get("source_request_id"),
        "source_gate_id": outcome_candidate.get("source_gate_id"),
        "source_dry_run_id": outcome_candidate.get("source_dry_run_id"),
        "source_plan_id": outcome_candidate.get("source_plan_id"),
        "source_outcome_id": outcome_candidate.get("source_outcome_id"),
        "source_packet_id": outcome_candidate.get("source_packet_id"),
        "source_submission_id": outcome_candidate.get("source_submission_id"),
        "source_draft_id": outcome_candidate.get("source_draft_id"),
        "source_decision_id": outcome_candidate.get("source_decision_id"),
        "source_queue_item_id": outcome_candidate.get("source_queue_item_id"),
        "block_id": outcome_candidate.get("block_id"),
        "block_type": outcome_candidate.get("block_type"),
        "project_scope": outcome_candidate.get("project_scope"),
        "reviewer": outcome_candidate.get("reviewer"),
        "outcome": outcome_candidate.get("outcome"),
        "rationale": outcome_candidate.get("rationale"),
        "approval_token_record_preview": outcome_candidate.get(
            "approval_token_record_preview", {}
        ),
        "approval_audit_record_preview": outcome_candidate.get(
            "approval_audit_record_preview", {}
        ),
        "token_target_paths_preview": outcome_candidate.get("token_target_paths_preview", {}),
        "proposal_record_preview": outcome_candidate.get("proposal_record_preview", {}),
        "operation_ledger_preview": outcome_candidate.get("operation_ledger_preview", {}),
        "target_paths_preview": outcome_candidate.get("target_paths_preview", {}),
        "payload_preview": outcome_candidate.get("payload_preview"),
        "source_pattern_ids": list(outcome_candidate.get("source_pattern_ids", [])),
        "source_fact_ids": list(outcome_candidate.get("source_fact_ids", [])),
        "token_write_execution_steps": list(
            outcome_candidate.get("token_write_execution_steps", [])
        ),
        "token_write_execution_preflight_checks": list(
            outcome_candidate.get("token_write_execution_preflight_checks", [])
        ),
        "approval_token_write_payload_preview": outcome_candidate.get(
            "approval_token_write_payload_preview", {}
        ),
        "approval_audit_write_payload_preview": outcome_candidate.get(
            "approval_audit_write_payload_preview", {}
        ),
        "token_write_target_paths_preview": outcome_candidate.get(
            "token_write_target_paths_preview", {}
        ),
        "final_token_write_preflight_checklist": list(
            outcome_candidate.get("final_token_write_preflight_checklist") or []
        ),
        "final_gate_checklist": list(outcome_candidate.get("final_gate_checklist") or []),
        "executor_contract_inputs": outcome_candidate.get("executor_contract_inputs", {}),
        "executor_hard_lock_checks": list(
            outcome_candidate.get("executor_hard_lock_checks") or []
        ),
        "executor_audit_fields": list(outcome_candidate.get("executor_audit_fields") or []),
        "executor_rollback_rules": list(
            outcome_candidate.get("executor_rollback_rules") or []
        ),
        "executor_forbidden_side_effects": list(
            outcome_candidate.get("executor_forbidden_side_effects") or []
        ),
        "executor_contract_checklist": list(
            outcome_candidate.get("executor_contract_checklist") or []
        ),
        "contract_review_checklist": list(
            outcome_candidate.get("contract_review_checklist") or []
        ),
        "contract_validation": outcome_candidate.get("contract_validation", {}),
        "policy": outcome_candidate.get("policy", {}),
    }
    return build_stable_digest(
        "memory-human-approval-token-real-write-executor-contract-review-outcome:v0.1",
        identity,
    )


def _as_dict(value: Any) -> dict[str, Any]:
    return deep_copy_mapping(value)


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
