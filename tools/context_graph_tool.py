#!/usr/bin/env python3
"""
Context Graph Tool — Personal knowledge graph for decisions, entities, and reasoning.

Provides temporal entity/relationship storage via Graphiti + Kuzu. Search is instant
(~300ms, no LLM calls). Ingestion requires LLM (~2-10s per episode) for entity
extraction, deduplication, and edge detection.

The tool is gated behind:
  - graphiti-core[kuzu] being installed
  - context_graph.enabled: true in cli-config.yaml

LLM cost is configurable via auxiliary.context_graph in config or
AUXILIARY_CONTEXT_GRAPH_MODEL/PROVIDER env vars.
"""

import json
import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Content scanning — reuse patterns from memory_tool for consistency
# ---------------------------------------------------------------------------

_THREAT_PATTERNS = [
    (r'ignore\s+(previous|all|above|prior)\s+instructions', "prompt_injection"),
    (r'you\s+are\s+now\s+', "role_hijack"),
    (r'system\s+prompt\s+override', "sys_prompt_override"),
    (r'disregard\s+(your|all|any)\s+(instructions|rules|guidelines)', "disregard_rules"),
    (r'curl\s+[^\n]*\$\{?\w*(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|API)', "exfil_curl"),
    (r'wget\s+[^\n]*\$\{?\w*(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|API)', "exfil_wget"),
]

_INVISIBLE_CHARS = {
    '\u200b', '\u200c', '\u200d', '\u2060', '\ufeff',
    '\u202a', '\u202b', '\u202c', '\u202d', '\u202e',
}


def _scan_content(content: str) -> Optional[str]:
    """Scan episode content for injection/exfiltration patterns."""
    if not content:
        return None
    for char in _INVISIBLE_CHARS:
        if char in content:
            return f"Blocked: invisible unicode U+{ord(char):04X}"
    for pattern, pid in _THREAT_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            return f"Blocked: threat pattern '{pid}'"
    return None


# ---------------------------------------------------------------------------
# Tool handler
# ---------------------------------------------------------------------------

async def context_graph_handler(
    action: str,
    query: str = None,
    content: str = None,
    source_type: str = None,
    name: str = None,
    entity_id: str = None,
    episode_uuid: str = None,
    limit: int = 10,
    since: str = None,
    group_id: str = "personal",
    manager=None,
) -> str:
    """Handle context_graph tool calls. Returns JSON string."""

    if manager is None:
        return json.dumps({
            "success": False,
            "error": "Context graph not initialized. Set context_graph.enabled: true in cli-config.yaml",
        }, ensure_ascii=False)

    try:
        if action == "search":
            if not query:
                return json.dumps({
                    "success": False,
                    "error": "query is required for search action",
                }, ensure_ascii=False)

            result = await manager.search(
                query=query,
                limit=min(limit, 25),
                group_ids=[group_id] if group_id else None,
            )
            return json.dumps({"success": True, **result}, ensure_ascii=False)

        elif action == "add_episode":
            if not content:
                return json.dumps({
                    "success": False,
                    "error": "content is required for add_episode action",
                }, ensure_ascii=False)

            # Security scan
            threat = _scan_content(content)
            if threat:
                return json.dumps({"success": False, "error": threat}, ensure_ascii=False)

            result = await manager.add_episode(
                content=content,
                source_type=source_type or "text",
                name=name or "",
                group_id=group_id,
            )
            return json.dumps({"success": True, **result}, ensure_ascii=False)

        elif action == "get_episodes":
            episodes = await manager.get_episodes(
                last_n=min(limit, 50),
                group_ids=[group_id] if group_id else None,
            )
            return json.dumps({
                "success": True,
                "count": len(episodes),
                "episodes": episodes,
            }, ensure_ascii=False)

        elif action == "get_episode_details":
            if not episode_uuid:
                return json.dumps({
                    "success": False,
                    "error": "episode_uuid is required for get_episode_details action",
                }, ensure_ascii=False)

            result = await manager.get_nodes_by_episode(episode_uuid)
            return json.dumps({"success": True, **result}, ensure_ascii=False)

        elif action == "export":
            export_json = await manager.export_json()
            return json.dumps({
                "success": True,
                "message": "Graph exported successfully",
                "data": json.loads(export_json),
            }, ensure_ascii=False)

        else:
            valid_actions = ["search", "add_episode", "get_episodes", "get_episode_details", "export"]
            return json.dumps({
                "success": False,
                "error": f"Unknown action '{action}'. Valid: {', '.join(valid_actions)}",
            }, ensure_ascii=False)

    except Exception as e:
        logger.exception("Context graph tool error (%s): %s", action, e)
        return json.dumps({
            "success": False,
            "error": f"{type(e).__name__}: {e}",
        }, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Availability check
# ---------------------------------------------------------------------------

def check_context_graph_requirements() -> bool:
    """Check if graphiti-core is installed and context_graph is enabled in config."""
    try:
        import graphiti_core  # noqa: F401
        import kuzu  # noqa: F401
    except ImportError:
        return False

    # Check config
    try:
        from hermes_constants import get_hermes_home
        import yaml

        config_path = get_hermes_home() / "cli-config.yaml"
        if config_path.exists():
            with open(config_path) as f:
                config = yaml.safe_load(f) or {}
            graph_config = config.get("context_graph", {})
            return bool(graph_config.get("enabled", False))
    except Exception:
        pass

    return False


# ---------------------------------------------------------------------------
# OpenAI Function-Calling Schema
# ---------------------------------------------------------------------------

CONTEXT_GRAPH_SCHEMA = {
    "name": "context_graph",
    "description": (
        "Personal knowledge graph that captures decisions, entities, and reasoning "
        "across sessions with temporal validity tracking.\n\n"
        "USE PROACTIVELY:\n"
        "- SEARCH before starting complex work to check for relevant past decisions\n"
        "- ADD_EPISODE after significant decisions, learnings, or project milestones\n"
        "  Include: goal, options considered, trade-offs, decision, reasoning, outcome\n"
        "- GET_EPISODES to review recent graph activity\n"
        "- EXPORT to backup the full graph as JSON\n\n"
        "DO NOT ingest trivial interactions — only decisions, learnings, and milestones.\n\n"
        "Search is instant (~300ms, no LLM cost). Ingestion uses a cheap LLM for "
        "entity extraction (~2-10s per episode)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["search", "add_episode", "get_episodes", "get_episode_details", "export"],
                "description": (
                    "search: find relevant entities/facts/decisions (instant, no LLM cost). "
                    "add_episode: ingest a decision trace or learning (uses LLM, ~2-10s). "
                    "get_episodes: list recent episodes. "
                    "get_episode_details: get entities/edges from a specific episode. "
                    "export: dump full graph as JSON for backup."
                ),
            },
            "query": {
                "type": "string",
                "description": "Natural language search query. Required for 'search'.",
            },
            "content": {
                "type": "string",
                "description": (
                    "Episode content to ingest. Required for 'add_episode'. "
                    "For decision traces, include: Goal, Options, Trade-offs, Decision, Reasoning, Outcome."
                ),
            },
            "source_type": {
                "type": "string",
                "enum": ["text", "message", "json"],
                "description": "Type of content being ingested. Default: 'text'.",
            },
            "name": {
                "type": "string",
                "description": "Short label for the episode (auto-generated if empty).",
            },
            "episode_uuid": {
                "type": "string",
                "description": "UUID of a specific episode. Required for 'get_episode_details'.",
            },
            "limit": {
                "type": "integer",
                "description": "Max results to return. Default: 10.",
            },
        },
        "required": ["action"],
    },
}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

from tools.registry import registry  # noqa: E402

registry.register(
    name="context_graph",
    toolset="context_graph",
    schema=CONTEXT_GRAPH_SCHEMA,
    handler=lambda args, **kw: context_graph_handler(
        action=args.get("action", ""),
        query=args.get("query"),
        content=args.get("content"),
        source_type=args.get("source_type"),
        name=args.get("name"),
        entity_id=args.get("entity_id"),
        episode_uuid=args.get("episode_uuid"),
        limit=args.get("limit", 10),
        manager=kw.get("graph_manager"),
    ),
    check_fn=check_context_graph_requirements,
    is_async=True,
    emoji="🕸️",
    mutates=True,
)
