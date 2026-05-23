from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Mapping

from agent.memory_proposal_governance_gate import (
    explain_governance_submission_candidate,
    recommend_governance_submission_action,
    validate_governance_submission_candidate,
)


MEMORY_GOVERNANCE_SUBMISSION_PACKET_VERSION = "0.1"
MEMORY_GOVERNANCE_SUBMISSION_PACKET_KIND = "memory_governance_submission_packet_candidate"
MEMORY_GOVERNANCE_SUBMISSION_PACKET_STATUS = "human_review_packet_required"
MEMORY_GOVERNANCE_SUBMISSION_PACKET_ROUTING = "manual_review_before_real_proposal_creation"
MEMORY_GOVERNANCE_SUBMISSION_PACKET_POLICY = {
    "read_only": True,
    "would_write_memory": False,
    "would_modify_config": False,
    "would_write_graph": False,
    "does_not_create_operation_events": True,
    "creates_review_packets_only": True,
    "creates_real_proposals": False,
    "applies_proposals": False,
    "persists_approvals": False,
    "submits_to_governance": False,
    "converts_to_real_proposal": False,
}

_FORBIDDEN_TRUE_KEYS = (
    "submitted",
    "applied",
    "persisted",
    "approved",
    "converted_to_real_proposal",
    "created_real_proposal",
    "created_operation_event",
)


def create_governance_submission_packet(
    submission_candidate: Mapping[str, Any], reviewer: str | None = None
) -> dict[str, Any]:
    """Create a deterministic read-only human-review packet candidate."""
    source = deepcopy(dict(submission_candidate))
    submission_validation = validate_governance_submission_candidate(source)
    invalid_reasons = _packet_invalid_reasons(source, submission_validation)

    packet = {
        "packet_id": None,
        "packet_kind": MEMORY_GOVERNANCE_SUBMISSION_PACKET_KIND,
        "packet_status": MEMORY_GOVERNANCE_SUBMISSION_PACKET_STATUS,
        "routing": MEMORY_GOVERNANCE_SUBMISSION_PACKET_ROUTING,
        "source_submission_id": source.get("submission_id"),
        "source_draft_id": source.get("source_draft_id"),
        "source_decision_id": source.get("source_decision_id"),
        "source_queue_item_id": source.get("source_queue_item_id"),
        "block_id": source.get("block_id"),
        "block_type": source.get("block_type"),
        "project_scope": source.get("project_scope"),
        "reviewer": reviewer if reviewer is not None else source.get("reviewer"),
        "payload_preview": deepcopy(source.get("payload_preview")),
        "source_pattern_ids": deepcopy(list(source.get("source_pattern_ids", []) or [])),
        "source_fact_ids": deepcopy(list(source.get("source_fact_ids", []) or [])),
        "evidence_summary": _evidence_summary(source),
        "human_review_checklist": _human_review_checklist(),
        "risk_notes": _risk_notes(source, submission_validation, invalid_reasons),
        "submission_validation": deepcopy(submission_validation),
        "packet_validation": {"valid": False, "errors": ["not_validated"]},
        "next_step_recommendation": {},
        "source_submission_snapshot": deepcopy(source),
        "policy": dict(MEMORY_GOVERNANCE_SUBMISSION_PACKET_POLICY),
    }
    packet["packet_id"] = _packet_id(packet)
    packet["packet_validation"] = validate_governance_submission_packet(packet)
    if invalid_reasons:
        errors = list(packet["packet_validation"]["errors"])
        for reason in invalid_reasons:
            if reason not in errors:
                errors.append(reason)
        packet["packet_validation"] = {"valid": False, "errors": errors}
    packet["next_step_recommendation"] = recommend_governance_submission_packet_action(packet)
    return packet


def validate_governance_submission_packet(packet: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    policy = _as_dict(packet.get("policy"))
    submission_validation = _as_dict(packet.get("submission_validation"))
    source_snapshot = _as_dict(packet.get("source_submission_snapshot"))

    for key in (
        "packet_id",
        "packet_kind",
        "packet_status",
        "routing",
        "source_submission_id",
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
        "evidence_summary",
        "human_review_checklist",
        "risk_notes",
        "submission_validation",
        "packet_validation",
        "next_step_recommendation",
        "source_submission_snapshot",
        "policy",
    ):
        if key not in packet:
            errors.append(f"missing_{key}")
    if packet.get("packet_kind") != MEMORY_GOVERNANCE_SUBMISSION_PACKET_KIND:
        errors.append("packet_kind_must_be_memory_governance_submission_packet_candidate")
    if packet.get("packet_status") != MEMORY_GOVERNANCE_SUBMISSION_PACKET_STATUS:
        errors.append("packet_status_must_be_human_review_packet_required")
    if packet.get("routing") != MEMORY_GOVERNANCE_SUBMISSION_PACKET_ROUTING:
        errors.append("routing_must_require_manual_review_before_real_proposal_creation")
    if submission_validation.get("valid") is not True:
        errors.append("invalid_governance_submission_candidate")
    if source_snapshot:
        snapshot_validation = validate_governance_submission_candidate(source_snapshot)
        if snapshot_validation.get("valid") is not True:
            errors.append("invalid_governance_submission_candidate")
    if source_snapshot.get("submission_status") != "governance_review_required":
        errors.append("source_submission_status_must_be_governance_review_required")
    if not isinstance(packet.get("payload_preview"), Mapping):
        errors.append("missing_payload_preview")
    if not isinstance(packet.get("source_pattern_ids"), list):
        errors.append("source_pattern_ids_must_be_list")
    if not isinstance(packet.get("source_fact_ids"), list):
        errors.append("source_fact_ids_must_be_list")
    if isinstance(packet.get("source_pattern_ids"), list) and isinstance(packet.get("source_fact_ids"), list):
        if not packet.get("source_pattern_ids") and not packet.get("source_fact_ids"):
            errors.append("missing_source_evidence")
    if not isinstance(packet.get("evidence_summary"), Mapping):
        errors.append("evidence_summary_must_be_mapping")
    if not isinstance(packet.get("human_review_checklist"), list) or not packet.get("human_review_checklist"):
        errors.append("human_review_checklist_must_be_non_empty_list")
    if not isinstance(packet.get("risk_notes"), list):
        errors.append("risk_notes_must_be_list")
    for forbidden_key in _FORBIDDEN_TRUE_KEYS:
        if packet.get(forbidden_key) is True:
            errors.append(f"{forbidden_key}_must_be_false_or_absent")
    for key, expected in MEMORY_GOVERNANCE_SUBMISSION_PACKET_POLICY.items():
        if policy.get(key) is not expected:
            errors.append(f"policy_{key}_must_be_{str(expected).lower()}")

    return {"valid": not errors, "errors": _dedupe(errors)}


def explain_governance_submission_packet(packet: Mapping[str, Any]) -> dict[str, Any]:
    validation = validate_governance_submission_packet(packet)
    source_snapshot = _as_dict(packet.get("source_submission_snapshot"))
    return {
        "packet_id": packet.get("packet_id"),
        "packet_kind": packet.get("packet_kind"),
        "packet_status": packet.get("packet_status"),
        "routing": packet.get("routing"),
        "source_submission_id": packet.get("source_submission_id"),
        "source_draft_id": packet.get("source_draft_id"),
        "source_decision_id": packet.get("source_decision_id"),
        "source_queue_item_id": packet.get("source_queue_item_id"),
        "block_id": packet.get("block_id"),
        "block_type": packet.get("block_type"),
        "project_scope": packet.get("project_scope"),
        "reviewer": packet.get("reviewer"),
        "source_pattern_count": len(packet.get("source_pattern_ids", []) or []),
        "source_fact_count": len(packet.get("source_fact_ids", []) or []),
        "evidence_summary": deepcopy(packet.get("evidence_summary")),
        "human_review_checklist": deepcopy(packet.get("human_review_checklist")),
        "risk_notes": deepcopy(packet.get("risk_notes")),
        "validation": validation,
        "submission_explanation": explain_governance_submission_candidate(source_snapshot) if source_snapshot else {},
        "submitted": False,
        "applied": False,
        "persisted": False,
        "approved": False,
        "converted_to_real_proposal": False,
        "created_real_proposal": False,
        "created_operation_event": False,
        "policy": dict(MEMORY_GOVERNANCE_SUBMISSION_PACKET_POLICY),
    }


def recommend_governance_submission_packet_action(packet: Mapping[str, Any]) -> dict[str, Any]:
    validation = validate_governance_submission_packet(packet)
    source_snapshot = _as_dict(packet.get("source_submission_snapshot"))
    if validation["valid"]:
        action = "route_packet_to_manual_human_review"
        reason = "Packet candidate is valid for manual human review, but this module does not submit or create a real proposal."
    else:
        action = "do_not_route_packet"
        reason = _recommendation_reason(validation)
    return {
        "action": action,
        "reason": reason,
        "routing": MEMORY_GOVERNANCE_SUBMISSION_PACKET_ROUTING,
        "validation": validation,
        "submission_recommendation": recommend_governance_submission_action(source_snapshot) if source_snapshot else {},
        "creates_review_packets_only": True,
        "creates_real_proposals": False,
        "applies_proposals": False,
        "persists_approvals": False,
        "submits_to_governance": False,
        "converts_to_real_proposal": False,
        "policy": dict(MEMORY_GOVERNANCE_SUBMISSION_PACKET_POLICY),
    }


def summarize_governance_submission_packets(
    packets: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
) -> dict[str, Any]:
    by_block_type: dict[str, int] = {}
    by_status: dict[str, int] = {}
    valid_count = 0
    invalid_count = 0
    for packet in packets:
        block_type = str(packet.get("block_type"))
        by_block_type[block_type] = by_block_type.get(block_type, 0) + 1
        status = str(packet.get("packet_status"))
        by_status[status] = by_status.get(status, 0) + 1
        validation = validate_governance_submission_packet(packet)
        if validation["valid"]:
            valid_count += 1
        else:
            invalid_count += 1
    return {
        "total": len(packets),
        "valid_count": valid_count,
        "invalid_count": invalid_count,
        "by_block_type": dict(sorted(by_block_type.items())),
        "by_status": dict(sorted(by_status.items())),
        "policy": dict(MEMORY_GOVERNANCE_SUBMISSION_PACKET_POLICY),
    }


def _packet_invalid_reasons(source: Mapping[str, Any], submission_validation: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    if submission_validation.get("valid") is not True:
        reasons.append("invalid_governance_submission_candidate")
    if not isinstance(source.get("payload_preview"), Mapping):
        reasons.append("missing_payload_preview")
    if not (source.get("source_pattern_ids") or source.get("source_fact_ids")):
        reasons.append("missing_source_evidence")
    return _dedupe(reasons)


def _evidence_summary(source: Mapping[str, Any]) -> dict[str, Any]:
    pattern_ids = list(source.get("source_pattern_ids", []) or [])
    fact_ids = list(source.get("source_fact_ids", []) or [])
    return {
        "source_pattern_count": len(pattern_ids),
        "source_fact_count": len(fact_ids),
        "source_pattern_ids": deepcopy(pattern_ids),
        "source_fact_ids": deepcopy(fact_ids),
        "has_source_evidence": bool(pattern_ids or fact_ids),
    }


def _human_review_checklist() -> list[dict[str, str]]:
    return [
        {
            "id": "verify_payload_preview",
            "label": "Verify payload preview matches intended memory block change.",
        },
        {
            "id": "verify_source_evidence",
            "label": "Verify source pattern and fact evidence supports the change.",
        },
        {
            "id": "verify_scope_and_routing",
            "label": "Verify project scope and manual review routing are correct.",
        },
        {
            "id": "verify_no_side_effects",
            "label": "Verify no proposal, approval, memory, graph, config, or ledger write occurred.",
        },
    ]


def _risk_notes(
    source: Mapping[str, Any],
    submission_validation: Mapping[str, Any],
    invalid_reasons: list[str],
) -> list[str]:
    notes = [
        "Packet is a read-only candidate for human review only.",
        "Manual review is required before any real proposal creation.",
    ]
    if submission_validation.get("valid") is not True:
        notes.append("Source governance submission candidate is invalid.")
    if "missing_payload_preview" in invalid_reasons:
        notes.append("Payload preview is missing and must be supplied before review.")
    if "missing_source_evidence" in invalid_reasons:
        notes.append("Source evidence is missing and must be supplied before review.")
    if source.get("block_type") == "safety_policy":
        notes.append("Safety policy blocks require extra governance scrutiny.")
    return notes


def _recommendation_reason(validation: Mapping[str, Any]) -> str:
    errors = list(validation.get("errors", []) or [])
    if "missing_payload_preview" in errors:
        return "Packet candidate is missing the payload preview required for human review."
    if "missing_source_evidence" in errors:
        return "Packet candidate is missing source pattern or fact evidence."
    if "invalid_governance_submission_candidate" in errors:
        return "Source governance submission candidate is invalid and cannot be routed as a review packet."
    return "Packet candidate violates the v0.1 governance submission packet validation contract."


def _packet_id(packet: Mapping[str, Any]) -> str:
    identity = {
        "version": MEMORY_GOVERNANCE_SUBMISSION_PACKET_VERSION,
        "packet_kind": packet.get("packet_kind"),
        "packet_status": packet.get("packet_status"),
        "routing": packet.get("routing"),
        "source_submission_id": packet.get("source_submission_id"),
        "source_draft_id": packet.get("source_draft_id"),
        "source_decision_id": packet.get("source_decision_id"),
        "source_queue_item_id": packet.get("source_queue_item_id"),
        "block_id": packet.get("block_id"),
        "block_type": packet.get("block_type"),
        "project_scope": packet.get("project_scope"),
        "reviewer": packet.get("reviewer"),
        "payload_preview": packet.get("payload_preview"),
        "source_pattern_ids": list(packet.get("source_pattern_ids", [])),
        "source_fact_ids": list(packet.get("source_fact_ids", [])),
        "evidence_summary": packet.get("evidence_summary", {}),
        "human_review_checklist": packet.get("human_review_checklist", []),
        "submission_validation": packet.get("submission_validation", {}),
        "policy": packet.get("policy", {}),
    }
    payload = json.dumps(identity, sort_keys=True, separators=(",", ":"), default=str)
    return f"memory-governance-submission-packet:v0.1:{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16]}"


def _as_dict(value: Any) -> dict[str, Any]:
    return deepcopy(dict(value)) if isinstance(value, Mapping) else {}


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
