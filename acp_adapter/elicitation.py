"""ACP elicitation helpers.

This module intentionally keeps ACP elicitation-specific behavior isolated from
permission/authorization handling. Capability detection accepts generated SDK
models as well as dict-like fallback data because older SDKs or clients may
preserve unstable capability fields in metadata.
"""

from __future__ import annotations

from typing import Any

__all__ = ["supports_form_elicitation"]


def _get_attr_or_key(value: Any, key: str, default: Any = None) -> Any:
    if value is None:
        return default
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _model_dump(value: Any) -> dict[str, Any] | None:
    dump = getattr(value, "model_dump", None)
    if not callable(dump):
        return None
    try:
        data = dump(by_alias=True, exclude_none=True)
    except TypeError:
        data = dump()
    return data if isinstance(data, dict) else None


def _metadata_elicitation(client_capabilities: object) -> Any:
    for metadata_key in ("meta", "_meta", "field_meta"):
        meta = _get_attr_or_key(client_capabilities, metadata_key)
        elicitation = _get_attr_or_key(meta, "elicitation")
        if elicitation is not None:
            return elicitation
        elicitation = _get_attr_or_key(meta, "acp.elicitation")
        if elicitation is not None:
            return elicitation
    return None


def supports_form_elicitation(client_capabilities: object) -> bool:
    """Return whether ACP client capabilities advertise form elicitation."""
    if client_capabilities is None:
        return False

    elicitation = _get_attr_or_key(client_capabilities, "elicitation")
    if elicitation is None:
        elicitation = _metadata_elicitation(client_capabilities)

    if elicitation is None:
        return False

    if isinstance(elicitation, dict):
        if elicitation == {}:
            return True
        return "form" in elicitation

    if getattr(elicitation, "form", None) is not None:
        return True

    data = _model_dump(elicitation)
    if data is not None:
        return data == {} or "form" in data

    return False
