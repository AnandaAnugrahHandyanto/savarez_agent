from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, Iterable, Set

from .exceptions import PolicyViolation
from .models import Entity, Triple

VERSION = "0.2.0"
SCHEMA_VERSION = "1.0.0"
POLICY_VERSION = "edgegde-memory-policy-v1"
ADAPTER_NAME = "mempalace-ladybug-projection"

DEFAULT_ENTITY_TYPES: Set[str] = {
    "person",
    "project",
    "repo",
    "tool",
    "policy",
    "document",
    "drawer",
    "wing",
    "palace",
    "memory",
    "system",
    "domain",
    "unknown",
}

DEFAULT_PREDICATES: Set[str] = {
    "leads",
    "owns",
    "works_on",
    "depends_on",
    "uses_tool",
    "uses_model",
    "contains",
    "references",
    "located_in",
    "governed_by",
    "derived_from",
    "supersedes",
    "expires",
    "has_policy",
    "has_source",
    "has",
    "prefers",
    "values",
    "version",
    "provider",
    "runs",
    "model",
    "expects",
    "cost_conscious",
    "max_retries",
    "backoff_sequence",
    "context_length",
    "drawer_count",
    "self_audits",
    "integration",
    "works_from",
    "works_in",
}

_SECRET_KEY_NAMES = {"api_key", "token", "secret", "password", "credential", "connection_string"}


def slug(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "unknown"


def normalize_entity_id(kind: str, name: str) -> str:
    return f"{slug(kind)}:{slug(name)}"


def validate_entity(entity: Entity, allowed_types: Iterable[str]) -> None:
    allowed = set(allowed_types)
    if entity.type not in allowed:
        raise PolicyViolation(f"unknown entity type: {entity.type}")
    if not entity.id or ":" not in entity.id:
        raise PolicyViolation(f"invalid entity id: {entity.id}")


def validate_predicate(predicate: str, allowed_predicates: Iterable[str]) -> None:
    if predicate not in set(allowed_predicates):
        raise PolicyViolation(f"unknown predicate: {predicate}")


def validate_triple(triple: Triple, allowed_types: Iterable[str], allowed_predicates: Iterable[str]) -> None:
    validate_entity(triple.subject, allowed_types)
    validate_entity(triple.object, allowed_types)
    validate_predicate(triple.predicate, allowed_predicates)
    if not 0.0 <= float(triple.confidence) <= 1.0:
        raise PolicyViolation(f"confidence out of range: {triple.confidence}")


def hash_json(data: Any) -> str:
    import json

    payload = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def redact_secrets(data: Any) -> Any:
    if isinstance(data, dict):
        redacted: Dict[str, Any] = {}
        for key, value in data.items():
            if str(key).lower() in _SECRET_KEY_NAMES or "secret" in str(key).lower() or "token" in str(key).lower():
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = redact_secrets(value)
        return redacted
    if isinstance(data, list):
        return [redact_secrets(item) for item in data]
    return data
