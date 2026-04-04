from __future__ import annotations

import json
import keyword
import os
import re
from typing import Any

from mcp.server.fastmcp import FastMCP

from agent.claude_cli_agent_bridge import call_agent_loop_tool
from model_tools import get_tool_definitions, handle_function_call

_AGENT_LOOP_TOOLS = {
    "clarify",
    "todo",
    "memory",
    "session_search",
    "delegate_task",
}
_TYPE_MAP = {
    "string": "str | None",
    "integer": "int | None",
    "number": "float | None",
    "boolean": "bool | None",
    "array": "list[Any] | None",
    "object": "dict[str, Any] | None",
}
_IDENTIFIER_RE = re.compile(r"[^0-9a-zA-Z_]")


def _safe_identifier(name: str, used: set[str]) -> str:
    candidate = _IDENTIFIER_RE.sub("_", name.strip()) or "arg"
    if candidate[0].isdigit():
        candidate = f"arg_{candidate}"
    if keyword.iskeyword(candidate):
        candidate = f"{candidate}_arg"
    original = candidate
    index = 2
    while candidate in used:
        candidate = f"{original}_{index}"
        index += 1
    used.add(candidate)
    return candidate


def _annotation_for_schema(prop_schema: dict[str, Any]) -> str:
    schema_type = prop_schema.get("type")
    if isinstance(schema_type, list):
        schema_type = next((item for item in schema_type if item != "null"), None)
    return _TYPE_MAP.get(schema_type or "string", "Any")


def _bridgeable_tool_defs(*, enabled_toolsets: list[str] | None, disabled_toolsets: list[str] | None) -> list[dict[str, Any]]:
    return get_tool_definitions(
        enabled_toolsets=enabled_toolsets,
        disabled_toolsets=disabled_toolsets,
        quiet_mode=True,
    )


def _make_tool_callable(
    tool_schema: dict[str, Any],
    *,
    task_id: str | None,
    enabled_tools: list[str],
    agent_loop_bridge: dict[str, str] | None,
) -> Any:
    function_schema = tool_schema["function"]
    tool_name = function_schema["name"]
    parameters = function_schema.get("parameters") or {}
    properties = parameters.get("properties") or {}
    required = set(parameters.get("required") or [])

    used_names: set[str] = set()
    arg_mapping: list[tuple[str, str]] = []
    signature_parts: list[str] = []
    globals_dict: dict[str, Any] = {
        "Any": Any,
        "call_agent_loop_tool": call_agent_loop_tool,
        "handle_function_call": handle_function_call,
        "json": json,
        "_task_id": task_id,
        "_enabled_tools": enabled_tools,
        "_tool_name": tool_name,
        "_required_names": required,
        "_agent_loop_bridge": agent_loop_bridge,
        "_AGENT_LOOP_TOOLS": _AGENT_LOOP_TOOLS,
    }

    for prop_name, prop_schema in properties.items():
        py_name = _safe_identifier(prop_name, used_names)
        arg_mapping.append((py_name, prop_name))
        annotation_expr = _annotation_for_schema(prop_schema)
        globals_dict[f"_ann_{py_name}"] = eval(annotation_expr, {"Any": Any})
        if prop_name in required:
            signature_parts.append(f"{py_name}: _ann_{py_name}")
        else:
            signature_parts.append(f"{py_name}: _ann_{py_name} = None")

    assignment_lines = []
    for py_name, prop_name in arg_mapping:
        assignment_lines.append(
            "    if {py_name} is not None or {prop_name!r} in _required_names:\n"
            "        payload[{prop_name!r}] = {py_name}".format(py_name=py_name, prop_name=prop_name)
        )

    signature = ", ".join(signature_parts)
    if signature:
        signature = f"{signature}, "

    source = (
        f"def _tool({signature}__tool_call_context__: str | None = None) -> str:\n"
        "    payload = {}\n"
        + ("\n".join(assignment_lines) + "\n" if assignment_lines else "")
        + "    if __tool_call_context__:\n"
        + "        payload.setdefault('_bridge_context', __tool_call_context__)\n"
        + "    if _tool_name in _AGENT_LOOP_TOOLS:\n"
        + "        if not _agent_loop_bridge:\n"
        + "            raise RuntimeError(f'Agent-loop bridge unavailable for {_tool_name}.')\n"
        + "        return call_agent_loop_tool(_tool_name, payload, host=_agent_loop_bridge['host'], port=int(_agent_loop_bridge['port']), authkey_hex=_agent_loop_bridge['authkey'])\n"
        + "    return handle_function_call(_tool_name, payload, task_id=_task_id, enabled_tools=_enabled_tools)\n"
    )
    namespace: dict[str, Any] = {}
    exec(source, globals_dict, namespace)
    tool_fn = namespace["_tool"]
    tool_fn.__name__ = f"bridge_{tool_name.replace('-', '_')}"
    tool_fn.__doc__ = function_schema.get("description") or f"Hermes bridged tool: {tool_name}"
    return tool_fn


def create_claude_cli_tool_bridge(*, enabled_toolsets: list[str] | None = None, disabled_toolsets: list[str] | None = None, task_id: str | None = None, agent_loop_bridge: dict[str, str] | None = None) -> FastMCP:
    mcp = FastMCP(
        "hermes-tools",
        instructions=(
            "Hermes Agent tool bridge for Claude CLI. Call these tools instead of "
            "describing hypothetical tool usage."
        ),
    )
    tool_defs = _bridgeable_tool_defs(enabled_toolsets=enabled_toolsets, disabled_toolsets=disabled_toolsets)
    enabled_tools = [tool_def["function"]["name"] for tool_def in tool_defs]
    for tool_def in tool_defs:
        function_schema = tool_def["function"]
        mcp.tool(
            name=function_schema["name"],
            description=function_schema.get("description") or function_schema["name"],
        )(
            _make_tool_callable(tool_def, task_id=task_id, enabled_tools=enabled_tools, agent_loop_bridge=agent_loop_bridge)
        )
    return mcp


def run_stdio_bridge() -> None:
    enabled_toolsets = json.loads(os.getenv("HERMES_CLAUDE_BRIDGE_ENABLED_TOOLSETS", "null"))
    disabled_toolsets = json.loads(os.getenv("HERMES_CLAUDE_BRIDGE_DISABLED_TOOLSETS", "null"))
    task_id = os.getenv("HERMES_CLAUDE_BRIDGE_TASK_ID") or None
    host = os.getenv("HERMES_AGENT_BRIDGE_HOST", "").strip()
    port = os.getenv("HERMES_AGENT_BRIDGE_PORT", "").strip()
    authkey = os.getenv("HERMES_AGENT_BRIDGE_AUTHKEY", "").strip()
    agent_loop_bridge = None
    if host and port and authkey:
        agent_loop_bridge = {"host": host, "port": port, "authkey": authkey}
    server = create_claude_cli_tool_bridge(
        enabled_toolsets=enabled_toolsets,
        disabled_toolsets=disabled_toolsets,
        task_id=task_id,
        agent_loop_bridge=agent_loop_bridge,
    )
    server.run()


if __name__ == "__main__":
    run_stdio_bridge()
