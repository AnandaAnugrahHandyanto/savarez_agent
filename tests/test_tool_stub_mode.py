"""Tests for tools.stub_mode — _apply_stub_mode() and the stub_mode param on
get_tool_definitions().

Invariants:
- Core tools (_STUB_MODE_FULL_TOOLS) keep full schemas (parameters present).
- Non-core tools are reduced to {name, description} only.
- The description of a stubbed tool is annotated with the delegation hint.
- stub_mode=False (default) leaves all schemas intact.
- stub_mode is cache-keyed independently — a full call and a stub call
  never share a cached object.
- _apply_stub_mode is safe on an empty list.
"""
from __future__ import annotations

import pytest

import model_tools
from model_tools import _apply_stub_mode, _STUB_MODE_FULL_TOOLS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tool(name: str, *, extra_param: bool = True) -> dict:
    fn: dict = {"name": name, "description": f"Tool {name}."}
    if extra_param:
        fn["parameters"] = {
            "type": "object",
            "properties": {"arg1": {"type": "string"}},
            "required": ["arg1"],
        }
    return {"type": "function", "function": fn}


# Pick one known core tool and one known non-core tool for parametrised tests.
_CORE_TOOL = "delegate_task"
_NON_CORE_TOOL = "terminal"


# ---------------------------------------------------------------------------
# _apply_stub_mode unit tests
# ---------------------------------------------------------------------------

class TestApplyStubMode:
    def test_empty_list_is_safe(self):
        assert _apply_stub_mode([]) == []

    def test_core_tool_keeps_full_schema(self):
        tool = _make_tool(_CORE_TOOL)
        result = _apply_stub_mode([tool])
        assert len(result) == 1
        fn = result[0]["function"]
        assert "parameters" in fn, "Core tool must retain its parameters schema."

    def test_non_core_tool_is_reduced_to_stub(self):
        tool = _make_tool(_NON_CORE_TOOL)
        result = _apply_stub_mode([tool])
        assert len(result) == 1
        fn = result[0]["function"]
        assert "parameters" not in fn, (
            "Non-core tool must not expose parameters in stub mode."
        )
        assert fn["name"] == _NON_CORE_TOOL
        assert fn["description"]  # must have some description

    def test_stub_description_includes_delegation_hint(self):
        tool = _make_tool(_NON_CORE_TOOL)
        result = _apply_stub_mode([tool])
        desc = result[0]["function"]["description"]
        assert "delegate_task" in desc, (
            "Stubbed description must hint that the tool must be invoked via delegate_task."
        )

    def test_mixed_tools_split_correctly(self):
        """All core tools keep full schemas; all non-core tools are stubbed."""
        core = [_make_tool(name) for name in _STUB_MODE_FULL_TOOLS]
        non_core = [_make_tool("fake_non_core_tool")]
        result = _apply_stub_mode(core + non_core)
        for item in result:
            name = item["function"]["name"]
            if name in _STUB_MODE_FULL_TOOLS:
                assert "parameters" in item["function"], f"{name} must keep full schema"
            else:
                assert "parameters" not in item["function"], f"{name} must be stubbed"

    def test_type_field_preserved(self):
        """The 'type': 'function' wrapper must survive stubbing."""
        tool = _make_tool(_NON_CORE_TOOL)
        result = _apply_stub_mode([tool])
        assert result[0].get("type") == "function"

    def test_tool_without_parameters_field_is_safe(self):
        """A tool that already has no parameters field must not crash."""
        tool = _make_tool(_NON_CORE_TOOL, extra_param=False)
        result = _apply_stub_mode([tool])
        assert result[0]["function"]["name"] == _NON_CORE_TOOL


# ---------------------------------------------------------------------------
# get_tool_definitions(stub_mode=...) integration tests
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_cache():
    model_tools._tool_defs_cache.clear()
    yield
    model_tools._tool_defs_cache.clear()


class TestGetToolDefinitionsStubMode:
    def test_stub_mode_false_returns_full_schemas(self):
        tools = model_tools.get_tool_definitions(quiet_mode=True, stub_mode=False)
        # At least some non-core tool must have a non-trivial schema.
        non_core = [
            t for t in tools
            if t["function"]["name"] not in _STUB_MODE_FULL_TOOLS
        ]
        assert any(
            "parameters" in t["function"] for t in non_core
        ), "stub_mode=False must leave full schemas intact."

    def test_stub_mode_true_strips_non_core_parameters(self):
        tools = model_tools.get_tool_definitions(quiet_mode=True, stub_mode=True)
        for t in tools:
            name = t["function"]["name"]
            if name not in _STUB_MODE_FULL_TOOLS:
                assert "parameters" not in t["function"], (
                    f"stub_mode=True: {name} must not expose parameters."
                )

    def test_stub_mode_true_preserves_core_tools(self):
        tools = model_tools.get_tool_definitions(quiet_mode=True, stub_mode=True)
        by_name = {t["function"]["name"]: t for t in tools}
        for core_name in _STUB_MODE_FULL_TOOLS:
            if core_name in by_name:
                assert "parameters" in by_name[core_name]["function"], (
                    f"stub_mode=True: core tool {core_name} must retain parameters."
                )

    def test_stub_and_full_use_separate_cache_entries(self):
        """stub_mode=True and stub_mode=False must not share a cache slot."""
        model_tools.get_tool_definitions(quiet_mode=True, stub_mode=False)
        model_tools.get_tool_definitions(quiet_mode=True, stub_mode=True)
        assert len(model_tools._tool_defs_cache) == 2, (
            "stub_mode should be part of the cache key — "
            "full and stub results must not overwrite each other."
        )

    def test_stub_mode_skip_tool_search_assembly_respected(self):
        """When skip_tool_search_assembly=True, stub mode is not applied
        (that path serves the bridge catalog reader, not the main agent)."""
        tools_bridge = model_tools.get_tool_definitions(
            quiet_mode=True,
            stub_mode=True,
            skip_tool_search_assembly=True,
        )
        # At least one non-core tool must retain full schema via bridge path.
        non_core_full = [
            t for t in tools_bridge
            if t["function"]["name"] not in _STUB_MODE_FULL_TOOLS
            and "parameters" in t["function"]
        ]
        assert non_core_full, (
            "skip_tool_search_assembly=True must bypass stub mode — "
            "the bridge reader needs full schemas."
        )
