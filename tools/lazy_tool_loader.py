"""Session-local lazy tool loading.

Tools remain registered in the global registry, but this helper can add
selected schemas to a running agent after session start.
"""

import json
from typing import Dict, Iterable, List, Set

from tools.registry import registry


TOOL_NAME = "load_tool_pack"

TOOL_PACKS: Dict[str, List[str]] = {
    "avatar": [
        "mcp_botparlor_get_avatar_inventory",
        "mcp_botparlor_get_outfits",
        "mcp_botparlor_create_avatar",
        "mcp_botparlor_get_avatar_job",
        "mcp_botparlor_get_moods",
    ],
    "reminders": [
        "mcp_botparlor_create_reminder",
        "mcp_botparlor_list_reminders",
        "mcp_botparlor_update_reminder",
        "mcp_botparlor_cancel_reminder",
    ],
    "media": [
        "mcp_botparlor_display_media",
        "mcp_botparlor_close_media",
    ],
    "botparlor_resources": [
        "mcp_botparlor_list_resources",
        "mcp_botparlor_read_resource",
        "mcp_botparlor_list_prompts",
        "mcp_botparlor_get_prompt",
    ],
    "recall": [
        "session_search",
    ],
    "skills": [
        "skills_list",
        "skill_view",
        "skill_manage",
    ],
    "power": [
        "web_search",
        "web_extract",
        "terminal",
        "process",
        "read_file",
        "write_file",
        "patch",
        "search_files",
        "browser_navigate",
        "browser_snapshot",
        "browser_click",
        "browser_type",
        "browser_scroll",
        "browser_back",
        "browser_press",
        "browser_get_images",
        "browser_vision",
        "browser_console",
        "browser_cdp",
        "browser_dialog",
        "vision_analyze",
        "image_generate",
        "text_to_speech",
        "todo",
        "execute_code",
        "delegate_task",
    ],
}


def _unique_tool_names(names: Iterable[str]) -> List[str]:
    seen: Set[str] = set()
    result: List[str] = []
    for name in names:
        clean = str(name or "").strip()
        if clean and clean not in seen:
            seen.add(clean)
            result.append(clean)
    return result


def _current_agent_tool_names(agent) -> Set[str]:
    current = set(getattr(agent, "valid_tool_names", set()) or set())
    for tool_def in getattr(agent, "tools", []) or []:
        name = tool_def.get("function", {}).get("name")
        if name:
            current.add(name)
    return current


def load_tool_pack_for_agent(agent, pack: str) -> str:
    """Add schemas from *pack* to a running agent and return a JSON result."""
    pack_name = str(pack or "").strip()
    if pack_name not in TOOL_PACKS:
        return json.dumps(
            {
                "success": False,
                "error": f"Unknown tool pack: {pack_name}",
                "available_packs": sorted(TOOL_PACKS),
            }
        )

    requested = _unique_tool_names(TOOL_PACKS[pack_name])
    current_names = _current_agent_tool_names(agent)
    definitions = registry.get_definitions(set(requested), quiet=True)
    definitions_by_name = {
        definition["function"]["name"]: definition
        for definition in definitions
        if definition.get("function", {}).get("name")
    }

    existing_tools = list(getattr(agent, "tools", []) or [])
    loaded: List[str] = []
    already_available: List[str] = []
    unavailable: List[str] = []

    for name in requested:
        definition = definitions_by_name.get(name)
        if definition is None:
            unavailable.append(name)
            continue
        if name in current_names:
            already_available.append(name)
            continue
        existing_tools.append(definition)
        current_names.add(name)
        loaded.append(name)

    agent.tools = existing_tools
    agent.valid_tool_names = current_names

    return json.dumps(
        {
            "success": True,
            "pack": pack_name,
            "loaded": loaded,
            "already_available": already_available,
            "unavailable": unavailable,
            "message": "Loaded tools are available on the next model call.",
        }
    )


def _load_tool_pack_handler(args, **kwargs):
    return json.dumps(
        {
            "success": False,
            "error": "load_tool_pack requires an active agent session.",
        }
    )


registry.register(
    name=TOOL_NAME,
    toolset="tool_loader",
    schema={
        "name": TOOL_NAME,
        "description": "Load optional tools into this session by pack name.",
        "parameters": {
            "type": "object",
            "properties": {
                "pack": {
                    "type": "string",
                    "enum": sorted(TOOL_PACKS),
                    "description": "Tool pack to load.",
                }
            },
            "required": ["pack"],
        },
    },
    handler=_load_tool_pack_handler,
    description="Load optional tools into this session by pack name.",
)
