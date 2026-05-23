"""Resolve Cursor SDK tool ids for Hermes display and session persistence."""

from __future__ import annotations

import json
from typing import Any, Mapping


def coerce_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("{"):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass
    return {}


def mcp_tool_name_from_payload(payload: Mapping[str, Any]) -> str:
    """Extract the concrete MCP tool id from a Cursor MCP wrapper payload."""
    if not payload:
        return ""

    for key in (
        "toolName",
        "tool_name",
        "mcpToolName",
        "mcp_tool_name",
        "functionName",
        "function_name",
    ):
        val = str(payload.get(key) or "").strip()
        if val and val.lower() not in {"mcp", "tool"}:
            return val

    server = (
        payload.get("server")
        or payload.get("serverName")
        or payload.get("server_name")
        or payload.get("mcpServer")
        or payload.get("mcp_server")
        or payload.get("provider")
    )
    tool = payload.get("tool") or payload.get("name")
    if tool:
        tool_s = str(tool).strip()
        if tool_s and tool_s.lower() not in {"mcp", "tool"}:
            if server:
                server_s = str(server).strip()
                if server_s:
                    return f"mcp_{server_s}_{tool_s}"
            return tool_s

    for nest_key in ("mcpToolCall", "mcp_tool_call", "mcp", "data", "payload"):
        nested = payload.get(nest_key)
        if isinstance(nested, Mapping):
            found = mcp_tool_name_from_payload(nested)
            if found:
                return found

    fn = payload.get("function")
    if isinstance(fn, Mapping):
        fn_name = str(fn.get("name") or "").strip()
        if fn_name and fn_name.lower() not in {"mcp", "tool"}:
            return fn_name

    return ""


def display_cursor_tool_name(name: str) -> str:
    """Normalize Cursor / MCP tool ids for Hermes scrollback and the sessions DB."""
    cleaned = (name or "").strip()
    if not cleaned or cleaned.lower() in {"tool", "mcp"}:
        return ""
    lowered = cleaned.lower()
    for prefix in (
        "mcp_hermes-tools_",
        "mcp_hermes_tools_",
        "hermes-tools_",
    ):
        if lowered.startswith(prefix):
            return cleaned[len(prefix) :]
    if lowered.startswith("mcp_") and "_" in cleaned[4:]:
        return cleaned.split("_", 2)[-1]
    return cleaned


def resolve_cursor_tool_name(
    raw_name: str,
    tc: Mapping[str, Any] | None = None,
    args: Mapping[str, Any] | None = None,
) -> str:
    """Map Cursor native + MCP wrapper events to a Hermes display tool name."""
    tc = tc or {}
    args = args or {}
    name = (raw_name or "").strip()
    if not name:
        name = str(
            tc.get("name")
            or tc.get("toolName")
            or tc.get("tool_name")
            or tc.get("tool")
            or ""
        ).strip()

    if name.lower().startswith("mcp_") and name.lower() not in {"mcp", "mcp_"}:
        display = display_cursor_tool_name(name)
        if display:
            return display

    if name.lower() in {"", "mcp", "tool"}:
        for payload in (tc, args):
            found = mcp_tool_name_from_payload(payload)
            if found:
                return display_cursor_tool_name(found)
        for key in ("input", "arguments", "args"):
            nested = coerce_mapping(tc.get(key))
            if nested:
                found = mcp_tool_name_from_payload(nested)
                if found:
                    return display_cursor_tool_name(found)

    return display_cursor_tool_name(name)
