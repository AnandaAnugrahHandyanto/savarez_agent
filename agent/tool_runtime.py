"""Tool runtime helpers for normalizing tool execution results while preserving legacy tool message compatibility."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolFailure:
    category: str
    message: str
    retriable: bool
    suggested_next_step: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolExecutionEnvelope:
    tool_name: str
    ok: bool
    content: str
    structured_content: dict[str, Any] = field(default_factory=dict)
    failure: ToolFailure | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def _coerce_content(raw_result: Any) -> str:
    if raw_result is None:
        return ""
    if isinstance(raw_result, str):
        return raw_result
    if isinstance(raw_result, (dict, list)):
        try:
            return json.dumps(raw_result, ensure_ascii=False)
        except TypeError:
            return str(raw_result)
    return str(raw_result)


def _looks_like_error_payload(parsed: Any) -> tuple[bool, str | None, dict[str, Any]]:
    if not isinstance(parsed, dict):
        return False, None, {}

    error_value = parsed.get("error")
    success_value = parsed.get("success")
    status_value = parsed.get("status")

    message = None
    if isinstance(error_value, str) and error_value.strip():
        message = error_value.strip()
    elif isinstance(parsed.get("message"), str) and parsed.get("message", "").strip():
        message = parsed.get("message", "").strip()

    is_error = False
    if message and success_value is False:
        is_error = True
    elif message and isinstance(status_value, str) and status_value.lower() in {"error", "failed", "failure"}:
        is_error = True
    elif message and "error" in parsed:
        is_error = True

    details = {}
    for key in ("error", "success", "status", "code", "type"):
        if key in parsed:
            details[key] = parsed[key]

    return is_error, message, details


def normalize_tool_result(
    tool_name: str,
    raw_result: Any,
    *,
    duration_seconds: float | None = None,
    source: str | None = None,
) -> ToolExecutionEnvelope:
    content = _coerce_content(raw_result)
    metadata: dict[str, Any] = {}
    if duration_seconds is not None:
        metadata["duration_seconds"] = round(float(duration_seconds), 6)
    if source:
        metadata["source"] = source

    structured_content: dict[str, Any] = {}
    failure: ToolFailure | None = None
    ok = True

    try:
        parsed = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        parsed = None

    if isinstance(parsed, dict):
        structured_content = parsed
        is_error, message, details = _looks_like_error_payload(parsed)
        if is_error:
            ok = False
            failure = ToolFailure(
                category="tool_error",
                message=message or f"Tool '{tool_name}' reported an error.",
                retriable=False,
                details=details,
            )

    if not ok and failure is None:
        failure = ToolFailure(
            category="tool_error",
            message=f"Tool '{tool_name}' reported an error.",
            retriable=False,
        )

    return ToolExecutionEnvelope(
        tool_name=tool_name,
        ok=ok,
        content=content,
        structured_content=structured_content,
        failure=failure,
        metadata=metadata,
    )


def normalize_tool_failure(
    tool_name: str,
    error: Exception | str,
    *,
    category: str = "execution_error",
    retriable: bool = False,
    suggested_next_step: str | None = None,
    details: dict[str, Any] | None = None,
    duration_seconds: float | None = None,
    source: str | None = None,
) -> ToolExecutionEnvelope:
    message = str(error)
    failure = ToolFailure(
        category=category,
        message=message,
        retriable=retriable,
        suggested_next_step=suggested_next_step,
        details=details or {},
    )
    metadata: dict[str, Any] = {}
    if duration_seconds is not None:
        metadata["duration_seconds"] = round(float(duration_seconds), 6)
    if source:
        metadata["source"] = source
    content = f"Error executing tool '{tool_name}': {message}"
    return ToolExecutionEnvelope(
        tool_name=tool_name,
        ok=False,
        content=content,
        failure=failure,
        metadata=metadata,
    )


def envelope_to_legacy_content(envelope: ToolExecutionEnvelope) -> str:
    return envelope.content
