#!/usr/bin/env python3
"""
Mem0 Tool — Vector Memory Retrieval via HTTP API

Queries the local mem0 HTTP API server (localhost:3201) for persistent,
semantic memory across sessions. The mem0 server uses Qdrant for vector
storage backed by SQLite.

This is the same mem0 instance that remote OpenClaw agents (via Tailscale VPN)
connect to at http://100.68.222.60:3201.

Use when the user asks things like:
  - "what were we working on before?"
  - "remember when we discussed X?"
  - "what did we do about Y last time?"
"""

import json
import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

MEM0_API = "http://localhost:3201"


def _api_get(path: str, params: dict = None) -> Optional[dict]:
    """Make a GET request to the mem0 API."""
    try:
        resp = httpx.get(f"{MEM0_API}{path}", params=params, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except httpx.HTTPError as e:
        logger.debug(f"mem0 API error: {e}")
    return None


def _api_post(path: str, data: dict) -> Optional[dict]:
    """Make a POST request to the mem0 API."""
    try:
        resp = httpx.post(f"{MEM0_API}{path}", json=data, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except httpx.HTTPError as e:
        logger.debug(f"mem0 API error: {e}")
    return None


def mem0_recall(query: str, agent_id: str = "hermes", limit: int = 5) -> List[Dict[str, Any]]:
    """
    Search mem0 for relevant memories using vector similarity.

    Args:
        query: Search query
        agent_id: Which agent's memories to search (default: "hermes")
        limit: Max results to return
    """
    result = _api_get(
        "/memory/search",
        params={"q": query, "agent_id": agent_id, "limit": limit}
    )
    if not result:
        return []
    return result.get("memories", [])


def mem0_get_all(agent_id: str = "hermes", limit: int = 50) -> List[Dict[str, Any]]:
    """Get all memories for an agent."""
    result = _api_get(
        "/memory/all",
        params={"agent_id": agent_id, "limit": limit}
    )
    if not result:
        return []
    return result.get("memories", [])


def mem0_save(text: str, agent_id: str = "hermes", metadata: dict = None) -> bool:
    """Save a memory to mem0."""
    result = _api_post("/memory/add", {
        "text": text,
        "agent_id": agent_id,
        "metadata": metadata or {},
    })
    return result is not None


def mem0_tool(
    action: str,
    query: str = None,
    text: str = None,
    agent_id: str = "hermes",
    limit: int = 5,
) -> str:
    """
    Query mem0 vector memory for relevant past conversations and facts.

    Actions:
      - "recall": Search for memories matching a query
      - "all": Get all memories for this agent
      - "save": Save a new memory
      - "health": Check if mem0 API is available
    """
    if action == "health":
        result = _api_get("/health")
        if result:
            return json.dumps({
                "success": True,
                "status": result,
                "message": "mem0 is healthy"
            }, ensure_ascii=False)
        return json.dumps({
            "success": False,
            "error": "mem0 API is not reachable at http://localhost:3201"
        }, ensure_ascii=False)

    if action == "recall":
        if not query:
            return json.dumps({
                "success": False,
                "error": "query is required for 'recall' action"
            }, ensure_ascii=False)

        memories = mem0_recall(query=query, agent_id=agent_id, limit=limit)

        if not memories:
            return json.dumps({
                "success": True,
                "query": query,
                "agent_id": agent_id,
                "memories": [],
                "message": "No relevant memories found"
            }, ensure_ascii=False)

        return json.dumps({
            "success": True,
            "query": query,
            "agent_id": agent_id,
            "memories": memories,
            "count": len(memories),
        }, ensure_ascii=False)

    elif action == "all":
        memories = mem0_get_all(agent_id=agent_id, limit=limit)
        return json.dumps({
            "success": True,
            "agent_id": agent_id,
            "memories": memories,
            "count": len(memories),
        }, ensure_ascii=False)

    elif action == "save":
        if not text:
            return json.dumps({
                "success": False,
                "error": "text is required for 'save' action"
            }, ensure_ascii=False)

        success = mem0_save(text=text, agent_id=agent_id)
        if success:
            return json.dumps({
                "success": True,
                "message": "Memory saved",
                "agent_id": agent_id,
            }, ensure_ascii=False)
        return json.dumps({
            "success": False,
            "error": "Failed to save memory"
        }, ensure_ascii=False)

    else:
        return json.dumps({
            "success": False,
            "error": f"Unknown action '{action}'. Use: recall, all, save, health"
        }, ensure_ascii=False)


def check_mem0_requirements() -> bool:
    """Check if mem0 API is reachable."""
    return _api_get("/health") is not None


# =============================================================================
# OpenAI Function-Calling Schema
# =============================================================================

MEM0_SCHEMA = {
    "name": "mem0",
    "description": (
        "Query mem0 vector memory for relevant past conversations and facts. "
        "Mem0 stores semantic embeddings of conversation history across sessions.\n\n"
        "This connects to the local mem0 server (localhost:3201), which is the "
        "same instance that remote OpenClaw agents access via Tailscale VPN.\n\n"
        "Use when:\n"
        "- User asks 'what were we working on before?' or 'remember when X?'\n"
        "- You need to recall context from past sessions\n"
        "- User references something from a previous conversation\n\n"
        "Actions:\n"
        "- 'recall': Search for memories matching a query\n"
        "- 'all': Get all memories for this agent\n"
        "- 'save': Save a new memory\n"
        "- 'health': Check if mem0 is available"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["recall", "all", "save", "health"],
                "description": "Action to perform"
            },
            "query": {
                "type": "string",
                "description": "Search query to find relevant memories (for 'recall')"
            },
            "text": {
                "type": "string",
                "description": "Text to save (for 'save')"
            },
            "agent_id": {
                "type": "string",
                "description": "Agent ID to filter memories (default: 'hermes')",
                "default": "hermes"
            },
            "limit": {
                "type": "integer",
                "description": "Maximum memories to return (default: 5)",
                "default": 5
            },
        },
        "required": ["action"],
    },
}

# --- Registry ---
from tools.registry import registry

registry.register(
    name="mem0",
    toolset="memory",
    schema=MEM0_SCHEMA,
    handler=lambda args, **kw: mem0_tool(
        action=args.get("action", ""),
        query=args.get("query"),
        text=args.get("text"),
        agent_id=args.get("agent_id", "hermes"),
        limit=args.get("limit", 5),
    ),
    check_fn=check_mem0_requirements,
    emoji="🧠",
)
