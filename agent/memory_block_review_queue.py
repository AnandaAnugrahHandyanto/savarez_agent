from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Mapping

from agent.memory_blocks import (
    MEMORY_BLOCK_POLICY,
    normalize_memory_block,
    recommend_memory_block_action,
    validate_memory_block_candidate,
)


MEMORY_BLOCK_REVIEW_QUEUE_VERSION = "0.1"
MEMORY_BLOCK_REVIEW_QUEUE_POLICY = {
    "read_only": True,
    "would_write_memory": False,
    "would_modify_config": False,
    "would_write_graph": False,
    "does_not_create_operation_events": True,
    "creates_review_candidates_only": True,
    "applies_blocks": False,
}

_TYPE_PRIORITY: dict[str, tuple[int, str]] = {
    "safety_policy": (90, "high"),
    "procedural_rules": (70, "medium"),
    "methodology": (70, "medium"),
    "persona": (60, "medium"),
    "collaboration_style": (60, "medium"),
    "human_profile": (60, "medium"),
    "project_context": (40, "low"),
    "current_task_state": (40, "low"),
}


def create_review_queue_item(
    block: Mapping[str, Any],
    reason: str | None = None,
    reviewer: str | None = None,
) -> dict[str, Any]:
    """Create a deterministic read-only review queue item for a memory block candidate."""
    normalized = normalize_memory_block(block)
    validation = validate_memory_block_candidate(normalized)
    priority, risk_level = _priority_for_block(normalized, validation)
    recommended_action = recommend_memory_block_action(normalized)
    item = {
        "queue_item_id": None,
        "block_id": normalized["block_id"],
        "block_type": normalized["block_type"],
        "project_scope": normalized["project_scope"],
        "status": "pending_review",
        "priority": priority,
        "risk_level": risk_level,
        "reason": reason or _default_reason(normalized, validation),
        "reviewer": reviewer,
        "source_pattern_ids": deepcopy(normalized["source_pattern_ids"]),
        "source_fact_ids": deepcopy(normalized["source_fact_ids"]),
        "validation": deepcopy(validation),
        "recommended_action": deepcopy(recommended_action),
        "block_snapshot": deepcopy(normalized),
        "policy": dict(MEMORY_BLOCK_REVIEW_QUEUE_POLICY),
    }
    item["queue_item_id"] = _queue_item_id(item)
    return item


def build_review_queue(
    blocks: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
    reviewer: str | None = None,
) -> list[dict[str, Any]]:
    """Build and prioritize a read-only review queue from memory block candidates."""
    return prioritize_review_queue([create_review_queue_item(block, reviewer=reviewer) for block in blocks])


def prioritize_review_queue(items: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...]) -> list[dict[str, Any]]:
    """Return queue items sorted by priority, then stable deterministic tie-breakers."""
    copied = [deepcopy(dict(item)) for item in items]
    return sorted(
        copied,
        key=lambda item: (
            -int(item.get("priority", 0)),
            str(item.get("risk_level", "")),
            str(item.get("block_type", "")),
            str(item.get("project_scope", "")),
            str(item.get("block_id", "")),
            str(item.get("queue_item_id", "")),
        ),
    )


def validate_review_queue_item(item: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    policy = _as_dict(item.get("policy"))
    validation = _as_dict(item.get("validation"))

    for key in (
        "queue_item_id",
        "block_id",
        "block_type",
        "status",
        "priority",
        "risk_level",
        "validation",
        "recommended_action",
        "block_snapshot",
        "policy",
    ):
        if key not in item:
            errors.append(f"missing_{key}")
    if item.get("status") != "pending_review":
        errors.append("status_must_be_pending_review")
    if not isinstance(item.get("priority"), int):
        errors.append("priority_must_be_int")
    if item.get("risk_level") not in {"low", "medium", "high"}:
        errors.append("risk_level_must_be_low_medium_or_high")
    if not isinstance(validation.get("valid"), bool):
        errors.append("validation_valid_must_be_bool")
    for key, expected in MEMORY_BLOCK_REVIEW_QUEUE_POLICY.items():
        if policy.get(key) is not expected:
            errors.append(f"policy_{key}_must_be_{str(expected).lower()}")

    return {"valid": not errors, "errors": errors}


def summarize_review_queue(items: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...]) -> dict[str, Any]:
    by_risk = {"high": 0, "medium": 0, "low": 0}
    by_block_type: dict[str, int] = {}
    invalid_count = 0
    for item in items:
        risk = str(item.get("risk_level", "medium"))
        if risk in by_risk:
            by_risk[risk] += 1
        block_type = str(item.get("block_type"))
        by_block_type[block_type] = by_block_type.get(block_type, 0) + 1
        validation = _as_dict(item.get("validation"))
        if validation.get("valid") is not True:
            invalid_count += 1
    return {
        "total": len(items),
        "by_risk": by_risk,
        "by_block_type": dict(sorted(by_block_type.items())),
        "invalid_count": invalid_count,
        "policy": dict(MEMORY_BLOCK_REVIEW_QUEUE_POLICY),
    }


def explain_review_queue_item(item: Mapping[str, Any]) -> dict[str, Any]:
    validation = validate_review_queue_item(item)
    return {
        "queue_item_id": item.get("queue_item_id"),
        "block_id": item.get("block_id"),
        "block_type": item.get("block_type"),
        "project_scope": item.get("project_scope"),
        "status": item.get("status"),
        "priority": item.get("priority"),
        "risk_level": item.get("risk_level"),
        "reviewer": item.get("reviewer"),
        "source_pattern_count": len(item.get("source_pattern_ids", []) or []),
        "source_fact_count": len(item.get("source_fact_ids", []) or []),
        "validation": validation,
        "block_validation": deepcopy(item.get("validation", {})),
        "recommended_action": deepcopy(item.get("recommended_action", {})),
        "applied": False,
        "policy": dict(MEMORY_BLOCK_REVIEW_QUEUE_POLICY),
    }


def recommend_review_queue_action(item: Mapping[str, Any]) -> dict[str, Any]:
    validation = _as_dict(item.get("validation"))
    if validation.get("valid") is not True:
        action = "review_and_reject_invalid_block"
        reason = "The queued memory block candidate violates the v0.1 validation contract."
    else:
        action = "human_review_required"
        reason = "The queued memory block candidate is valid but must stay pending until a governed proposal path is used."
    return {
        "action": action,
        "reason": reason,
        "creates_review_candidates_only": True,
        "applies_blocks": False,
        "policy": dict(MEMORY_BLOCK_REVIEW_QUEUE_POLICY),
    }


def _priority_for_block(block: Mapping[str, Any], validation: Mapping[str, Any]) -> tuple[int, str]:
    if validation.get("valid") is not True:
        return 100, "high"
    return _TYPE_PRIORITY.get(str(block.get("block_type")), (50, "medium"))


def _default_reason(block: Mapping[str, Any], validation: Mapping[str, Any]) -> str:
    if validation.get("valid") is not True:
        return "Invalid memory block candidate requires review before rejection."
    return f"{block.get('block_type')} memory block candidate requires read-only review."


def _queue_item_id(item: Mapping[str, Any]) -> str:
    identity = {
        "version": MEMORY_BLOCK_REVIEW_QUEUE_VERSION,
        "block_id": item.get("block_id"),
        "block_type": item.get("block_type"),
        "project_scope": item.get("project_scope"),
        "reason": item.get("reason"),
        "reviewer": item.get("reviewer"),
        "source_pattern_ids": list(item.get("source_pattern_ids", [])),
        "source_fact_ids": list(item.get("source_fact_ids", [])),
        "validation": item.get("validation", {}),
        "policy": item.get("policy", {}),
    }
    payload = json.dumps(identity, sort_keys=True, separators=(",", ":"), default=str)
    return f"memory-block-review:v0.1:{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16]}"


def _as_dict(value: Any) -> dict[str, Any]:
    return deepcopy(dict(value)) if isinstance(value, Mapping) else {}
