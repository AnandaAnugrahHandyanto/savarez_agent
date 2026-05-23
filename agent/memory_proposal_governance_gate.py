from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Mapping

from agent.memory_proposal_draft_builder import (
    explain_memory_proposal_draft,
    recommend_memory_proposal_draft_action,
    validate_memory_proposal_draft,
)


MEMORY_PROPOSAL_GOVERNANCE_GATE_VERSION = "0.1"
MEMORY_GOVERNANCE_SUBMISSION_KIND = "memory_block_write_governance_submission_candidate"
MEMORY_GOVERNANCE_SUBMISSION_STATUS = "governance_review_required"
MEMORY_GOVERNANCE_SUBMISSION_ROUTING = "manual_governed_proposal_creation_required"
MEMORY_PROPOSAL_GOVERNANCE_GATE_POLICY = {
    "read_only": True,
    "would_write_memory": False,
    "would_modify_config": False,
    "would_write_graph": False,
    "does_not_create_operation_events": True,
    "creates_submission_candidates_only": True,
    "creates_real_proposals": False,
    "applies_proposals": False,
    "persists_approvals": False,
    "submits_to_governance": False,
}


def create_governance_submission_candidate(proposal_draft: Mapping[str, Any], reviewer: str | None = None) -> dict[str, Any]:
    """Create a deterministic read-only governance submission candidate from a proposal draft."""
    draft = deepcopy(dict(proposal_draft))
    draft_validation = validate_memory_proposal_draft(draft)
    invalid_reasons = _submission_invalid_reasons(draft, draft_validation)

    candidate = {
        "submission_id": None,
        "submission_kind": MEMORY_GOVERNANCE_SUBMISSION_KIND,
        "submission_status": MEMORY_GOVERNANCE_SUBMISSION_STATUS,
        "routing": MEMORY_GOVERNANCE_SUBMISSION_ROUTING,
        "source_draft_id": draft.get("draft_id"),
        "source_decision_id": draft.get("source_decision_id"),
        "source_queue_item_id": draft.get("source_queue_item_id"),
        "block_id": draft.get("block_id"),
        "block_type": draft.get("block_type"),
        "project_scope": draft.get("project_scope"),
        "reviewer": reviewer if reviewer is not None else draft.get("author"),
        "payload_preview": deepcopy(draft.get("payload_preview")),
        "source_pattern_ids": deepcopy(list(draft.get("source_pattern_ids", []) or [])),
        "source_fact_ids": deepcopy(list(draft.get("source_fact_ids", []) or [])),
        "draft_validation": deepcopy(draft_validation),
        "submission_validation": {"valid": False, "errors": ["not_validated"]},
        "next_step_recommendation": {},
        "source_draft_snapshot": deepcopy(draft),
        "policy": dict(MEMORY_PROPOSAL_GOVERNANCE_GATE_POLICY),
    }
    candidate["submission_id"] = _submission_id(candidate)
    candidate["submission_validation"] = validate_governance_submission_candidate(candidate)
    if invalid_reasons:
        errors = list(candidate["submission_validation"]["errors"])
        for reason in invalid_reasons:
            if reason not in errors:
                errors.append(reason)
        candidate["submission_validation"] = {"valid": False, "errors": errors}
    candidate["next_step_recommendation"] = recommend_governance_submission_action(candidate)
    return candidate


def validate_governance_submission_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    policy = _as_dict(candidate.get("policy"))
    draft_validation = _as_dict(candidate.get("draft_validation"))
    source_snapshot = _as_dict(candidate.get("source_draft_snapshot"))

    for key in (
        "submission_id",
        "submission_kind",
        "submission_status",
        "routing",
        "source_draft_id",
        "source_decision_id",
        "source_queue_item_id",
        "block_id",
        "block_type",
        "project_scope",
        "reviewer",
        "payload_preview",
        "source_pattern_ids",
        "source_fact_ids",
        "draft_validation",
        "submission_validation",
        "next_step_recommendation",
        "source_draft_snapshot",
        "policy",
    ):
        if key not in candidate:
            errors.append(f"missing_{key}")
    if candidate.get("submission_kind") != MEMORY_GOVERNANCE_SUBMISSION_KIND:
        errors.append("submission_kind_must_be_memory_block_write_governance_submission_candidate")
    if candidate.get("submission_status") != MEMORY_GOVERNANCE_SUBMISSION_STATUS:
        errors.append("submission_status_must_be_governance_review_required")
    if candidate.get("routing") != MEMORY_GOVERNANCE_SUBMISSION_ROUTING:
        errors.append("routing_must_require_manual_governed_proposal_creation")
    if draft_validation.get("valid") is not True:
        errors.append("invalid_proposal_draft")
    if source_snapshot.get("proposal_status") != "draft_review_required":
        errors.append("source_proposal_status_must_be_draft_review_required")
    if not isinstance(candidate.get("payload_preview"), Mapping):
        errors.append("missing_payload_preview")
    if not isinstance(candidate.get("source_pattern_ids"), list):
        errors.append("source_pattern_ids_must_be_list")
    if not isinstance(candidate.get("source_fact_ids"), list):
        errors.append("source_fact_ids_must_be_list")
    if isinstance(candidate.get("source_pattern_ids"), list) and isinstance(candidate.get("source_fact_ids"), list):
        if not candidate.get("source_pattern_ids") and not candidate.get("source_fact_ids"):
            errors.append("missing_source_evidence")
    for forbidden_key in (
        "submitted",
        "applied",
        "persisted",
        "approved",
        "created_real_proposal",
        "created_operation_event",
    ):
        if candidate.get(forbidden_key) is True:
            errors.append(f"{forbidden_key}_must_be_false_or_absent")
    for key, expected in MEMORY_PROPOSAL_GOVERNANCE_GATE_POLICY.items():
        if policy.get(key) is not expected:
            errors.append(f"policy_{key}_must_be_{str(expected).lower()}")

    return {"valid": not errors, "errors": errors}


def explain_governance_submission_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    validation = validate_governance_submission_candidate(candidate)
    source_snapshot = _as_dict(candidate.get("source_draft_snapshot"))
    return {
        "submission_id": candidate.get("submission_id"),
        "submission_kind": candidate.get("submission_kind"),
        "submission_status": candidate.get("submission_status"),
        "routing": candidate.get("routing"),
        "source_draft_id": candidate.get("source_draft_id"),
        "source_decision_id": candidate.get("source_decision_id"),
        "source_queue_item_id": candidate.get("source_queue_item_id"),
        "block_id": candidate.get("block_id"),
        "block_type": candidate.get("block_type"),
        "project_scope": candidate.get("project_scope"),
        "reviewer": candidate.get("reviewer"),
        "source_pattern_count": len(candidate.get("source_pattern_ids", []) or []),
        "source_fact_count": len(candidate.get("source_fact_ids", []) or []),
        "validation": validation,
        "draft_explanation": explain_memory_proposal_draft(source_snapshot) if source_snapshot else {},
        "submitted": False,
        "applied": False,
        "persisted": False,
        "approved": False,
        "created_real_proposal": False,
        "created_operation_event": False,
        "policy": dict(MEMORY_PROPOSAL_GOVERNANCE_GATE_POLICY),
    }


def recommend_governance_submission_action(candidate: Mapping[str, Any]) -> dict[str, Any]:
    validation = validate_governance_submission_candidate(candidate)
    source_snapshot = _as_dict(candidate.get("source_draft_snapshot"))
    if validation["valid"]:
        action = "create_real_proposal_manually_in_governed_flow"
        reason = "Submission candidate is valid for manual governance review, but this gate does not submit or create a real proposal."
    else:
        action = "do_not_create_governance_submission"
        reason = _recommendation_reason(validation)
    return {
        "action": action,
        "reason": reason,
        "routing": MEMORY_GOVERNANCE_SUBMISSION_ROUTING,
        "validation": validation,
        "draft_recommendation": recommend_memory_proposal_draft_action(source_snapshot) if source_snapshot else {},
        "creates_submission_candidates_only": True,
        "creates_real_proposals": False,
        "applies_proposals": False,
        "persists_approvals": False,
        "submits_to_governance": False,
        "policy": dict(MEMORY_PROPOSAL_GOVERNANCE_GATE_POLICY),
    }


def summarize_governance_submission_candidates(
    candidates: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
) -> dict[str, Any]:
    by_block_type: dict[str, int] = {}
    by_status: dict[str, int] = {}
    valid_count = 0
    invalid_count = 0
    for candidate in candidates:
        block_type = str(candidate.get("block_type"))
        by_block_type[block_type] = by_block_type.get(block_type, 0) + 1
        status = str(candidate.get("submission_status"))
        by_status[status] = by_status.get(status, 0) + 1
        validation = validate_governance_submission_candidate(candidate)
        if validation["valid"]:
            valid_count += 1
        else:
            invalid_count += 1
    return {
        "total": len(candidates),
        "valid_count": valid_count,
        "invalid_count": invalid_count,
        "by_block_type": dict(sorted(by_block_type.items())),
        "by_status": dict(sorted(by_status.items())),
        "policy": dict(MEMORY_PROPOSAL_GOVERNANCE_GATE_POLICY),
    }


def _submission_invalid_reasons(draft: Mapping[str, Any], draft_validation: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    if draft_validation.get("valid") is not True:
        reasons.append("invalid_proposal_draft")
    if not isinstance(draft.get("payload_preview"), Mapping):
        reasons.append("missing_payload_preview")
    if not (draft.get("source_pattern_ids") or draft.get("source_fact_ids")):
        reasons.append("missing_source_evidence")
    if draft.get("proposal_status") != "draft_review_required":
        reasons.append("source_proposal_status_must_be_draft_review_required")
    return reasons


def _recommendation_reason(validation: Mapping[str, Any]) -> str:
    errors = list(validation.get("errors", []) or [])
    if "missing_payload_preview" in errors:
        return "Submission candidate is missing the payload preview required for manual governance review."
    if "missing_source_evidence" in errors:
        return "Submission candidate is missing source pattern or fact evidence."
    if "invalid_proposal_draft" in errors:
        return "Source proposal draft is invalid and cannot be routed toward governance review."
    return "Submission candidate violates the v0.1 governance submission validation contract."


def _submission_id(candidate: Mapping[str, Any]) -> str:
    identity = {
        "version": MEMORY_PROPOSAL_GOVERNANCE_GATE_VERSION,
        "submission_kind": candidate.get("submission_kind"),
        "submission_status": candidate.get("submission_status"),
        "routing": candidate.get("routing"),
        "source_draft_id": candidate.get("source_draft_id"),
        "source_decision_id": candidate.get("source_decision_id"),
        "source_queue_item_id": candidate.get("source_queue_item_id"),
        "block_id": candidate.get("block_id"),
        "block_type": candidate.get("block_type"),
        "project_scope": candidate.get("project_scope"),
        "reviewer": candidate.get("reviewer"),
        "payload_preview": candidate.get("payload_preview"),
        "source_pattern_ids": list(candidate.get("source_pattern_ids", [])),
        "source_fact_ids": list(candidate.get("source_fact_ids", [])),
        "draft_validation": candidate.get("draft_validation", {}),
        "policy": candidate.get("policy", {}),
    }
    payload = json.dumps(identity, sort_keys=True, separators=(",", ":"), default=str)
    return f"memory-governance-submission:v0.1:{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16]}"


def _as_dict(value: Any) -> dict[str, Any]:
    return deepcopy(dict(value)) if isinstance(value, Mapping) else {}
