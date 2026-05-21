"""Build the immutable tool surface exposed to an agent."""

from __future__ import annotations

import os
from copy import deepcopy
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Set, Tuple

from tools.registry import registry
from toolsets import get_all_toolsets, resolve_toolset, validate_toolset


LEGACY_TOOLSET_MAP: Dict[str, List[str]] = {
    "web_tools": ["web_search", "web_extract"],
    "terminal_tools": ["terminal"],
    "vision_tools": ["vision_analyze"],
    "moa_tools": ["mixture_of_agents"],
    "image_tools": ["image_generate"],
    "skills_tools": ["skills_list", "skill_view", "skill_manage"],
    "browser_tools": [
        "browser_navigate", "browser_snapshot", "browser_click",
        "browser_type", "browser_scroll", "browser_back",
        "browser_press", "browser_get_images",
        "browser_vision", "browser_console",
    ],
    "cronjob_tools": ["cronjob"],
    "file_tools": ["read_file", "write_file", "patch", "search_files"],
    "tts_tools": ["text_to_speech"],
}


@dataclass(frozen=True)
class ToolSourceMetadata:
    name: str
    source_type: str
    toolset: Optional[str] = None
    adapter: Optional[str] = None


@dataclass(frozen=True)
class ToolPlatformPolicy:
    requested_enabled_toolsets: Optional[Tuple[str, ...]]
    requested_disabled_toolsets: Tuple[str, ...]
    effective_enabled_toolsets: Optional[Tuple[str, ...]]
    forced_toolsets: Tuple[str, ...]
    requested_tool_names: Tuple[str, ...]


@dataclass(frozen=True)
class ToolCatalog:
    schemas: Tuple[Mapping[str, Any], ...]
    valid_names: frozenset[str]
    source_metadata: Mapping[str, ToolSourceMetadata]
    platform_policy: ToolPlatformPolicy

    def to_openai_tools(self) -> List[Dict[str, Any]]:
        """Return fresh mutable OpenAI-format schemas for API callers."""
        return [_thaw(schema) for schema in self.schemas]


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)
    if isinstance(value, tuple):
        return tuple(_freeze(v) for v in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {k: _thaw(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_thaw(v) for v in value]
    return deepcopy(value)


def _tool_name(schema: Mapping[str, Any]) -> str:
    function = schema.get("function", {})
    if isinstance(function, Mapping):
        return str(function.get("name") or "")
    return ""


def _wrap_schema(schema: Mapping[str, Any]) -> Dict[str, Any]:
    return {"type": "function", "function": dict(schema)}


def _resolve_requested_tools(
    enabled_toolsets: Optional[List[str]],
    disabled_toolsets: Optional[List[str]],
    quiet_mode: bool,
) -> tuple[Set[str], ToolPlatformPolicy]:
    tools_to_include: Set[str] = set()
    forced_toolsets: list[str] = []
    effective_enabled_toolsets: Optional[list[str]] = None

    if enabled_toolsets is not None:
        effective_enabled_toolsets = list(enabled_toolsets)
        if os.environ.get("HERMES_KANBAN_TASK") and "kanban" not in effective_enabled_toolsets:
            effective_enabled_toolsets.append("kanban")
            forced_toolsets.append("kanban")
        for toolset_name in effective_enabled_toolsets:
            if validate_toolset(toolset_name):
                resolved = resolve_toolset(toolset_name)
                tools_to_include.update(resolved)
                if not quiet_mode:
                    print(f"✅ Enabled toolset '{toolset_name}': {', '.join(resolved) if resolved else 'no tools'}")
            elif toolset_name in LEGACY_TOOLSET_MAP:
                legacy_tools = LEGACY_TOOLSET_MAP[toolset_name]
                tools_to_include.update(legacy_tools)
                if not quiet_mode:
                    print(f"✅ Enabled legacy toolset '{toolset_name}': {', '.join(legacy_tools)}")
            elif not quiet_mode:
                print(f"⚠️  Unknown toolset: {toolset_name}")
    else:
        for ts_name in get_all_toolsets():
            tools_to_include.update(resolve_toolset(ts_name))

    if disabled_toolsets:
        for toolset_name in disabled_toolsets:
            if validate_toolset(toolset_name):
                resolved = resolve_toolset(toolset_name)
                tools_to_include.difference_update(resolved)
                if not quiet_mode:
                    print(f"🚫 Disabled toolset '{toolset_name}': {', '.join(resolved) if resolved else 'no tools'}")
            elif toolset_name in LEGACY_TOOLSET_MAP:
                legacy_tools = LEGACY_TOOLSET_MAP[toolset_name]
                tools_to_include.difference_update(legacy_tools)
                if not quiet_mode:
                    print(f"🚫 Disabled legacy toolset '{toolset_name}': {', '.join(legacy_tools)}")
            elif not quiet_mode:
                print(f"⚠️  Unknown toolset: {toolset_name}")

    policy = ToolPlatformPolicy(
        requested_enabled_toolsets=tuple(enabled_toolsets) if enabled_toolsets is not None else None,
        requested_disabled_toolsets=tuple(disabled_toolsets or ()),
        effective_enabled_toolsets=(
            tuple(effective_enabled_toolsets)
            if effective_enabled_toolsets is not None
            else None
        ),
        forced_toolsets=tuple(forced_toolsets),
        requested_tool_names=tuple(sorted(tools_to_include)),
    )
    return tools_to_include, policy


def _apply_schema_adapters(
    schemas: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    available_tool_names = {_tool_name(schema) for schema in schemas}

    if "execute_code" in available_tool_names:
        from tools.code_execution_tool import SANDBOX_ALLOWED_TOOLS, build_execute_code_schema, _get_execution_mode
        sandbox_enabled = SANDBOX_ALLOWED_TOOLS & available_tool_names
        dynamic_schema = build_execute_code_schema(sandbox_enabled, mode=_get_execution_mode())
        for i, td in enumerate(schemas):
            if _tool_name(td) == "execute_code":
                schemas[i] = {"type": "function", "function": dynamic_schema}
                break

    discord_schema_fns = {
        "discord": "get_dynamic_schema_core",
        "discord_admin": "get_dynamic_schema_admin",
    }
    for discord_tool_name, schema_fn_name in discord_schema_fns.items():
        if discord_tool_name in available_tool_names:
            try:
                from tools import discord_tool as discord_tool
                schema_fn = getattr(discord_tool, schema_fn_name)
                dynamic = schema_fn()
            except Exception:
                dynamic = None
            if dynamic is None:
                schemas = [
                    t for t in schemas
                    if _tool_name(t) != discord_tool_name
                ]
                available_tool_names.discard(discord_tool_name)
            else:
                for i, td in enumerate(schemas):
                    if _tool_name(td) == discord_tool_name:
                        schemas[i] = {"type": "function", "function": dynamic}
                        break

    if "browser_navigate" in available_tool_names:
        web_tools_available = {"web_search", "web_extract"} & available_tool_names
        if not web_tools_available:
            for i, td in enumerate(schemas):
                if _tool_name(td) == "browser_navigate":
                    desc = td["function"].get("description", "")
                    desc = desc.replace(
                        " For simple information retrieval, prefer web_search or web_extract (faster, cheaper).",
                        "",
                    )
                    schemas[i] = {
                        "type": "function",
                        "function": {**td["function"], "description": desc},
                    }
                    break

    try:
        from tools.schema_sanitizer import sanitize_tool_schemas
        schemas = sanitize_tool_schemas(schemas)
    except Exception:
        pass

    return schemas


def _append_runtime_schemas(
    schemas: List[Dict[str, Any]],
    sources: Dict[str, ToolSourceMetadata],
    provider: Any,
    method_name: str,
    source_type: str,
) -> None:
    if provider is None:
        return
    get_schemas: Optional[Callable[[], Iterable[Mapping[str, Any]]]] = getattr(provider, method_name, None)
    if get_schemas is None:
        return

    existing_names = {_tool_name(schema) for schema in schemas}
    for schema in get_schemas() or []:
        name = str(schema.get("name") or "")
        if not name or name in existing_names:
            continue
        schemas.append(_wrap_schema(schema))
        sources[name] = ToolSourceMetadata(
            name=name,
            source_type=source_type,
            adapter=provider.__class__.__name__,
        )
        existing_names.add(name)


def build_tool_catalog(
    enabled_toolsets: List[str] = None,
    disabled_toolsets: List[str] = None,
    quiet_mode: bool = False,
    memory_manager: Any = None,
    context_engine: Any = None,
) -> ToolCatalog:
    """Return the immutable tool surface for an agent or legacy caller."""
    tools_to_include, platform_policy = _resolve_requested_tools(
        enabled_toolsets=enabled_toolsets,
        disabled_toolsets=disabled_toolsets,
        quiet_mode=quiet_mode,
    )

    schemas = registry.get_definitions(tools_to_include, quiet=quiet_mode)
    schemas = _apply_schema_adapters(schemas)

    sources: Dict[str, ToolSourceMetadata] = {}
    for schema in schemas:
        name = _tool_name(schema)
        if not name:
            continue
        sources[name] = ToolSourceMetadata(
            name=name,
            source_type="registry",
            toolset=registry.get_toolset_for_tool(name),
        )

    _append_runtime_schemas(
        schemas,
        sources,
        memory_manager,
        "get_all_tool_schemas",
        "memory_provider",
    )
    _append_runtime_schemas(
        schemas,
        sources,
        context_engine,
        "get_tool_schemas",
        "context_engine",
    )

    if not quiet_mode:
        if schemas:
            tool_names = [_tool_name(t) for t in schemas]
            print(f"🛠️  Final tool selection ({len(schemas)} tools): {', '.join(tool_names)}")
        else:
            print("🛠️  No tools selected (all filtered out or unavailable)")

    frozen_schemas = tuple(_freeze(schema) for schema in schemas)
    valid_names = frozenset(_tool_name(schema) for schema in schemas if _tool_name(schema))
    return ToolCatalog(
        schemas=frozen_schemas,
        valid_names=valid_names,
        source_metadata=MappingProxyType(dict(sources)),
        platform_policy=platform_policy,
    )
