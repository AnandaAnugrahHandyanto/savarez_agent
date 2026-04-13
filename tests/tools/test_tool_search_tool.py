"""Tests for deferred tool loading and the tool_search tool."""

import json

import pytest

from model_tools import get_tool_definitions
from tools.registry import ToolRegistry, registry


def _dummy_handler(args, **kwargs):
    return json.dumps({"ok": True})


def _schema(name: str, description: str = "") -> dict:
    return {
        "name": name,
        "description": description,
        "parameters": {"type": "object", "properties": {}},
    }


@pytest.fixture
def register_tools():
    registered = []

    def _register(
        name: str,
        *,
        toolset: str = "c2_tool_search_suite",
        description: str = "",
        search_hint: str = "",
        deferred: bool = False,
        always_load: bool = False,
    ) -> str:
        registry.register(
            name=name,
            toolset=toolset,
            schema=_schema(name, description),
            handler=_dummy_handler,
            description=description,
            search_hint=search_hint,
            deferred=deferred,
            always_load=always_load,
        )
        registered.append(name)
        return name

    yield _register

    for name in reversed(registered):
        registry.deregister(name)


def test_tool_search_finds_tools_by_name_substring(register_tools):
    name = register_tools(
        "c2_name_match_alpha_tool",
        description="Useful for exact substring matching tests.",
    )

    payload = json.loads(registry.dispatch("tool_search", {"query": "name_match_alpha"}))
    names = {item["name"] for item in payload["results"]}
    assert name in names


def test_tool_search_finds_tools_by_search_hint_keyword(register_tools):
    name = register_tools(
        "c2_hint_lookup_tool",
        description="Hidden behind a search hint.",
        search_hint="quasar orchestration pipeline",
    )

    payload = json.loads(registry.dispatch("tool_search", {"query": "quasar"}))
    names = {item["name"] for item in payload["results"]}
    assert name in names


def test_tool_search_returns_deferred_tools(register_tools):
    name = register_tools(
        "c2_deferred_lookup_tool",
        description="Deferred search target.",
        search_hint="nebula deferred capability",
        deferred=True,
    )

    payload = json.loads(registry.dispatch("tool_search", {"query": "nebula"}))
    deferred_matches = {
        item["name"]: item["deferred"]
        for item in payload["results"]
    }
    assert deferred_matches[name] is True


def test_tool_search_result_includes_expected_fields(register_tools):
    name = register_tools(
        "c2_field_probe_tool",
        toolset="c2_field_probe_toolset",
        description="Field coverage target.",
        search_hint="field probe discovery",
        deferred=True,
    )

    payload = json.loads(registry.dispatch("tool_search", {"query": "field probe"}))
    result = next(item for item in payload["results"] if item["name"] == name)
    assert set(result.keys()) == {"name", "description", "toolset", "search_hint", "deferred"}


def test_deferred_tool_not_in_get_tool_definitions_default_output(register_tools):
    toolset = "c2_deferred_toolset"
    name = register_tools(
        "c2_deferred_not_loaded_tool",
        toolset=toolset,
        description="Deferred by default.",
        search_hint="manual activation required",
        deferred=True,
    )

    default_defs = get_tool_definitions(enabled_toolsets=[toolset], quiet_mode=True)
    default_names = {tool["function"]["name"] for tool in default_defs}
    assert name not in default_names

    activated_defs = get_tool_definitions(
        enabled_toolsets=[toolset],
        quiet_mode=True,
        activated_tools=[name],
    )
    activated_names = {tool["function"]["name"] for tool in activated_defs}
    assert name in activated_names


def test_always_load_tool_always_in_get_tool_definitions_output(register_tools):
    name = register_tools(
        "c2_always_loaded_tool",
        toolset="c2_always_loaded_toolset",
        description="Must always be present.",
        always_load=True,
    )

    defs = get_tool_definitions(enabled_toolsets=["terminal"], quiet_mode=True)
    names = {tool["function"]["name"] for tool in defs}
    assert name in names


def test_normal_tool_in_get_tool_definitions_output(register_tools):
    toolset = "c2_normal_toolset"
    name = register_tools(
        "c2_normal_loaded_tool",
        toolset=toolset,
        description="Normal tool inclusion path.",
    )

    defs = get_tool_definitions(enabled_toolsets=[toolset], quiet_mode=True)
    names = {tool["function"]["name"] for tool in defs}
    assert name in names


def test_deferred_and_always_load_on_same_tool_raises_value_error():
    reg = ToolRegistry()
    with pytest.raises(ValueError, match="deferred and always_load"):
        reg.register(
            name="c2_invalid_tool",
            toolset="c2_invalid_toolset",
            schema=_schema("c2_invalid_tool", "invalid"),
            handler=_dummy_handler,
            deferred=True,
            always_load=True,
        )
