"""Helpers for mirroring built-in memory writes to external memory providers."""

from __future__ import annotations

import json
from typing import Any


_SUCCESSFUL_MEMORY_ACTIONS = {"add", "replace"}


def successful_memory_tool_payload(function_result: str) -> dict[str, Any] | None:
    """Parse a built-in memory tool result, returning payload only on success."""
    try:
        payload = json.loads(function_result)
    except Exception:
        return None
    if isinstance(payload, dict) and payload.get("success") is True:
        return payload
    return None


def mirror_builtin_memory_write(
    agent: Any,
    *,
    action: str,
    target: str,
    content: str,
    function_result: str,
    task_id: str | None,
    tool_call_id: str | None,
    old_text: str | None = None,
) -> None:
    """Notify external memory providers only after the canonical memory write succeeds.

    The built-in memory tool is the source of truth for curated MEMORY.md/USER.md
    writes.  External providers must not mirror rejected writes, ambiguous
    replacements, or blocked injection/exfiltration payloads.  For replacements,
    ``old_text`` is only the user-provided match substring; the memory tool's
    successful payload carries the resolved full previous entry as
    ``replaced_entry`` so providers can supersede the exact mirrored fact.
    """
    if not getattr(agent, "_memory_manager", None) or action not in _SUCCESSFUL_MEMORY_ACTIONS:
        return

    payload = successful_memory_tool_payload(function_result)
    if payload is None:
        return

    try:
        metadata = agent._build_memory_write_metadata(
            task_id=task_id,
            tool_call_id=tool_call_id,
        )
        if action == "replace":
            if old_text:
                metadata["old_text"] = old_text
            replaced_entry = payload.get("replaced_entry")
            if isinstance(replaced_entry, str) and replaced_entry.strip():
                metadata["resolved_old_text"] = replaced_entry

        agent._memory_manager.on_memory_write(
            action,
            target,
            content,
            metadata=metadata,
        )
    except Exception:
        pass
