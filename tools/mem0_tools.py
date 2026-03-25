"""Mem0 tools for persistent memory retrieval and storage.

Registers four tools under the 'mem0' toolset:

  mem0_profile  — get all stored memories (fast, no reranking)
  mem0_search   — semantic search with optional precision mode
  mem0_context  — deep retrieval with reranking + graph
  mem0_conclude — store a durable fact about the user

The user_id is injected at runtime by the agent loop via
``set_mem0_context()``.
"""

import json
import logging

logger = logging.getLogger(__name__)

# -- Module-level state (injected by AIAgent at init time) --

_mem0_manager = None   # Mem0MemoryManager instance
_mem0_user_id: str | None = None


def set_mem0_context(manager, user_id: str) -> None:
    """Register the active Mem0 manager and user ID.

    Called by AIAgent.__init__ when Mem0 is enabled.
    """
    global _mem0_manager, _mem0_user_id
    _mem0_manager = manager
    _mem0_user_id = user_id


def clear_mem0_context() -> None:
    """Clear Mem0 context (for testing or shutdown)."""
    global _mem0_manager, _mem0_user_id
    _mem0_manager = None
    _mem0_user_id = None


# -- Availability check --

def _check_mem0_available() -> bool:
    """Tool is only available when Mem0 is active."""
    return _mem0_manager is not None and _mem0_user_id is not None


def _resolve_mem0_context(**kwargs):
    """Prefer the calling agent's context over module-global fallback."""
    manager = kwargs.get("mem0_manager") or _mem0_manager
    user_id = kwargs.get("mem0_user_id") or _mem0_user_id
    return manager, user_id


# -- mem0_profile --

_PROFILE_SCHEMA = {
    "name": "mem0_profile",
    "description": (
        "Retrieve all stored memories about the user \u2014 preferences, facts, "
        "project context, corrections. Fast, no reranking. "
        "Use at conversation start or when you need a full picture. "
        "Use mem0_search for targeted queries instead."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}


def _handle_mem0_profile(args: dict, **kw) -> str:
    manager, user_id = _resolve_mem0_context(**kw)
    if not manager or not user_id:
        return json.dumps({"error": "Mem0 is not active for this session."})
    try:
        memories = manager.get_profile(user_id)
        if not memories:
            return json.dumps({"result": "No memories stored yet. The user's profile builds over time through conversations."})
        return json.dumps({"result": memories})
    except Exception as e:
        logger.error("Error fetching Mem0 profile: %s", e)
        return json.dumps({"error": f"Failed to fetch profile: {e}"})


# -- mem0_search --

_SEARCH_SCHEMA = {
    "name": "mem0_search",
    "description": (
        "Search the user's memories by meaning. Returns relevant facts "
        "ranked by similarity. Use when looking for specific information "
        "like preferences, past decisions, or project details. "
        "Set rerank=true for higher accuracy (+150ms)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "What to search for (e.g. 'programming languages', 'dietary preferences').",
            },
            "rerank": {
                "type": "boolean",
                "description": "Override reranking. Omit to use config setting (default: enabled).",
            },
            "top_k": {
                "type": "integer",
                "description": "Number of results to return (default 10, max 50).",
            },
        },
        "required": ["query"],
    },
}


def _handle_mem0_search(args: dict, **kw) -> str:
    query = args.get("query", "")
    if not query:
        return json.dumps({"error": "Missing required parameter: query"})
    manager, user_id = _resolve_mem0_context(**kw)
    if not manager or not user_id:
        return json.dumps({"error": "Mem0 is not active for this session."})
    rerank = bool(args["rerank"]) if "rerank" in args else None  # None = use config default
    top_k = min(int(args.get("top_k", 10)), 50)
    try:
        results = manager.search(query, user_id, top_k=top_k, rerank=rerank)
        if not results:
            return json.dumps({"result": "No relevant memories found."})
        return json.dumps({"result": results})
    except Exception as e:
        logger.error("Error searching Mem0: %s", e)
        return json.dumps({"error": f"Failed to search memories: {e}"})


# -- mem0_context (deep retrieval) --

_CONTEXT_SCHEMA = {
    "name": "mem0_context",
    "description": (
        "Deep context retrieval — searches memories with reranking "
        "for higher accuracy. Higher latency than mem0_search but "
        "richer results. Use when you need comprehensive context "
        "for a complex question."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "A natural language question about the user or their context.",
            },
        },
        "required": ["query"],
    },
}


def _handle_mem0_context(args: dict, **kw) -> str:
    query = args.get("query", "")
    if not query:
        return json.dumps({"error": "Missing required parameter: query"})
    manager, user_id = _resolve_mem0_context(**kw)
    if not manager or not user_id:
        return json.dumps({"error": "Mem0 is not active for this session."})
    try:
        results = manager.search(query, user_id, top_k=5, rerank=True)
        if not results:
            return json.dumps({"result": "No relevant context found."})
        return json.dumps({"result": results})
    except Exception as e:
        logger.error("Error querying Mem0 context: %s", e)
        return json.dumps({"error": f"Failed to query context: {e}"})


# -- mem0_conclude --

_CONCLUDE_SCHEMA = {
    "name": "mem0_conclude",
    "description": (
        "Store a fact about the user in persistent memory. "
        "Use when the user states a preference, corrects you, "
        "or shares something that should be remembered across sessions. "
        "The fact is stored as-is without LLM extraction. "
        "Examples: 'User prefers dark mode', 'Project uses Python 3.11'."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "conclusion": {
                "type": "string",
                "description": "A factual statement about the user to persist in memory.",
            },
        },
        "required": ["conclusion"],
    },
}


def _handle_mem0_conclude(args: dict, **kw) -> str:
    conclusion = args.get("conclusion", "")
    if not conclusion:
        return json.dumps({"error": "Missing required parameter: conclusion"})
    manager, user_id = _resolve_mem0_context(**kw)
    if not manager or not user_id:
        return json.dumps({"error": "Mem0 is not active for this session."})
    try:
        result = manager.store_fact(conclusion, user_id)
        if "error" not in result:
            return json.dumps({"result": f"Conclusion saved: {conclusion}"})
        return json.dumps({"error": f"Failed to save: {result['error']}"})
    except Exception as e:
        logger.error("Error saving Mem0 conclusion: %s", e)
        return json.dumps({"error": f"Failed to save conclusion: {e}"})


# -- Registration --

from tools.registry import registry

registry.register(
    name="mem0_profile",
    toolset="mem0",
    schema=_PROFILE_SCHEMA,
    handler=_handle_mem0_profile,
    check_fn=_check_mem0_available,
    emoji="\U0001f9e0",
)

registry.register(
    name="mem0_search",
    toolset="mem0",
    schema=_SEARCH_SCHEMA,
    handler=_handle_mem0_search,
    check_fn=_check_mem0_available,
    emoji="\U0001f9e0",
)

registry.register(
    name="mem0_context",
    toolset="mem0",
    schema=_CONTEXT_SCHEMA,
    handler=_handle_mem0_context,
    check_fn=_check_mem0_available,
    emoji="\U0001f9e0",
)

registry.register(
    name="mem0_conclude",
    toolset="mem0",
    schema=_CONCLUDE_SCHEMA,
    handler=_handle_mem0_conclude,
    check_fn=_check_mem0_available,
    emoji="\U0001f9e0",
)
