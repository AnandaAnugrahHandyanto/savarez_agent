"""Companion audit/context snapshots for dashboard-visible oversight.

This module writes append-only JSONL records under ``$HERMES_HOME/audit`` so
profile-scoped companion agents have a durable, inspectable trail of what
context was sent to the model on each turn/API call.
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from hermes_constants import get_hermes_home

_MAX_PREVIEW_CHARS = 4000
_MAX_RESULT_PREVIEW_CHARS = 2000


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today_file(root: Path | None = None) -> Path:
    home = root or get_hermes_home()
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return home / "audit" / f"{day}.jsonl"


def _safe_preview(value: Any, limit: int = _MAX_PREVIEW_CHARS) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, ensure_ascii=False, sort_keys=True)
        except Exception:
            text = str(value)
    if len(text) <= limit:
        return text
    return text[:limit] + f"… [truncated {len(text) - limit} chars]"


def _content_text(message: dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)
    return _safe_preview(content)


def _tool_names(tools: Iterable[Any] | None) -> list[str]:
    names: list[str] = []
    for tool in tools or []:
        name = None
        if isinstance(tool, dict):
            if isinstance(tool.get("function"), dict):
                name = tool["function"].get("name")
            name = name or tool.get("name")
        if isinstance(name, str) and name and name not in names:
            names.append(name)
    return sorted(names)


def _parse_arguments(raw: Any) -> Any:
    if not isinstance(raw, str):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return raw


def _extract_tool_attempts(request_messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results_by_id: dict[str, str] = {}
    for msg in request_messages:
        if msg.get("role") == "tool":
            call_id = msg.get("tool_call_id")
            if isinstance(call_id, str):
                results_by_id[call_id] = _safe_preview(
                    _content_text(msg),
                    limit=_MAX_RESULT_PREVIEW_CHARS,
                )

    attempts: list[dict[str, Any]] = []
    for msg in request_messages:
        for tc in msg.get("tool_calls") or []:
            if not isinstance(tc, dict):
                continue
            raw_fn = tc.get("function")
            fn: dict[str, Any] = raw_fn if isinstance(raw_fn, dict) else {}
            call_id = tc.get("id")
            entry = {
                "id": call_id or "",
                "name": fn.get("name") or tc.get("name") or "unknown",
                "arguments": _parse_arguments(fn.get("arguments")),
            }
            if isinstance(call_id, str) and call_id in results_by_id:
                entry["result_preview"] = results_by_id[call_id]
            attempts.append(entry)
    return attempts


def resolve_active_profile_name(root: Path | None = None) -> str:
    """Return profile name for the current Hermes home.

    ``~/.hermes`` -> ``default``; ``~/.hermes/profiles/<name>`` -> ``<name>``.
    """
    import os

    explicit = os.environ.get("HERMES_PROFILE", "").strip()
    if explicit:
        return explicit
    try:
        home = (root or get_hermes_home()).resolve()
        parts = home.parts
        if len(parts) >= 2 and parts[-2] == "profiles":
            return parts[-1]
    except Exception:
        pass
    return "default"


def write_turn_snapshot(
    *,
    session_id: str,
    profile: str | None = None,
    platform: str | None = None,
    user_message: str | None = None,
    assistant_response: str | None = None,
    system_prompt: str | None = None,
    request_messages: list[dict[str, Any]] | None = None,
    tools: Iterable[Any] | None = None,
    enabled_toolsets: list[str] | None = None,
    memory_context: str | None = None,
    plugin_context: str | None = None,
    api_call_count: int | None = None,
    approx_input_tokens: int | None = None,
    request_char_count: int | None = None,
    model: str | None = None,
    provider: str | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Append one companion audit/context snapshot and return the event."""
    request_messages = request_messages or []
    system_prompt = system_prompt or ""
    tool_names = _tool_names(tools)
    event = {
        "schema_version": 1,
        "event": "turn_context_snapshot",
        "timestamp": _utc_timestamp(),
        "timestamp_unix": time.time(),
        "session_id": session_id,
        "profile": profile or "default",
        "platform": platform or "",
        "user_message": _safe_preview(user_message),
        "assistant_response": _safe_preview(assistant_response),
        "model": model or "",
        "provider": provider or "",
        "context": {
            "system_prompt_sha256": hashlib.sha256(system_prompt.encode("utf-8")).hexdigest() if system_prompt else "",
            "system_prompt_char_count": len(system_prompt),
            "system_prompt_preview": _safe_preview(system_prompt),
            "memory_context_present": bool(memory_context),
            "memory_context_preview": _safe_preview(memory_context),
            "plugin_context_present": bool(plugin_context),
            "plugin_context_preview": _safe_preview(plugin_context),
            "enabled_toolsets": list(enabled_toolsets or []),
        },
        "request": {
            "api_call_count": api_call_count,
            "message_count": len(request_messages),
            "approx_input_tokens": approx_input_tokens,
            "request_char_count": request_char_count,
        },
        "tools": {
            "available": tool_names,
            "available_count": len(tool_names),
        },
        "tool_attempts": _extract_tool_attempts(request_messages),
    }

    path = output_path or _today_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    return event


def iter_audit_events(root: Path | None = None) -> Iterable[dict[str, Any]]:
    audit_dir = (root or get_hermes_home()) / "audit"
    if not audit_dir.exists():
        return
    for path in sorted(audit_dir.glob("*.jsonl"), reverse=True):
        try:
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        continue
        except OSError:
            continue


def iter_session_audit_events(session_id: str, root: Path | None = None) -> Iterable[dict[str, Any]]:
    for event in iter_audit_events(root=root) or []:
        if event.get("session_id") == session_id:
            yield event
