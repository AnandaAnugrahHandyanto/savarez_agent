from __future__ import annotations

import pytest

from tools.registry import registry


@pytest.fixture
def catalog_registry_tool():
    registry.register(
        name="catalog_base_tool",
        toolset="catalog_static",
        schema={
            "name": "catalog_base_tool",
            "description": "Base catalog test tool.",
            "parameters": {"type": "object", "properties": {}},
        },
        handler=lambda args, **kwargs: "{}",
    )
    yield
    registry.deregister("catalog_base_tool")


class FakeMemoryManager:
    def get_all_tool_schemas(self):
        return [
            {
                "name": "catalog_base_tool",
                "description": "Duplicate memory tool.",
                "parameters": {"type": "object", "properties": {}},
            },
            {
                "name": "catalog_memory_tool",
                "description": "Runtime memory tool.",
                "parameters": {"type": "object", "properties": {}},
            },
        ]


class FakeContextEngine:
    def get_tool_schemas(self):
        return [
            {
                "name": "catalog_memory_tool",
                "description": "Duplicate context tool.",
                "parameters": {"type": "object", "properties": {}},
            },
            {
                "name": "catalog_context_tool",
                "description": "Runtime context tool.",
                "parameters": {"type": "object", "properties": {}},
            },
        ]


def test_catalog_adds_runtime_adapters_once_with_metadata(catalog_registry_tool):
    from tool_catalog import build_tool_catalog

    catalog = build_tool_catalog(
        enabled_toolsets=["catalog_static"],
        quiet_mode=True,
        memory_manager=FakeMemoryManager(),
        context_engine=FakeContextEngine(),
    )

    assert catalog.valid_names == frozenset(
        {"catalog_base_tool", "catalog_memory_tool", "catalog_context_tool"}
    )
    assert [tool["function"]["name"] for tool in catalog.to_openai_tools()] == [
        "catalog_base_tool",
        "catalog_memory_tool",
        "catalog_context_tool",
    ]

    assert catalog.source_metadata["catalog_base_tool"].source_type == "registry"
    assert catalog.source_metadata["catalog_base_tool"].toolset == "catalog_static"
    assert catalog.source_metadata["catalog_memory_tool"].source_type == "memory_provider"
    assert catalog.source_metadata["catalog_context_tool"].source_type == "context_engine"
    assert catalog.platform_policy.requested_enabled_toolsets == ("catalog_static",)
    assert catalog.platform_policy.effective_enabled_toolsets == ("catalog_static",)


def test_catalog_is_immutable_and_exports_mutable_copies(catalog_registry_tool):
    from tool_catalog import build_tool_catalog

    catalog = build_tool_catalog(enabled_toolsets=["catalog_static"], quiet_mode=True)

    with pytest.raises(AttributeError):
        catalog.schemas.append({"type": "function", "function": {"name": "leak"}})
    with pytest.raises(AttributeError):
        catalog.valid_names.add("leak")
    with pytest.raises(TypeError):
        catalog.source_metadata["leak"] = catalog.source_metadata["catalog_base_tool"]

    exported = catalog.to_openai_tools()
    exported.append({"type": "function", "function": {"name": "leak"}})
    exported[0]["function"]["description"] = "mutated"

    fresh = catalog.to_openai_tools()
    assert [tool["function"]["name"] for tool in fresh] == ["catalog_base_tool"]
    assert fresh[0]["function"]["description"] == "Base catalog test tool."


def test_quiet_catalog_cache_isolation(catalog_registry_tool):
    import model_tools

    model_tools._clear_tool_defs_cache()
    first = model_tools.get_tool_catalog(enabled_toolsets=["catalog_static"], quiet_mode=True)
    first_export = first.to_openai_tools()
    first_export.append({"type": "function", "function": {"name": "leak"}})

    second = model_tools.get_tool_catalog(enabled_toolsets=["catalog_static"], quiet_mode=True)
    assert first is second
    assert [tool["function"]["name"] for tool in second.to_openai_tools()] == [
        "catalog_base_tool"
    ]

    model_tools._clear_tool_defs_cache()
