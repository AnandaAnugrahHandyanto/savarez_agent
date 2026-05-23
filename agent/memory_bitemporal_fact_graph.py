from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from typing import Any, Iterable, Mapping


BITEMPORAL_FACT_GRAPH_POLICY = {
    "read_only": True,
    "would_write_memory": False,
    "would_modify_config": False,
    "would_write_graph": False,
    "does_not_create_operation_events": True,
}


@dataclass(frozen=True)
class BitemporalFact:
    fact_id: str
    subject: str
    predicate: str
    object: str
    project_id: str | None = None
    source_episode_id: str | None = None
    provenance: Any = None
    confidence: float = 1.0
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    system_created_at: datetime | None = None
    system_invalidated_at: datetime | None = None
    supersedes: tuple[str, ...] = ()
    contradiction_group: str | None = None
    governance: Mapping[str, Any] | None = None

    def to_json(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in ("valid_from", "valid_until", "system_created_at", "system_invalidated_at"):
            payload[key] = _datetime_to_json(payload[key])
        payload["supersedes"] = list(self.supersedes)
        payload["governance"] = dict(self.governance or BITEMPORAL_FACT_GRAPH_POLICY)
        return payload


def normalize_fact(fact: Mapping[str, Any] | BitemporalFact | None = None, **overrides: Any) -> BitemporalFact:
    """Return a normalized immutable fact record without writing external state."""
    data: dict[str, Any]
    if isinstance(fact, BitemporalFact):
        data = fact.to_json()
    else:
        data = dict(fact or {})
    data.update(overrides)

    fact_id = str(data.get("fact_id") or "").strip()
    subject = str(data.get("subject") or "").strip()
    predicate = str(data.get("predicate") or "").strip()
    obj = str(data.get("object") or "").strip()
    if not fact_id:
        raise ValueError("fact_id is required")
    if not subject:
        raise ValueError("subject is required")
    if not predicate:
        raise ValueError("predicate is required")
    if not obj:
        raise ValueError("object is required")

    confidence = float(data.get("confidence", 1.0))
    confidence = min(max(confidence, 0.0), 1.0)
    governance = data.get("governance") or BITEMPORAL_FACT_GRAPH_POLICY

    return BitemporalFact(
        fact_id=fact_id,
        subject=subject,
        predicate=predicate,
        object=obj,
        project_id=_optional_str(data.get("project_id")),
        source_episode_id=_optional_str(data.get("source_episode_id")),
        provenance=data.get("provenance"),
        confidence=confidence,
        valid_from=_coerce_datetime(data.get("valid_from")),
        valid_until=_coerce_datetime(data.get("valid_until")),
        system_created_at=_coerce_datetime(data.get("system_created_at")),
        system_invalidated_at=_coerce_datetime(data.get("system_invalidated_at")),
        supersedes=tuple(str(item) for item in _as_list(data.get("supersedes")) if str(item)),
        contradiction_group=_optional_str(data.get("contradiction_group")),
        governance=dict(governance),
    )


def fact_is_valid_at(fact: Mapping[str, Any] | BitemporalFact, at_time: str | datetime) -> bool:
    normalized = normalize_fact(fact)
    at = _require_datetime(at_time, "at_time")
    if normalized.valid_from and at < normalized.valid_from:
        return False
    if normalized.valid_until and at >= normalized.valid_until:
        return False
    if normalized.system_invalidated_at and at >= normalized.system_invalidated_at:
        return False
    return True


def select_current_facts(
    facts: Iterable[Mapping[str, Any] | BitemporalFact],
    at_time: str | datetime,
    project_scope: str | None = None,
) -> list[BitemporalFact]:
    normalized = [normalize_fact(fact) for fact in facts]
    scoped = [
        fact
        for fact in normalized
        if fact_is_valid_at(fact, at_time)
        and (project_scope is None or fact.project_id == project_scope)
    ]
    winners: dict[tuple[str, str, str | None], BitemporalFact] = {}
    for fact in scoped:
        key = (fact.subject, fact.predicate, fact.project_id)
        current = winners.get(key)
        if current is None or _fact_sort_key(fact) > _fact_sort_key(current):
            winners[key] = fact
    return sorted(winners.values(), key=lambda fact: (fact.project_id or "", fact.subject, fact.predicate, fact.fact_id))


def supersede_fact(
    old_fact: Mapping[str, Any] | BitemporalFact,
    new_fact: Mapping[str, Any] | BitemporalFact,
    superseded_at: str | datetime,
) -> tuple[BitemporalFact, BitemporalFact]:
    superseded_time = _require_datetime(superseded_at, "superseded_at")
    old = normalize_fact(old_fact)
    new = normalize_fact(new_fact)
    updated_old = replace(
        old,
        valid_until=old.valid_until or superseded_time,
        system_invalidated_at=old.system_invalidated_at or superseded_time,
    )
    updated_new = replace(
        new,
        valid_from=new.valid_from or superseded_time,
        supersedes=tuple(dict.fromkeys((*new.supersedes, old.fact_id))),
    )
    return updated_old, updated_new


def detect_fact_contradictions(facts: Iterable[Mapping[str, Any] | BitemporalFact]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str | None], list[BitemporalFact]] = {}
    for fact in (normalize_fact(item) for item in facts):
        groups.setdefault((fact.subject, fact.predicate, fact.project_id), []).append(fact)

    contradictions: list[dict[str, Any]] = []
    for (subject, predicate, project_id), group in groups.items():
        objects = sorted({fact.object for fact in group})
        if len(objects) < 2:
            continue
        contradictions.append(
            {
                "subject": subject,
                "predicate": predicate,
                "project_id": project_id,
                "objects": objects,
                "fact_ids": sorted(fact.fact_id for fact in group),
                "contradiction_group": group[0].contradiction_group
                or _contradiction_group_id(subject, predicate, project_id),
            }
        )
    return sorted(contradictions, key=lambda item: (item["project_id"] or "", item["subject"], item["predicate"]))


def explain_fact_lineage(fact_id: str, facts: Iterable[Mapping[str, Any] | BitemporalFact]) -> dict[str, Any]:
    normalized = [normalize_fact(fact) for fact in facts]
    by_id = {fact.fact_id: fact for fact in normalized}
    target = by_id.get(fact_id)
    if target is None:
        return {
            "fact_id": fact_id,
            "found": False,
            "policy": dict(BITEMPORAL_FACT_GRAPH_POLICY),
            "lineage": [],
            "superseded_by": [],
        }

    lineage: list[BitemporalFact] = []
    seen: set[str] = set()
    stack = list(target.supersedes)
    while stack:
        current_id = stack.pop(0)
        if current_id in seen:
            continue
        seen.add(current_id)
        current = by_id.get(current_id)
        if current is None:
            continue
        lineage.append(current)
        stack.extend(current.supersedes)

    superseded_by = [fact for fact in normalized if target.fact_id in fact.supersedes]
    return {
        "fact_id": fact_id,
        "found": True,
        "fact": target.to_json(),
        "lineage": [fact.to_json() for fact in lineage],
        "superseded_by": [fact.to_json() for fact in sorted(superseded_by, key=_fact_sort_key)],
        "policy": dict(BITEMPORAL_FACT_GRAPH_POLICY),
    }


def _fact_sort_key(fact: BitemporalFact) -> tuple[datetime, datetime, float, str]:
    return (
        fact.valid_from or datetime.min.replace(tzinfo=UTC),
        fact.system_created_at or datetime.min.replace(tzinfo=UTC),
        fact.confidence,
        fact.fact_id,
    )


def _coerce_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if not value:
        return None
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"Invalid datetime: {value}") from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _require_datetime(value: str | datetime, name: str) -> datetime:
    parsed = _coerce_datetime(value)
    if parsed is None:
        raise ValueError(f"{name} is required")
    return parsed


def _datetime_to_json(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _contradiction_group_id(subject: str, predicate: str, project_id: str | None) -> str:
    return "|".join((project_id or "*", subject, predicate))
