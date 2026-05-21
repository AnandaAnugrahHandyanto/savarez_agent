from __future__ import annotations

from agent.codex_responses_adapter import _responses_tools


def _tool(name: str, parameters: dict) -> dict:
    return {"type": "function", "function": {"name": name, "parameters": parameters}}


def test_responses_tools_strip_codex_forbidden_schema_keywords_recursively():
    tools = [_tool("memory", {
        "type": "object",
        "oneOf": [{"required": ["content"]}],
        "properties": {
            "action": {"type": "string", "enum": ["add", "remove"]},
            "payload": {
                "anyOf": [
                    {"type": "object", "properties": {"x": {"type": "string"}}},
                    {"type": "null"},
                ],
            },
        },
    })]

    out = _responses_tools(tools)
    assert out is not None
    params = out[0]["parameters"]

    assert "oneOf" not in params
    assert "enum" not in params["properties"]["action"]
    assert "anyOf" not in params["properties"]["payload"]


def test_responses_tools_inject_array_items_for_codex_responses():
    tools = [_tool("mcp_dinero_dinero_create_invoice", {
        "type": "object",
        "properties": {
            "productLines": {"type": "array"},
        },
    })]

    out = _responses_tools(tools)
    assert out is not None

    assert out[0]["parameters"]["properties"]["productLines"]["items"] == {}
