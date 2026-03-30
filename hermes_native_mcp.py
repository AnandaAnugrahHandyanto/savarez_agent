"""Local MCP bridge that exposes selected Hermes-native tools to Claude Code.

This module serves two roles:

1. Shared helper functions used by the Claude Code CLI backend to decide which
   Hermes-native tools should be exposed through MCP.
2. A tiny stdio MCP server that dynamically wraps registry-backed Hermes tools
   so Claude Code can call them during `claude -p` runs.
"""

from __future__ import annotations

import inspect
import json
import keyword
import os
import re
from typing import Any

_DEFAULT_SERVER_NAME = "hermes_native"
_CATALOG_TOOL_NAME = "hermes_list_native_tools"
_DEFAULT_TOOL_SELECTION = "session_search"
_DISABLED_VALUES = {"0", "false", "none", "off", "disabled", "no"}
_ALL_VALUES = {"*", "all"}


def _load_registry():
    # Import model_tools for tool-module side effects before accessing registry.
    import model_tools  # noqa: F401
    from tools.registry import registry

    return registry


def _split_tool_selection(raw_selection: str | None) -> list[str]:
    if raw_selection is None:
        raw_selection = _DEFAULT_TOOL_SELECTION

    value = str(raw_selection).strip()
    if not value:
        value = _DEFAULT_TOOL_SELECTION

    lowered = value.lower()
    if lowered in _DISABLED_VALUES:
        return []
    if lowered in _ALL_VALUES:
        return ["*"]

    return [part.strip() for part in value.split(",") if part.strip()]


def resolve_requested_tool_names(raw_selection: str | None) -> list[str]:
    """Resolve a comma-separated selection into known Hermes tool names."""
    registry = _load_registry()
    requested = _split_tool_selection(raw_selection)
    if not requested:
        return []
    if requested == ["*"]:
        return registry.get_all_tool_names()

    available = set(registry.get_all_tool_names())
    selected: list[str] = []
    for name in requested:
        if name in available and name not in selected:
            selected.append(name)
    return selected


def get_catalog_tool_name() -> str:
    return _CATALOG_TOOL_NAME


def build_claude_mcp_tool_names(
    tool_names: list[str],
    *,
    server_name: str = _DEFAULT_SERVER_NAME,
) -> list[str]:
    """Return Claude-Code-style MCP tool identifiers."""
    resolved: list[str] = []
    for tool_name in [*tool_names, _CATALOG_TOOL_NAME]:
        claude_name = f"mcp__{server_name}__{tool_name}"
        if claude_name not in resolved:
            resolved.append(claude_name)
    return resolved


def build_hermes_tool_awareness_text(tool_names: list[str]) -> str:
    """Prompt hint so Claude knows which Hermes-native tools are bridged."""
    bridged = [name for name in tool_names if name]
    bridged_display = ", ".join([_CATALOG_TOOL_NAME, *bridged]) if bridged else _CATALOG_TOOL_NAME
    return (
        "Hermes-native MCP tools are available in this run. "
        f"Current bridged Hermes tools: {bridged_display}. "
        f"Use {_CATALOG_TOOL_NAME} if you need to inspect the wider Hermes tool catalog. "
        "If you need a Hermes-native capability that is not bridged here, tell the user exactly "
        "which Hermes tool should be added."
    )


def _sanitize_identifier(name: str) -> str:
    normalized = re.sub(r"\W+", "_", str(name).strip())
    if not normalized:
        normalized = "arg"
    if normalized[0].isdigit():
        normalized = f"arg_{normalized}"
    if keyword.iskeyword(normalized):
        normalized = f"{normalized}_value"
    return normalized


def _json_schema_to_annotation(schema: dict[str, Any] | None) -> Any:
    if not isinstance(schema, dict):
        return str

    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        schema_type = next((item for item in schema_type if item != "null"), None)

    if schema_type == "string":
        return str
    if schema_type == "integer":
        return int
    if schema_type == "number":
        return float
    if schema_type == "boolean":
        return bool
    if schema_type == "array":
        return list
    if schema_type == "object":
        return dict
    return str


def _build_signature_for_schema(parameters_schema: dict[str, Any]) -> tuple[inspect.Signature, dict[str, str]]:
    properties = parameters_schema.get("properties")
    if not isinstance(properties, dict):
        return inspect.Signature(), {}

    required = set(parameters_schema.get("required") or [])
    parameters: list[inspect.Parameter] = []
    sanitized_to_original: dict[str, str] = {}

    for original_name, property_schema in properties.items():
        safe_name = _sanitize_identifier(original_name)
        while safe_name in sanitized_to_original:
            safe_name = f"{safe_name}_value"
        sanitized_to_original[safe_name] = original_name

        annotation = _json_schema_to_annotation(property_schema if isinstance(property_schema, dict) else None)
        default = inspect.Parameter.empty if original_name in required else None
        parameters.append(
            inspect.Parameter(
                safe_name,
                kind=inspect.Parameter.KEYWORD_ONLY,
                annotation=annotation,
                default=default,
            )
        )

    return inspect.Signature(parameters), sanitized_to_original


def _list_native_tools() -> str:
    registry = _load_registry()
    bridged = resolve_requested_tool_names(os.getenv("HERMES_NATIVE_MCP_TOOLS"))
    results = []
    for entry in registry.iter_entries():
        description = entry.description or entry.schema.get("description", "")
        results.append(
            {
                "name": entry.name,
                "toolset": entry.toolset,
                "description": description,
                "bridged_via_mcp": entry.name in bridged,
            }
        )

    payload = {
        "success": True,
        "count": len(results),
        "bridged_tools": bridged,
        "results": results,
        "message": (
            "Hermes-native tools registered in this environment. "
            "bridged_via_mcp=true means Claude Code can call that tool directly in this run."
        ),
    }
    return json.dumps(payload, ensure_ascii=False)


def _build_context_kwargs() -> tuple[dict[str, Any], Any | None]:
    context: dict[str, Any] = {}
    session_id = os.getenv("HERMES_NATIVE_MCP_SESSION_ID", "").strip() or None
    user_task = os.getenv("HERMES_NATIVE_MCP_USER_TASK", "").strip() or None

    db = None
    try:
        from hermes_state import SessionDB

        db = SessionDB()
        context["db"] = db
    except Exception:
        db = None

    if session_id:
        context["current_session_id"] = session_id
        context["task_id"] = session_id
    if user_task:
        context["user_task"] = user_task
    return context, db


def _create_registry_wrapper(tool_name: str):
    registry = _load_registry()
    entry = registry.get_entry(tool_name)
    if entry is None:
        raise KeyError(tool_name)

    parameters_schema = entry.schema.get("parameters") or {}
    signature, name_map = _build_signature_for_schema(parameters_schema)
    description = entry.description or entry.schema.get("description", "")

    def _tool_wrapper(**kwargs: Any) -> str:
        original_kwargs = {
            name_map.get(key, key): value
            for key, value in kwargs.items()
            if value is not None
        }
        context_kwargs, db_handle = _build_context_kwargs()
        try:
            return registry.dispatch(tool_name, original_kwargs, **context_kwargs)
        finally:
            if db_handle is not None:
                try:
                    db_handle.close()
                except Exception:
                    pass

    _tool_wrapper.__name__ = tool_name
    _tool_wrapper.__doc__ = description or f"Hermes-native tool bridge for {tool_name}."
    _tool_wrapper.__signature__ = signature
    return _tool_wrapper


def build_mcp_server():
    """Build a FastMCP server with a catalog tool plus selected Hermes tools."""
    from mcp.server.fastmcp import FastMCP

    server = FastMCP(_DEFAULT_SERVER_NAME)

    def hermes_list_native_tools() -> str:
        """List Hermes-native tools registered in this environment."""
        return _list_native_tools()

    server.tool()(hermes_list_native_tools)

    for tool_name in resolve_requested_tool_names(os.getenv("HERMES_NATIVE_MCP_TOOLS")):
        server.tool()(_create_registry_wrapper(tool_name))

    return server


def main() -> int:
    server = build_mcp_server()
    server.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
