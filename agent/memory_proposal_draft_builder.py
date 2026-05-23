from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Mapping

from agent.memory_review_decision_gate import (
    explain_review_decision_candidate,
    recommend_review_decision_action,
    validate_review_decision_candidate,
)


MEMORY_PROPOSAL_DRAFT_BUILDER_VERSION = "0.1"
MEMORY_PROPOSAL_DRAFT_KIND = "memory_block_write_proposal_draft"
MEMORY_PROPOSAL_DRAFT_STATUS = "draft_review_required"
MEMORY_PROPOSAL_DRAFT_ROUTING = "separate_governed_proposal_flow_required"
MEMORY_PROPOSAL_DRAFT_POLICY = {
    "read_only": True,
    "would_write_memory": False,
    "would_modify_config": False,
    "would_write_graph": False,
    "does_not_create_operation_events": True,
    "creates_draft_candidates_only": True,
    "creates_real_proposals": False,
    "applies_proposals": False,
    "persists_approvals": False,
}

_INVALID_REASON_BY_DECISION = {
    "request_more_evidence": "more_evidence_required",
    "reject": "rejected_decision",
    "defer": "deferred_decision",
}


def create_memory_proposal_draft(decision_candidate: Mapping[str, Any], author: str | None = None) -> dict[str, Any]:
    """Create a deterministic read-only proposal draft candidate from a decision candidate."""
    source = deepcopy(dict(decision_candidate))
    decision_validation = validate_review_decision_candidate(source)
    source_snapshot = deepcopy(source)
    queue_snapshot = _as_dict(source.get("queue_item_snapshot"))
    block_snapshot = _as_dict(queue_snapshot.get("block_snapshot"))
    reason = _draft_invalid_reason(source, decision_validation)

    draft = {
        "draft_id": None,
        "proposal_kind": MEMORY_PROPOSAL_DRAFT_KIND,
        "proposal_status": MEMORY_PROPOSAL_DRAFT_STATUS,
        "routing": MEMORY_PROPOSAL_DRAFT_ROUTING,
        "source_decision_id": source.get("decision_id"),
        "source_queue_item_id": source.get("queue_item_id"),
        "block_id": source.get("block_id"),
        "block_type": source.get("block_type"),
        "project_scope": source.get("project_scope"),
        "author": author if author is not None else source.get("reviewer"),
        "rationale": _draft_rationale(source, reason),
        "payload_preview": _payload_preview(source, block_snapshot),
        "source_pattern_ids": deepcopy(list(source.get("source_pattern_ids", []) or [])),
        "source_fact_ids": deepcopy(list(source.get("source_fact_ids", []) or [])),
        "decision_validation": deepcopy(decision_validation),
        "draft_validation": {"valid": False, "errors": ["not_validated"]},
        "next_step_recommendation": {},
        "source_decision_snapshot": source_snapshot,
        "policy": dict(MEMORY_PROPOSAL_DRAFT_POLICY),
    }
    draft["draft_id"] = _draft_id(draft)
    draft["draft_validation"] = validate_memory_proposal_draft(draft)
    draft["next_step_recommendation"] = recommend_memory_proposal_draft_action(draft)
    return draft


def validate_memory_proposal_draft(draft: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    policy = _as_dict(draft.get("policy"))
    decision_validation = _as_dict(draft.get("decision_validation"))
    source_snapshot = _as_dict(draft.get("source_decision_snapshot"))

    for key in (
        "draft_id",
        "proposal_kind",
        "proposal_status",
        "source_decision_id",
        "source_queue_item_id",
        "block_id",
        "block_type",
        "project_scope",
        "author",
        "rationale",
        "payload_preview",
        "source_pattern_ids",
        "source_fact_ids",
        "decision_validation",
        "draft_validation",
        "next_step_recommendation",
        "source_decision_snapshot",
        "policy",
    ):
        if key not in draft:
            errors.append(f"missing_{key}")
    if "routing" not in draft:
        errors.append("missing_routing")
    if draft.get("proposal_kind") != MEMORY_PROPOSAL_DRAFT_KIND:
        errors.append("proposal_kind_must_be_memory_block_write_proposal_draft")
    if draft.get("proposal_status") != MEMORY_PROPOSAL_DRAFT_STATUS:
        errors.append("proposal_status_must_be_draft_review_required")
    if draft.get("routing") != MEMORY_PROPOSAL_DRAFT_ROUTING:
        errors.append("routing_must_require_separate_governed_proposal_flow")
    if decision_validation.get("valid") is not True:
        errors.append("invalid_decision_candidate")
    elif source_snapshot.get("decision") != "approve_to_proposal":
        errors.append(_INVALID_REASON_BY_DECISION.get(str(source_snapshot.get("decision")), "invalid_decision_candidate"))
    if not isinstance(draft.get("source_pattern_ids"), list):
        errors.append("source_pattern_ids_must_be_list")
    if not isinstance(draft.get("source_fact_ids"), list):
        errors.append("source_fact_ids_must_be_list")
    if not isinstance(draft.get("payload_preview"), Mapping):
        errors.append("payload_preview_must_be_mapping")
    for forbidden_key in ("applied", "persisted", "created_real_proposal", "created_operation_event"):
        if draft.get(forbidden_key) is True:
            errors.append(f"{forbidden_key}_must_be_false_or_absent")
    for key, expected in MEMORY_PROPOSAL_DRAFT_POLICY.items():
        if policy.get(key) is not expected:
            errors.append(f"policy_{key}_must_be_{str(expected).lower()}")

    return {"valid": not errors, "errors": errors}


def explain_memory_proposal_draft(draft: Mapping[str, Any]) -> dict[str, Any]:
    validation = validate_memory_proposal_draft(draft)
    source_snapshot = _as_dict(draft.get("source_decision_snapshot"))
    return {
        "draft_id": draft.get("draft_id"),
        "proposal_kind": draft.get("proposal_kind"),
        "proposal_status": draft.get("proposal_status"),
        "routing": draft.get("routing"),
        "source_decision_id": draft.get("source_decision_id"),
        "source_queue_item_id": draft.get("source_queue_item_id"),
        "block_id": draft.get("block_id"),
        "block_type": draft.get("block_type"),
        "project_scope": draft.get("project_scope"),
        "author": draft.get("author"),
        "source_pattern_count": len(draft.get("source_pattern_ids", []) or []),
        "source_fact_count": len(draft.get("source_fact_ids", []) or []),
        "validation": validation,
        "decision_explanation": explain_review_decision_candidate(source_snapshot) if source_snapshot else {},
        "applied": False,
        "persisted": False,
        "created_real_proposal": False,
        "created_operation_event": False,
        "policy": dict(MEMORY_PROPOSAL_DRAFT_POLICY),
    }


def recommend_memory_proposal_draft_action(draft: Mapping[str, Any]) -> dict[str, Any]:
    validation = validate_memory_proposal_draft(draft)
    source_snapshot = _as_dict(draft.get("source_decision_snapshot"))
    if validation["valid"]:
        action = "submit_to_separate_governed_proposal_flow"
        reason = "Draft candidate is valid for human review, but this builder does not create a real proposal."
    else:
        action = "do_not_submit_draft"
        reason = _recommendation_reason(validation)
    return {
        "action": action,
        "reason": reason,
        "routing": MEMORY_PROPOSAL_DRAFT_ROUTING,
        "validation": validation,
        "decision_recommendation": recommend_review_decision_action(source_snapshot) if source_snapshot else {},
        "creates_draft_candidates_only": True,
        "creates_real_proposals": False,
        "applies_proposals": False,
        "persists_approvals": False,
        "policy": dict(MEMORY_PROPOSAL_DRAFT_POLICY),
    }


def summarize_memory_proposal_drafts(drafts: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...]) -> dict[str, Any]:
    by_block_type: dict[str, int] = {}
    by_status: dict[str, int] = {}
    valid_count = 0
    invalid_count = 0
    for draft in drafts:
        block_type = str(draft.get("block_type"))
        by_block_type[block_type] = by_block_type.get(block_type, 0) + 1
        status = str(draft.get("proposal_status"))
        by_status[status] = by_status.get(status, 0) + 1
        validation = validate_memory_proposal_draft(draft)
        if validation["valid"]:
            valid_count += 1
        else:
            invalid_count += 1
    return {
        "total": len(drafts),
        "valid_count": valid_count,
        "invalid_count": invalid_count,
        "by_block_type": dict(sorted(by_block_type.items())),
        "by_status": dict(sorted(by_status.items())),
        "policy": dict(MEMORY_PROPOSAL_DRAFT_POLICY),
    }


def _draft_invalid_reason(source: Mapping[str, Any], decision_validation: Mapping[str, Any]) -> str | None:
    if decision_validation.get("valid") is not True:
        return "invalid_decision_candidate"
    decision = str(source.get("decision"))
    if decision == "approve_to_proposal":
        return None
    return _INVALID_REASON_BY_DECISION.get(decision, "invalid_decision_candidate")


def _draft_rationale(source: Mapping[str, Any], reason: str | None) -> str:
    if reason is None:
        return str(source.get("rationale") or "Approved decision candidate may be drafted for governed proposal review.")
    return f"Draft is invalid: {reason}."


def _payload_preview(source: Mapping[str, Any], block_snapshot: Mapping[str, Any]) -> dict[str, Any]:
    preview_source = block_snapshot if block_snapshot else source
    keys = (
        "block_id",
        "block_type",
        "status",
        "project_scope",
        "content",
        "source_pattern_ids",
        "source_fact_ids",
        "metadata",
        "version",
        "source_event_id",
        "confidence",
        "validity",
        "mutation_policy",
        "direct_write_allowed",
        "policy",
    )
    preview = {key: deepcopy(preview_source.get(key)) for key in keys if key in preview_source}
    preview.setdefault("block_id", source.get("block_id"))
    preview.setdefault("block_type", source.get("block_type"))
    preview.setdefault("project_scope", source.get("project_scope"))
    preview.setdefault("source_pattern_ids", deepcopy(list(source.get("source_pattern_ids", []) or [])))
    preview.setdefault("source_fact_ids", deepcopy(list(source.get("source_fact_ids", []) or [])))
    preview["applied"] = False
    preview["persisted"] = False
    preview["created_real_proposal"] = False
    return preview


def _recommendation_reason(validation: Mapping[str, Any]) -> str:
    errors = list(validation.get("errors", []) or [])
    if "more_evidence_required" in errors:
        return "Source decision requested more evidence before any proposal draft can be reviewed."
    if "rejected_decision" in errors:
        return "Source decision rejected the block candidate."
    if "deferred_decision" in errors:
        return "Source decision deferred the block candidate for manual review."
    return "Draft candidate violates the v0.1 proposal draft validation contract."


def _draft_id(draft: Mapping[str, Any]) -> str:
    identity = {
        "version": MEMORY_PROPOSAL_DRAFT_BUILDER_VERSION,
        "proposal_kind": draft.get("proposal_kind"),
        "proposal_status": draft.get("proposal_status"),
        "routing": draft.get("routing"),
        "source_decision_id": draft.get("source_decision_id"),
        "source_queue_item_id": draft.get("source_queue_item_id"),
        "block_id": draft.get("block_id"),
        "block_type": draft.get("block_type"),
        "project_scope": draft.get("project_scope"),
        "author": draft.get("author"),
        "source_pattern_ids": list(draft.get("source_pattern_ids", [])),
        "source_fact_ids": list(draft.get("source_fact_ids", [])),
        "decision_validation": draft.get("decision_validation", {}),
        "payload_preview": draft.get("payload_preview", {}),
        "policy": draft.get("policy", {}),
    }
    payload = json.dumps(identity, sort_keys=True, separators=(",", ":"), default=str)
    return f"memory-proposal-draft:v0.1:{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16]}"


def _as_dict(value: Any) -> dict[str, Any]:
    return deepcopy(dict(value)) if isinstance(value, Mapping) else {}
