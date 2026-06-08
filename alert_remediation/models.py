from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


EVENT_SCHEMA_VERSION = "alert.remediation/v1"
VALID_SEVERITIES = {"info", "warning", "high", "critical"}


class AlertValidationError(ValueError):
    """Raised when an alert event is missing required fields or is malformed."""


@dataclass(frozen=True)
class AlertEvent:
    schema_version: str
    source: str
    dedupe_key: str
    severity: str
    service: str
    symptom: str
    event_id: str | None = None
    host: str | None = None
    tags: list[str] = field(default_factory=list)
    first_seen: str | None = None
    last_seen: str | None = None
    count: int | None = None
    evidence: list[dict[str, Any]] = field(default_factory=list)
    runbook: str | None = None
    suggested_action: str | None = None
    links: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "AlertEvent":
        required = ("schema_version", "source", "dedupe_key", "severity", "service", "symptom")
        missing = [field_name for field_name in required if not data.get(field_name)]
        if missing:
            raise AlertValidationError(f"missing required alert field(s): {', '.join(missing)}")

        schema_version = str(data["schema_version"])
        if schema_version != EVENT_SCHEMA_VERSION:
            raise AlertValidationError(
                f"unsupported schema_version {schema_version!r}; expected {EVENT_SCHEMA_VERSION!r}"
            )

        severity = str(data["severity"]).lower()
        if severity not in VALID_SEVERITIES:
            raise AlertValidationError(
                f"unsupported severity {severity!r}; expected one of {sorted(VALID_SEVERITIES)}"
            )

        return cls(
            schema_version=schema_version,
            source=str(data["source"]),
            dedupe_key=str(data["dedupe_key"]),
            severity=severity,
            service=str(data["service"]),
            symptom=str(data["symptom"]),
            event_id=_optional_str(data.get("event_id")),
            host=_optional_str(data.get("host")),
            tags=[str(tag) for tag in data.get("tags", [])],
            first_seen=_optional_str(data.get("first_seen")),
            last_seen=_optional_str(data.get("last_seen")),
            count=_optional_int(data.get("count")),
            evidence=_list_of_dicts(data.get("evidence", []), "evidence"),
            runbook=_optional_str(data.get("runbook")),
            suggested_action=_optional_str(data.get("suggested_action")),
            links=_list_of_dicts(data.get("links", []), "links"),
            metadata=_dict_or_empty(data.get("metadata"), "metadata"),
        )


@dataclass(frozen=True)
class RouteDecision:
    action: str
    severity: str
    notify_target: str | None
    assignee: str | None
    runbooks: list[str]
    kanban_on_failure: bool
    reason: str
    matched_rule: str | None = None
    forbidden_without_approval: list[str] = field(default_factory=list)
    initial_status: str | None = None


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise AlertValidationError(f"count must be an integer, got {value!r}") from exc


def _list_of_dicts(value: Any, field_name: str) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise AlertValidationError(f"{field_name} must be a list")
    if not all(isinstance(item, dict) for item in value):
        raise AlertValidationError(f"{field_name} entries must be objects")
    return [dict(item) for item in value]


def _dict_or_empty(value: Any, field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise AlertValidationError(f"{field_name} must be an object")
    return dict(value)
