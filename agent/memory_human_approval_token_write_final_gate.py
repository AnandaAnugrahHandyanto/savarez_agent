from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from agent.memory_human_approval_token_write_execution_dry_run import (
    MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_EXECUTION_DRY_RUN_FINAL_PREFLIGHT_REQUIRED,
    MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_EXECUTION_DRY_RUN_LOCKED,
    explain_human_approval_token_write_execution_dry_run,
    recommend_human_approval_token_write_execution_dry_run_action,
    validate_human_approval_token_write_execution_dry_run,
)
from agent.memory_read_only_candidate_utils import (
    build_stable_digest,
    deep_copy_mapping,
    summarize_candidates,
    validate_forbidden_true_keys_false_or_absent,
    validate_policy_flags,
)


MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_FINAL_GATE_VERSION = "0.1"
MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_FINAL_GATE_KIND = (
    "memory_human_approval_token_write_final_gate_candidate"
)
MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_FINAL_GATE_ELIGIBLE = (
    "eligible_for_real_token_write_executor"
)
MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_FINAL_GATE_LOCKED = "locked"
MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_FINAL_GATE_ROUTING = (
    "real_token_write_executor_required_but_not_invoked"
)
MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_FINAL_GATE_POLICY = {
    "read_only": True,
    "would_write_memory": False,
    "would_modify_config": False,
    "would_write_graph": False,
    "does_not_create_operation_events": True,
    "creates_token_write_final_gate_candidates_only": True,
    "invokes_real_token_write_executor": False,
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

_DEFAULT_OPERATOR = "hermes_memory_human_approval_token_write_final_gate_v0.1"
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
_FINAL_PREFLIGHT_PREVIEW_FIELDS = (
    "approval_token_write_payload_preview",
    "approval_audit_write_payload_preview",
    "token_write_target_paths_preview",
)
_LOCK_REASONS = {
    None,
    "token_write_execution_dry_run_locked",
    "invalid_token_write_execution_dry_run",
    "missing_approval_token_record_preview",
    "missing_approval_audit_record_preview",
    "missing_token_target_paths_preview",
    "missing_proposal_record_preview",
    "missing_operation_ledger_preview",
    "missing_target_paths_preview",
    "missing_approval_token_write_payload_preview",
    "missing_approval_audit_write_payload_preview",
    "missing_token_write_target_paths_preview",
    "missing_source_evidence",
    "missing_final_token_write_preflight_checklist",
    "preview_integrity_failed",
    "final_preflight_integrity_failed",
    "final_confirmation_requested_changes",
    "final_confirmation_rejected",
    "final_confirmation_deferred",
    "invalid_final_confirmation_review_outcome",
}


def create_human_approval_token_write_final_gate(
    write_execution_dry_run: Mapping[str, Any],
    operator: str | None = None,
) -> dict[str, Any]:
    """Create a deterministic read-only token write final gate candidate."""
    source = deepcopy(dict(write_execution_dry_run))
    write_execution_dry_run_validation = validate_human_approval_token_write_execution_dry_run(
        source
    )
    lock_reason = _gate_lock_reason(source, write_execution_dry_run_validation)
    gate_status = (
        MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_FINAL_GATE_ELIGIBLE
        if lock_reason is None
        else MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_FINAL_GATE_LOCKED
    )

    gate = {
        "gate_id": None,
        "gate_kind": MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_FINAL_GATE_KIND,
        "gate_status": gate_status,
        "routing": MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_FINAL_GATE_ROUTING,
        "lock_reason": lock_reason,
        "source_write_execution_dry_run_id": source.get("dry_run_id"),
        "source_write_execution_plan_id": source.get("source_write_execution_plan_id"),
        "source_final_confirmation_review_outcome_id": source.get(
            "source_final_confirmation_review_outcome_id"
        ),
        "source_final_confirmation_request_id": source.get("source_final_confirmation_request_id"),
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
        "operator": operator if operator is not None else _DEFAULT_OPERATOR,
        "outcome": source.get("outcome"),
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
        "final_gate_checklist": _final_gate_checklist(),
        "write_execution_dry_run_validation": deepcopy(write_execution_dry_run_validation),
        "gate_validation": {"valid": False, "errors": ["not_validated"]},
        "next_step_recommendation": {},
        "source_write_execution_dry_run_snapshot": deepcopy(source),
        "policy": dict(MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_FINAL_GATE_POLICY),
    }
    gate["gate_id"] = _gate_id(gate)
    gate["gate_validation"] = validate_human_approval_token_write_final_gate(gate)
    gate["next_step_recommendation"] = recommend_human_approval_token_write_final_gate_action(gate)
    return gate


def validate_human_approval_token_write_final_gate(gate: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    policy = _as_dict(gate.get("policy"))
    source_snapshot = _as_dict(gate.get("source_write_execution_dry_run_snapshot"))
    dry_run_validation = _as_dict(gate.get("write_execution_dry_run_validation"))
    expected_dry_run_validation = validate_human_approval_token_write_execution_dry_run(
        source_snapshot
    )
    expected_lock_reason = _gate_lock_reason(source_snapshot, dry_run_validation)

    for key in _REQUIRED_GATE_KEYS:
        if key not in gate:
            errors.append(f"missing_{key}")
    if gate.get("gate_kind") != MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_FINAL_GATE_KIND:
        errors.append("gate_kind_must_be_memory_human_approval_token_write_final_gate_candidate")
    if gate.get("gate_status") not in {
        MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_FINAL_GATE_ELIGIBLE,
        MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_FINAL_GATE_LOCKED,
    }:
        errors.append("gate_status_must_be_supported")
    if gate.get("routing") != MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_FINAL_GATE_ROUTING:
        errors.append("routing_must_require_real_token_write_executor_but_not_invoke_it")
    if gate.get("lock_reason") not in _LOCK_REASONS:
        errors.append("lock_reason_must_be_supported")
    if gate.get("lock_reason") != expected_lock_reason:
        errors.append("lock_reason_must_match_token_write_final_gate_checks")
    if (
        expected_lock_reason is None
        and gate.get("gate_status") != MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_FINAL_GATE_ELIGIBLE
    ):
        errors.append("valid_token_write_execution_dry_run_must_be_executor_eligible")
    if (
        expected_lock_reason is not None
        and gate.get("gate_status") != MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_FINAL_GATE_LOCKED
    ):
        errors.append("invalid_or_locked_token_write_execution_dry_run_must_lock_gate")
    if not isinstance(gate.get("operator"), str) or not gate.get("operator"):
        errors.append("operator_must_be_non_empty_string")
    if dry_run_validation != expected_dry_run_validation:
        errors.append(
            "write_execution_dry_run_validation_must_match_source_write_execution_dry_run_snapshot"
        )
    if gate.get("source_write_execution_dry_run_id") != source_snapshot.get("dry_run_id"):
        errors.append("source_write_execution_dry_run_id_must_match_source_snapshot")
    for source_key in _SOURCE_KEYS:
        if gate.get(source_key) != source_snapshot.get(source_key):
            errors.append(f"{source_key}_must_match_source_snapshot")
    if not isinstance(gate.get("payload_preview"), Mapping):
        errors.append("missing_payload_preview")
    if not isinstance(gate.get("source_pattern_ids"), list):
        errors.append("source_pattern_ids_must_be_list")
    if not isinstance(gate.get("source_fact_ids"), list):
        errors.append("source_fact_ids_must_be_list")
    if isinstance(gate.get("source_pattern_ids"), list) and isinstance(
        gate.get("source_fact_ids"), list
    ):
        if (
            not gate.get("source_pattern_ids")
            and not gate.get("source_fact_ids")
            and gate.get("lock_reason") != "missing_source_evidence"
        ):
            errors.append("missing_source_evidence")
    for field in _PREVIEW_FIELDS:
        if (
            not isinstance(gate.get(field), Mapping)
            and gate.get("lock_reason") != f"missing_{field}"
        ):
            errors.append(f"missing_{field}")
    for field in _FINAL_PREFLIGHT_PREVIEW_FIELDS:
        if (
            not isinstance(gate.get(field), Mapping)
            and gate.get("lock_reason") != f"missing_{field}"
        ):
            errors.append(f"missing_{field}")
    if (
        not isinstance(gate.get("final_token_write_preflight_checklist"), list)
        and gate.get("lock_reason") != "missing_final_token_write_preflight_checklist"
    ):
        errors.append("missing_final_token_write_preflight_checklist")
    if gate.get("lock_reason") != "preview_integrity_failed":
        errors.extend(_preview_integrity_errors(gate))
    if gate.get("lock_reason") != "final_preflight_integrity_failed":
        errors.extend(_final_preflight_integrity_errors(gate))
    if gate.get("final_gate_checklist") != _final_gate_checklist():
        errors.append("final_gate_checklist_must_match_v0_1_deterministic_checks")
    for field in _PREVIEW_FIELDS + _FINAL_PREFLIGHT_PREVIEW_FIELDS + (
        "payload_preview",
        "final_token_write_preflight_checklist",
    ):
        if field in gate and field in source_snapshot and gate.get(field) != source_snapshot.get(field):
            errors.append(f"{field}_must_match_source_write_execution_dry_run_snapshot")
    if gate.get("source_pattern_ids") != list(source_snapshot.get("source_pattern_ids", []) or []):
        errors.append("source_pattern_ids_must_match_source_write_execution_dry_run_snapshot")
    if gate.get("source_fact_ids") != list(source_snapshot.get("source_fact_ids", []) or []):
        errors.append("source_fact_ids_must_match_source_write_execution_dry_run_snapshot")
    if gate.get("token_write_execution_steps") != list(
        source_snapshot.get("token_write_execution_steps", []) or []
    ):
        errors.append("token_write_execution_steps_must_match_source_write_execution_dry_run_snapshot")
    if gate.get("token_write_execution_preflight_checks") != list(
        source_snapshot.get("token_write_execution_preflight_checks", []) or []
    ):
        errors.append(
            "token_write_execution_preflight_checks_must_match_source_write_execution_dry_run_snapshot"
        )
    errors.extend(validate_forbidden_true_keys_false_or_absent(gate, _FORBIDDEN_TRUE_KEYS))
    errors.extend(
        validate_policy_flags(policy, MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_FINAL_GATE_POLICY)
    )

    return {"valid": not errors, "errors": _dedupe(errors)}


def explain_human_approval_token_write_final_gate(gate: Mapping[str, Any]) -> dict[str, Any]:
    validation = validate_human_approval_token_write_final_gate(gate)
    source_snapshot = _as_dict(gate.get("source_write_execution_dry_run_snapshot"))
    return {
        "gate_id": gate.get("gate_id"),
        "gate_kind": gate.get("gate_kind"),
        "gate_status": gate.get("gate_status"),
        "routing": gate.get("routing"),
        "lock_reason": gate.get("lock_reason"),
        "source_write_execution_dry_run_id": gate.get("source_write_execution_dry_run_id"),
        "source_write_execution_plan_id": gate.get("source_write_execution_plan_id"),
        "source_final_confirmation_review_outcome_id": gate.get(
            "source_final_confirmation_review_outcome_id"
        ),
        "block_id": gate.get("block_id"),
        "block_type": gate.get("block_type"),
        "project_scope": gate.get("project_scope"),
        "operator": gate.get("operator"),
        "outcome": gate.get("outcome"),
        "source_pattern_count": len(gate.get("source_pattern_ids", []) or []),
        "source_fact_count": len(gate.get("source_fact_ids", []) or []),
        "token_write_execution_step_count": len(
            gate.get("token_write_execution_steps", []) or []
        ),
        "token_write_execution_preflight_check_count": len(
            gate.get("token_write_execution_preflight_checks", []) or []
        ),
        "final_token_write_preflight_checklist": deepcopy(
            gate.get("final_token_write_preflight_checklist")
        ),
        "final_gate_checklist": deepcopy(gate.get("final_gate_checklist")),
        "validation": validation,
        "write_execution_dry_run_explanation": (
            explain_human_approval_token_write_execution_dry_run(source_snapshot)
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
        "policy": dict(MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_FINAL_GATE_POLICY),
    }


def recommend_human_approval_token_write_final_gate_action(
    gate: Mapping[str, Any],
) -> dict[str, Any]:
    validation = validate_human_approval_token_write_final_gate(gate)
    source_snapshot = _as_dict(gate.get("source_write_execution_dry_run_snapshot"))
    if (
        validation["valid"]
        and gate.get("gate_status") == MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_FINAL_GATE_ELIGIBLE
    ):
        action = "route_to_real_token_write_executor_without_invoking_it"
        reason = "Token write final gate candidate is eligible for a separate real token write executor; this gate does not invoke that executor or write tokens."
    elif validation["valid"]:
        action = "keep_token_write_final_gate_locked"
        reason = f"Token write final gate candidate is locked by {gate.get('lock_reason')}."
    else:
        action = "repair_token_write_final_gate_candidate"
        reason = "Token write final gate candidate failed validation and cannot proceed."
    return {
        "action": action,
        "reason": reason,
        "routing": MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_FINAL_GATE_ROUTING,
        "validation": validation,
        "write_execution_dry_run_recommendation": (
            recommend_human_approval_token_write_execution_dry_run_action(source_snapshot)
            if source_snapshot
            else {}
        ),
        "creates_token_write_final_gate_candidates_only": True,
        "invokes_real_token_write_executor": False,
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
        "policy": dict(MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_FINAL_GATE_POLICY),
    }


def summarize_human_approval_token_write_final_gates(
    gates: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
) -> dict[str, Any]:
    candidate_summary = summarize_candidates(gates, "gate_status")
    lock_reason_summary = summarize_candidates(gates, "lock_reason")
    eligible_count = 0
    locked_count = 0
    valid_count = 0
    invalid_count = 0
    for gate in gates:
        if gate.get("gate_status") == MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_FINAL_GATE_ELIGIBLE:
            eligible_count += 1
        if gate.get("gate_status") == MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_FINAL_GATE_LOCKED:
            locked_count += 1
        validation = validate_human_approval_token_write_final_gate(gate)
        if validation["valid"]:
            valid_count += 1
        else:
            invalid_count += 1
    return {
        "total": len(gates),
        "valid_count": valid_count,
        "invalid_count": invalid_count,
        "eligible_for_real_token_write_executor_count": eligible_count,
        "locked_count": locked_count,
        "by_block_type": candidate_summary["by_block_type"],
        "by_status": candidate_summary["by_status"],
        "by_lock_reason": lock_reason_summary["by_status"],
        "policy": dict(MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_FINAL_GATE_POLICY),
    }


_SOURCE_KEYS = (
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
    "outcome",
)

_REQUIRED_GATE_KEYS = (
    "gate_id",
    "gate_kind",
    "gate_status",
    "routing",
    "lock_reason",
    "source_write_execution_dry_run_id",
) + _SOURCE_KEYS + (
    "operator",
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
    "write_execution_dry_run_validation",
    "gate_validation",
    "next_step_recommendation",
    "source_write_execution_dry_run_snapshot",
    "policy",
)


def _gate_lock_reason(
    dry_run: Mapping[str, Any],
    dry_run_validation: Mapping[str, Any],
) -> str | None:
    if dry_run.get("dry_run_status") == MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_EXECUTION_DRY_RUN_LOCKED:
        return dry_run.get("lock_reason") or "token_write_execution_dry_run_locked"
    for field in _PREVIEW_FIELDS:
        if not isinstance(dry_run.get(field), Mapping):
            return f"missing_{field}"
    for field in _FINAL_PREFLIGHT_PREVIEW_FIELDS:
        if not isinstance(dry_run.get(field), Mapping):
            return f"missing_{field}"
    if not (dry_run.get("source_pattern_ids") or dry_run.get("source_fact_ids")):
        return "missing_source_evidence"
    if not isinstance(dry_run.get("final_token_write_preflight_checklist"), list):
        return "missing_final_token_write_preflight_checklist"
    if _preview_integrity_errors(dry_run):
        return "preview_integrity_failed"
    if _final_preflight_integrity_errors(dry_run):
        return "final_preflight_integrity_failed"
    if dry_run_validation.get("valid") is not True:
        return "invalid_token_write_execution_dry_run"
    if (
        dry_run.get("dry_run_status")
        != MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_EXECUTION_DRY_RUN_FINAL_PREFLIGHT_REQUIRED
    ):
        return "invalid_token_write_execution_dry_run"
    return None


def _final_gate_checklist() -> list[str]:
    return [
        "source_write_execution_dry_run_is_valid_and_final_preflight_required",
        "approval_token_record_preview_is_preview_only",
        "approval_audit_record_preview_is_preview_only",
        "token_target_paths_preview_is_preview_only",
        "proposal_record_preview_is_not_written",
        "operation_ledger_preview_is_not_written",
        "target_paths_preview_is_preview_only",
        "source_evidence_is_present",
        "approval_token_write_payload_preview_is_preview_only",
        "approval_audit_write_payload_preview_is_preview_only",
        "token_write_target_paths_preview_is_preview_only",
        "final_token_write_preflight_checklist_is_present",
        "no_real_approval_token_issued",
        "no_approval_persisted",
        "no_real_proposal_created",
        "no_operation_ledger_event_created",
        "no_proposal_file_written",
        "no_operation_ledger_written",
        "no_token_file_written",
        "no_approval_audit_written",
        "no_memory_or_graph_or_config_write",
        "real_token_write_executor_required_but_not_invoked",
    ]


def _preview_integrity_errors(container: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in _PREVIEW_FIELDS:
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


def _final_preflight_integrity_errors(container: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in _FINAL_PREFLIGHT_PREVIEW_FIELDS:
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
    checklist = container.get("final_token_write_preflight_checklist")
    if isinstance(checklist, list) and "no_real_approval_token_issued" not in checklist:
        errors.append("final_token_write_preflight_checklist_must_preserve_no_token_write_checks")
    return errors


def _gate_id(gate: Mapping[str, Any]) -> str:
    identity = {
        "version": MEMORY_HUMAN_APPROVAL_TOKEN_WRITE_FINAL_GATE_VERSION,
        "gate_kind": gate.get("gate_kind"),
        "gate_status": gate.get("gate_status"),
        "routing": gate.get("routing"),
        "lock_reason": gate.get("lock_reason"),
        "source_write_execution_dry_run_id": gate.get("source_write_execution_dry_run_id"),
        "source_write_execution_plan_id": gate.get("source_write_execution_plan_id"),
        "source_final_confirmation_review_outcome_id": gate.get(
            "source_final_confirmation_review_outcome_id"
        ),
        "source_final_confirmation_request_id": gate.get("source_final_confirmation_request_id"),
        "source_token_write_lock_gate_id": gate.get("source_token_write_lock_gate_id"),
        "source_token_issuance_dry_run_id": gate.get("source_token_issuance_dry_run_id"),
        "source_token_issuance_plan_id": gate.get("source_token_issuance_plan_id"),
        "source_review_outcome_id": gate.get("source_review_outcome_id"),
        "source_request_id": gate.get("source_request_id"),
        "source_gate_id": gate.get("source_gate_id"),
        "source_dry_run_id": gate.get("source_dry_run_id"),
        "source_plan_id": gate.get("source_plan_id"),
        "source_outcome_id": gate.get("source_outcome_id"),
        "source_packet_id": gate.get("source_packet_id"),
        "source_submission_id": gate.get("source_submission_id"),
        "source_draft_id": gate.get("source_draft_id"),
        "source_decision_id": gate.get("source_decision_id"),
        "source_queue_item_id": gate.get("source_queue_item_id"),
        "block_id": gate.get("block_id"),
        "block_type": gate.get("block_type"),
        "project_scope": gate.get("project_scope"),
        "operator": gate.get("operator"),
        "outcome": gate.get("outcome"),
        "approval_token_record_preview": gate.get("approval_token_record_preview", {}),
        "approval_audit_record_preview": gate.get("approval_audit_record_preview", {}),
        "token_target_paths_preview": gate.get("token_target_paths_preview", {}),
        "proposal_record_preview": gate.get("proposal_record_preview", {}),
        "operation_ledger_preview": gate.get("operation_ledger_preview", {}),
        "target_paths_preview": gate.get("target_paths_preview", {}),
        "payload_preview": gate.get("payload_preview"),
        "source_pattern_ids": list(gate.get("source_pattern_ids", [])),
        "source_fact_ids": list(gate.get("source_fact_ids", [])),
        "token_write_execution_steps": list(gate.get("token_write_execution_steps", [])),
        "token_write_execution_preflight_checks": list(
            gate.get("token_write_execution_preflight_checks", [])
        ),
        "approval_token_write_payload_preview": gate.get(
            "approval_token_write_payload_preview", {}
        ),
        "approval_audit_write_payload_preview": gate.get(
            "approval_audit_write_payload_preview", {}
        ),
        "token_write_target_paths_preview": gate.get("token_write_target_paths_preview", {}),
        "final_token_write_preflight_checklist": list(
            gate.get("final_token_write_preflight_checklist") or []
        ),
        "final_gate_checklist": list(gate.get("final_gate_checklist", [])),
        "write_execution_dry_run_validation": gate.get("write_execution_dry_run_validation", {}),
        "policy": gate.get("policy", {}),
    }
    return build_stable_digest("memory-human-approval-token-write-final-gate:v0.1", identity)


def _as_dict(value: Any) -> dict[str, Any]:
    return deep_copy_mapping(value)


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
