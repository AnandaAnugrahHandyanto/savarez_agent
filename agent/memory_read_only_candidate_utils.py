from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from copy import deepcopy
from typing import Any


READ_ONLY_POLICY_BASE = {
    "read_only": True,
    "would_write_memory": False,
    "would_modify_config": False,
    "would_write_graph": False,
    "does_not_create_operation_events": True,
    "creates_real_proposals": False,
    "writes_proposal_files": False,
    "writes_operation_ledger": False,
    "writes_token_files": False,
    "writes_approval_audit": False,
    "invokes_real_token_write_executor": False,
    "implements_real_token_write_executor": False,
    "creates_executor_source_files": False,
}

DEFAULT_FORBIDDEN_TRUE_KEYS = (
    "token_issued",
    "approved",
    "persisted",
    "submitted",
    "written",
    "created",
    "created_real_proposal",
    "created_operation_event",
    "creates_real_proposals",
    "writes_proposal_files",
    "writes_operation_ledger",
    "writes_token_files",
    "writes_approval_audit",
    "issues_real_approval_tokens",
    "persists_approvals",
    "applies_proposals",
    "submits_to_governance",
    "converts_to_real_proposal",
    "converted_to_real_proposal",
    "would_write_memory",
    "would_modify_config",
    "would_write_graph",
    "invokes_real_token_write_executor",
    "implements_real_token_write_executor",
    "creates_executor_source_files",
    "creates_executor_tests",
)

DEFAULT_PREVIEW_FIELDS = (
    "approval_token_record_preview",
    "approval_audit_record_preview",
    "token_target_paths_preview",
    "proposal_record_preview",
    "operation_ledger_preview",
    "target_paths_preview",
)

DEFAULT_WRITE_PREVIEW_FIELDS = (
    "approval_token_write_payload_preview",
    "approval_audit_write_payload_preview",
    "token_write_target_paths_preview",
)


def as_mapping(value: Any) -> dict[str, Any]:
    """Return a deep-copied dict for mapping-like values, otherwise an empty dict."""
    return deepcopy(dict(value)) if isinstance(value, Mapping) else {}


def as_list(value: Any) -> list[Any]:
    """Return a deep-copied list for list or tuple values, otherwise an empty list."""
    return deepcopy(list(value)) if isinstance(value, (list, tuple)) else []


def _mapping_view(value: Any) -> Mapping[Any, Any]:
    """Return a read-only mapping view without copying nested candidate graphs."""
    return value if isinstance(value, Mapping) else {}


def deep_copy_mapping(value: Any) -> dict[str, Any]:
    """Return a deep-copied mapping without sharing nested values."""
    return as_mapping(value)


def copy_fields(source: Mapping[str, Any], fields: Iterable[str]) -> dict[str, Any]:
    source_mapping = as_mapping(source)
    copied: dict[str, Any] = {}
    for field in _iter_keys(fields):
        if field in source_mapping:
            copied[field] = deepcopy(source_mapping[field])
    return copied


def copy_source_lineage(source: Mapping[str, Any], source_keys: Iterable[str]) -> dict[str, Any]:
    return copy_fields(source, source_keys)


def validate_required_keys(
    candidate: Mapping[str, Any],
    required_keys: Iterable[str],
) -> list[str]:
    candidate_mapping = _mapping_view(candidate)
    errors = [
        f"missing_{key}"
        for key in _iter_keys(required_keys)
        if key not in candidate_mapping
    ]
    return merge_validation_errors(errors)


def validate_forbidden_true_keys(
    candidate: Mapping[str, Any],
    forbidden_keys: Iterable[str] = DEFAULT_FORBIDDEN_TRUE_KEYS,
) -> list[str]:
    candidate_mapping = _mapping_view(candidate)
    errors = [
        f"{key}_must_be_false"
        for key in _iter_keys(forbidden_keys)
        if candidate_mapping.get(key) is True
    ]
    return merge_validation_errors(errors)


def validate_forbidden_true_keys_false_or_absent(
    candidate: Mapping[str, Any],
    forbidden_keys: Iterable[str] = DEFAULT_FORBIDDEN_TRUE_KEYS,
) -> list[str]:
    candidate_mapping = _mapping_view(candidate)
    errors = [
        f"{key}_must_be_false_or_absent"
        for key in _iter_keys(forbidden_keys)
        if candidate_mapping.get(key) is True
    ]
    return merge_validation_errors(errors)


def validate_policy_flags(
    policy: Mapping[str, Any],
    expected_flags: Mapping[str, bool] = READ_ONLY_POLICY_BASE,
) -> list[str]:
    policy_mapping = _mapping_view(policy)
    errors: list[str] = []
    for key, expected in _mapping_view(expected_flags).items():
        if expected is True and policy_mapping.get(key) is not True:
            errors.append(f"policy_{key}_must_be_true")
        elif expected is False and policy_mapping.get(key) is not False:
            errors.append(f"policy_{key}_must_be_false")
    return merge_validation_errors(errors)


def validate_preview_integrity(
    candidate: Mapping[str, Any],
    preview_fields: Iterable[str] = DEFAULT_PREVIEW_FIELDS,
    forbidden_true_keys: Iterable[str] = DEFAULT_FORBIDDEN_TRUE_KEYS,
) -> list[str]:
    return _validate_preview_fields(candidate, preview_fields, forbidden_true_keys)


def validate_preview_forbidden_true_keys_false_or_absent(
    candidate: Mapping[str, Any],
    preview_fields: Iterable[str] = DEFAULT_PREVIEW_FIELDS,
    forbidden_true_keys: Iterable[str] = DEFAULT_FORBIDDEN_TRUE_KEYS,
) -> list[str]:
    candidate_mapping = _mapping_view(candidate)
    errors: list[str] = []
    for field in _iter_keys(preview_fields):
        preview = candidate_mapping.get(field)
        if not isinstance(preview, Mapping):
            continue
        for key in _iter_keys(forbidden_true_keys):
            if preview.get(key) is True:
                errors.append(f"{field}_{key}_must_be_false_or_absent")
    return merge_validation_errors(errors)


def validate_write_preview_integrity(
    candidate: Mapping[str, Any],
    write_preview_fields: Iterable[str] = DEFAULT_WRITE_PREVIEW_FIELDS,
    forbidden_true_keys: Iterable[str] = DEFAULT_FORBIDDEN_TRUE_KEYS,
) -> list[str]:
    return _validate_preview_fields(candidate, write_preview_fields, forbidden_true_keys)


def build_stable_digest(
    prefix: str,
    payload: Any,
    ignored_keys: Iterable[str] | None = None,
) -> str:
    ignored = {str(key) for key in _iter_keys(ignored_keys or ())}
    normalized = _normalize_for_digest(payload, ignored)
    encoded = json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def summarize_candidates(
    candidates: Iterable[Mapping[str, Any]],
    status_key: str,
    type_key: str | None = None,
    block_type_key: str = "block_type",
) -> dict[str, Any]:
    candidate_list = _iter_candidates(candidates)
    summary: dict[str, Any] = {
        "total": len(candidate_list),
        "by_status": _count_by_key(candidate_list, status_key),
        "by_block_type": _count_by_key(candidate_list, block_type_key),
    }
    if type_key is not None:
        summary["by_type"] = _count_by_key(candidate_list, type_key)
    return summary


def merge_validation_errors(*error_lists: Iterable[str]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for error_list in error_lists:
        for error in as_list(error_list):
            if error is None:
                continue
            error_text = str(error)
            if error_text not in seen:
                seen.add(error_text)
                errors.append(error_text)
    return errors


def _validate_preview_fields(
    candidate: Mapping[str, Any],
    preview_fields: Iterable[str],
    forbidden_true_keys: Iterable[str],
) -> list[str]:
    candidate_mapping = _mapping_view(candidate)
    forbidden = {str(key) for key in _iter_keys(forbidden_true_keys)}
    errors: list[str] = []
    for field in _iter_keys(preview_fields):
        preview = candidate_mapping.get(field)
        if not isinstance(preview, Mapping):
            continue
        if preview.get("preview_only") is not True:
            errors.append(f"{field}_must_be_preview_only")
        for key, value in preview.items():
            key_text = str(key)
            if value is True and _is_forbidden_true_key(key_text, forbidden):
                errors.append(f"{field}_{key_text}_must_not_be_true")
    return merge_validation_errors(errors)


def _is_forbidden_true_key(key: str, forbidden: set[str]) -> bool:
    return (
        key in forbidden
        or key in {"created", "written", "token_issued", "approved", "persisted"}
        or "created" in key
        or "written" in key
        or key.startswith("writes_")
    )


def _count_by_key(candidates: list[Mapping[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for candidate in candidates:
        candidate_mapping = _mapping_view(candidate)
        value = str(candidate_mapping.get(key))
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _iter_candidates(candidates: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    if isinstance(candidates, (str, bytes, bytearray, Mapping)):
        return []
    try:
        return list(candidates)
    except TypeError:
        return []


def _iter_keys(keys: Iterable[str] | str) -> tuple[str, ...]:
    if keys is None:
        return ()
    if isinstance(keys, str):
        return (keys,)
    try:
        return tuple(str(key) for key in keys)
    except TypeError:
        return (str(keys),)


def _normalize_for_digest(value: Any, ignored_keys: set[str]) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _normalize_for_digest(item, ignored_keys)
            for key, item in sorted(value.items(), key=lambda item: str(item[0]))
            if str(key) not in ignored_keys
        }
    if isinstance(value, (list, tuple)):
        return [_normalize_for_digest(item, ignored_keys) for item in value]
    if isinstance(value, (set, frozenset)):
        normalized_items = [_normalize_for_digest(item, ignored_keys) for item in value]
        return sorted(
            normalized_items,
            key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")),
        )
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


__all__ = [
    "READ_ONLY_POLICY_BASE",
    "DEFAULT_FORBIDDEN_TRUE_KEYS",
    "DEFAULT_PREVIEW_FIELDS",
    "DEFAULT_WRITE_PREVIEW_FIELDS",
    "as_mapping",
    "as_list",
    "deep_copy_mapping",
    "copy_fields",
    "copy_source_lineage",
    "validate_required_keys",
    "validate_forbidden_true_keys",
    "validate_forbidden_true_keys_false_or_absent",
    "validate_policy_flags",
    "validate_preview_integrity",
    "validate_preview_forbidden_true_keys_false_or_absent",
    "validate_write_preview_integrity",
    "build_stable_digest",
    "summarize_candidates",
    "merge_validation_errors",
]
