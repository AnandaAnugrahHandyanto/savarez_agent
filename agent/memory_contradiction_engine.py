from __future__ import annotations

from datetime import UTC, datetime
from itertools import combinations
from typing import Any, Iterable, Mapping

from agent.memory_bitemporal_fact_graph import BitemporalFact, normalize_fact


CONTRADICTION_ENGINE_POLICY = {
    "read_only": True,
    "would_write_memory": False,
    "would_modify_config": False,
    "would_write_graph": False,
    "does_not_create_operation_events": True,
    "creates_review_recommendations_only": True,
}

RELATION_LABELS = (
    "supports",
    "updates",
    "contradicts",
    "unrelated",
    "needs_review",
)

_UNSAFE_GOVERNANCE_TRUE_KEYS = (
    "unsafe",
    "write_allowed",
    "would_write_memory",
    "would_modify_config",
    "would_write_graph",
    "creates_operation_event",
    "create_operation_event",
    "approves_allowlist",
    "approve_allowlist",
    "external_auto_recall_allowed",
)


def classify_fact_relation(
    existing_fact: Mapping[str, Any] | BitemporalFact,
    candidate_fact: Mapping[str, Any] | BitemporalFact,
) -> dict[str, Any]:
    """Classify one existing/candidate fact pair without mutating either input."""
    existing = normalize_fact(existing_fact)
    candidate = normalize_fact(candidate_fact)
    reasons: list[str] = []
    risks: list[str] = []

    same_scope = (
        existing.subject == candidate.subject
        and existing.predicate == candidate.predicate
        and existing.project_id == candidate.project_id
    )
    if not same_scope:
        relation = "unrelated"
        reasons.append("subject_predicate_or_project_scope_differs")
    else:
        missing_provenance = _missing_provenance(existing) or _missing_provenance(candidate)
        unsafe_governance = _unsafe_governance_reasons(existing.governance) + _unsafe_governance_reasons(candidate.governance)
        low_confidence = min(existing.confidence, candidate.confidence) < 0.5

        if missing_provenance:
            risks.append("missing_provenance")
        if unsafe_governance:
            risks.extend(f"unsafe_governance:{reason}" for reason in sorted(set(unsafe_governance)))
        if low_confidence:
            risks.append("low_confidence")

        if existing.object == candidate.object:
            relation = "needs_review" if risks else "supports"
            reasons.append("same_subject_predicate_project_and_object")
        elif _candidate_updates_existing(existing, candidate):
            relation = "needs_review" if risks else "updates"
            reasons.append("candidate_validity_starts_after_existing_validity")
        else:
            relation = "needs_review" if risks else "contradicts"
            reasons.append("same_subject_predicate_project_with_different_object")
            if _validity_windows_overlap(existing, candidate):
                reasons.append("validity_windows_overlap_or_are_open")
            else:
                reasons.append("validity_windows_do_not_overlap")

    return {
        "relation": relation,
        "existing_fact": existing.to_json(),
        "candidate_fact": candidate.to_json(),
        "same_subject": existing.subject == candidate.subject,
        "same_predicate": existing.predicate == candidate.predicate,
        "same_project_id": existing.project_id == candidate.project_id,
        "same_object": existing.object == candidate.object,
        "validity_windows_overlap": _validity_windows_overlap(existing, candidate),
        "confidence": {
            "existing": existing.confidence,
            "candidate": candidate.confidence,
            "minimum": min(existing.confidence, candidate.confidence),
        },
        "risks": risks,
        "reasons": reasons,
        "policy": dict(CONTRADICTION_ENGINE_POLICY),
    }


def detect_contradiction_candidates(
    existing_facts: Iterable[Mapping[str, Any] | BitemporalFact],
    candidate_facts: Iterable[Mapping[str, Any] | BitemporalFact],
) -> list[dict[str, Any]]:
    """Return candidate classifications that need review or represent conflicts."""
    classifications: list[dict[str, Any]] = []
    for existing in existing_facts:
        for candidate in candidate_facts:
            relation = classify_fact_relation(existing, candidate)
            if relation["relation"] in {"contradicts", "needs_review", "updates"}:
                classifications.append(relation)
    return sorted(
        classifications,
        key=lambda item: (
            item["candidate_fact"].get("project_id") or "",
            item["candidate_fact"]["subject"],
            item["candidate_fact"]["predicate"],
            item["candidate_fact"]["fact_id"],
            item["existing_fact"]["fact_id"],
        ),
    )


def group_contradictions(facts: Iterable[Mapping[str, Any] | BitemporalFact]) -> list[dict[str, Any]]:
    """Group same subject/predicate/project facts that have conflicting objects."""
    normalized = [normalize_fact(fact) for fact in facts]
    grouped: dict[tuple[str, str, str | None], list[BitemporalFact]] = {}
    for fact in normalized:
        grouped.setdefault((fact.subject, fact.predicate, fact.project_id), []).append(fact)

    contradiction_groups: list[dict[str, Any]] = []
    for (subject, predicate, project_id), group in grouped.items():
        objects = sorted({fact.object for fact in group})
        if len(objects) < 2:
            continue
        relation_items = [
            classify_fact_relation(existing, candidate)
            for existing, candidate in combinations(sorted(group, key=lambda fact: fact.fact_id), 2)
        ]
        contradiction_groups.append(
            {
                "group_id": _group_id(subject, predicate, project_id),
                "subject": subject,
                "predicate": predicate,
                "project_id": project_id,
                "objects": objects,
                "fact_ids": sorted(fact.fact_id for fact in group),
                "facts": [fact.to_json() for fact in sorted(group, key=lambda fact: fact.fact_id)],
                "relations": relation_items,
                "policy": dict(CONTRADICTION_ENGINE_POLICY),
            }
        )
    return sorted(
        contradiction_groups,
        key=lambda item: (item["project_id"] or "", item["subject"], item["predicate"], item["group_id"]),
    )


def explain_contradiction_group(group: Mapping[str, Any]) -> dict[str, Any]:
    relations = list(group.get("relations", []))
    labels = sorted({relation.get("relation") for relation in relations if relation.get("relation")})
    risks = sorted({risk for relation in relations for risk in relation.get("risks", [])})
    return {
        "group_id": group.get("group_id"),
        "subject": group.get("subject"),
        "predicate": group.get("predicate"),
        "project_id": group.get("project_id"),
        "objects": list(group.get("objects", [])),
        "fact_ids": list(group.get("fact_ids", [])),
        "relation_labels": labels,
        "risks": risks,
        "summary": _summary_for_labels(labels, risks),
        "recommended_action": recommend_contradiction_action(group),
        "policy": dict(CONTRADICTION_ENGINE_POLICY),
    }


def recommend_contradiction_action(group: Mapping[str, Any]) -> dict[str, Any]:
    """Recommend review-only next steps; this never creates proposals or writes state."""
    relations = list(group.get("relations", []))
    labels = {relation.get("relation") for relation in relations}
    risks = sorted({risk for relation in relations for risk in relation.get("risks", [])})

    if "needs_review" in labels:
        action = "review_required"
        reason = "One or more facts lack provenance, have low confidence, or carry unsafe governance indicators."
    elif "contradicts" in labels:
        action = "review_contradiction"
        reason = "Conflicting objects share the same subject, predicate, and project scope."
    elif "updates" in labels:
        action = "review_update"
        reason = "A newer candidate appears to update an expired or superseded fact."
    else:
        action = "no_action"
        reason = "No contradictory relation was detected."

    return {
        "action": action,
        "reason": reason,
        "risks": risks,
        "creates_review_recommendations_only": True,
        "policy": dict(CONTRADICTION_ENGINE_POLICY),
    }


def _candidate_updates_existing(existing: BitemporalFact, candidate: BitemporalFact) -> bool:
    if existing.fact_id in candidate.supersedes:
        return True
    if existing.valid_until and candidate.valid_from and existing.valid_until <= candidate.valid_from:
        return True
    if existing.system_invalidated_at and candidate.system_created_at:
        return existing.system_invalidated_at <= candidate.system_created_at
    return False


def _validity_windows_overlap(left: BitemporalFact, right: BitemporalFact) -> bool:
    left_start = left.valid_from or datetime.min.replace(tzinfo=UTC)
    left_end = left.valid_until or datetime.max.replace(tzinfo=UTC)
    right_start = right.valid_from or datetime.min.replace(tzinfo=UTC)
    right_end = right.valid_until or datetime.max.replace(tzinfo=UTC)
    return left_start < right_end and right_start < left_end


def _missing_provenance(fact: BitemporalFact) -> bool:
    return not (fact.provenance or fact.source_episode_id)


def _unsafe_governance_reasons(governance: Mapping[str, Any] | None) -> list[str]:
    if not governance:
        return []
    if not isinstance(governance, Mapping):
        return []
    reasons = [key for key in _UNSAFE_GOVERNANCE_TRUE_KEYS if governance.get(key) is True]
    mode = str(governance.get("mode", "")).lower()
    if any(marker in mode for marker in ("write", "mutate", "modify")):
        reasons.append("mode")
    if governance.get("read_only") is False:
        reasons.append("read_only")
    return reasons


def _group_id(subject: str, predicate: str, project_id: str | None) -> str:
    return "|".join((project_id or "*", subject, predicate))


def _summary_for_labels(labels: list[str], risks: list[str]) -> str:
    if "needs_review" in labels:
        return "Conflicting memory facts require human review before any proposal or write path is considered."
    if "contradicts" in labels:
        return "Conflicting memory facts were detected in the same subject, predicate, and project scope."
    if "updates" in labels:
        return "A candidate appears to update an older expired fact and should be reviewed as a lineage change."
    if risks:
        return "Memory facts carry review risks even though no hard contradiction was detected."
    return "No contradiction was detected."
