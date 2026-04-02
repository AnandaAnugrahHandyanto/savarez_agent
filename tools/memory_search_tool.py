#!/usr/bin/env python3
"""
Memory Search Tool — semantic search over persistent memory entries.

Uses sqlite-vec for vector similarity search when all of the following are true:
  1. sqlite-vec is installed
  2. memory.embedding_enabled is true in config
  3. memories_vec has been populated (embeddings written via future embedding write-through)

Falls back to a simple SQLite LIKE-based keyword search when embeddings
are not configured, sqlite-vec is unavailable, or memories_vec is empty.

NOTE: Embedding write-through (populating memories_vec on add/replace) is not yet
implemented. Vector search will always fall back to keyword until that is added.
"""

import json
import logging
from pathlib import Path
from hermes_constants import get_hermes_home
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = get_hermes_home() / "state.db"


def _get_db_conn(db_path: Path):
    """Open a fresh connection with sqlite-vec loaded if available."""
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    vec_available = False
    try:
        import sqlite_vec
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        vec_available = True
    except Exception:
        pass
    return conn, vec_available


def _get_embedding(query: str, config: dict) -> Optional[List[float]]:
    """Generate an embedding for the query using the configured provider."""
    memory_cfg = config.get("memory", {})
    if not memory_cfg.get("embedding_enabled", False):
        return None

    provider = memory_cfg.get("embedding_provider", "openrouter")
    model = memory_cfg.get("embedding_model", "openai/text-embedding-3-small")

    try:
        import os
        from openai import OpenAI

        if provider == "openrouter":
            api_key = os.environ.get("OPENROUTER_API_KEY", "")
            base_url = "https://openrouter.ai/api/v1"
        else:
            api_key = os.environ.get("OPENAI_API_KEY", "")
            base_url = None

        if not api_key:
            logger.debug("No API key for embedding provider '%s'", provider)
            return None

        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url

        client = OpenAI(**kwargs)
        response = client.embeddings.create(
            model=model,
            input=query,
        )
        return response.data[0].embedding
    except Exception as e:
        logger.warning("Embedding generation failed: %s", e)
        return None


def memory_search_handler(
    query: str,
    target: str = "both",
    limit: int = 5,
    db_path: Path = None,
    config: dict = None,
) -> str:
    """
    Search memory entries using semantic search (vec) or keyword fallback.

    Args:
        query: Search query text
        target: "memory", "user", or "both"
        limit: Maximum number of results to return
        db_path: Path to the SQLite DB (defaults to state.db)
        config: Config dict for embedding settings

    Returns:
        JSON string with list of matching entries
    """
    if not query or not query.strip():
        return json.dumps({"success": False, "error": "Query cannot be empty."})

    db_path = db_path or DEFAULT_DB_PATH
    # Load config from disk if not provided — ensures embedding_enabled can be read
    if config is None:
        try:
            import yaml
            from hermes_constants import get_hermes_home
            config_path = get_hermes_home() / "config.yaml"
            if config_path.exists():
                with open(config_path, encoding="utf-8") as f:
                    config = yaml.safe_load(f) or {}
            else:
                config = {}
        except Exception:
            config = {}
    limit = max(1, min(limit, 50))  # Clamp to 1-50

    try:
        conn, vec_available = _get_db_conn(db_path)
        try:
            results = []

            # Determine which targets to search
            if target == "both":
                target_filter = ("memory", "user")
            elif target in ("memory", "user"):
                target_filter = (target,)
            else:
                return json.dumps({"success": False, "error": f"Invalid target '{target}'. Use 'memory', 'user', or 'both'."})

            # Try vector search first, fall back to keyword if unavailable or failed
            embedding = _get_embedding(query, config) if vec_available else None
            used_vector = False

            if embedding is not None and vec_available:
                vec_results = _vec_search(conn, embedding, target_filter, limit)
                if vec_results:
                    # Use vector results only when we have at least one match
                    results = vec_results
                    used_vector = True
                else:
                    # vec search returned None or empty — fall back to keyword
                    results = _keyword_search(conn, query, target_filter, limit)
            else:
                results = _keyword_search(conn, query, target_filter, limit)

        finally:
            conn.close()

        return json.dumps({
            "success": True,
            "query": query,
            "target": target,
            "results": results,
            "count": len(results),
            "search_mode": "vector" if used_vector else "keyword",
        }, ensure_ascii=False)

    except Exception as e:
        logger.error("Memory search failed: %s", e)
        return json.dumps({"success": False, "error": f"Search failed: {e}"})


def _vec_search(conn, embedding: List[float], target_filter: tuple, limit: int) -> List[dict]:
    """Perform vector KNN search using memories_vec.

    sqlite-vec requires the MATCH clause on the vec0 table with k= constraint.
    We join to memories to apply the target/level filters post-KNN.
    """
    try:
        import sqlite_vec
        embedding_bytes = sqlite_vec.serialize_float32(embedding)

        placeholders = ",".join("?" * len(target_filter))
        cursor = conn.cursor()
        # vec0 KNN: MATCH on embedding column, k= sets the result count
        cursor.execute(
            f"""
            SELECT m.id, m.target, m.content, m.level, m.created_at,
                   mv.distance
            FROM memories_vec mv
            JOIN memories m ON mv.rowid = m.id
            WHERE mv.embedding MATCH ?
              AND k = ?
              AND m.level = 1
              AND m.target IN ({placeholders})
            ORDER BY mv.distance ASC
            """,
            (embedding_bytes, limit, *target_filter),
        )
        rows = cursor.fetchall()
        return [
            {
                "id": r["id"],
                "target": r["target"],
                "content": r["content"],
                "score": 1.0 - float(r["distance"]) if r["distance"] is not None else None,
                "search_mode": "vector",
            }
            for r in rows
        ]
    except Exception as e:
        logger.warning("Vector search failed, falling back to keyword: %s", e)
        return None  # Signal caller to use keyword fallback


def _keyword_search(conn, query: Optional[str], target_filter: tuple, limit: int) -> List[dict]:
    """Perform LIKE-based keyword search."""
    cursor = conn.cursor()
    placeholders = ",".join("?" * len(target_filter))

    if query:
        # Simple LIKE search — works without FTS
        like_pattern = f"%{query}%"
        cursor.execute(
            f"""
            SELECT id, target, content, level, created_at
            FROM memories
            WHERE level = 1 AND target IN ({placeholders}) AND content LIKE ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (*target_filter, like_pattern, limit),
        )
    else:
        # No query — return most recent entries
        cursor.execute(
            f"""
            SELECT id, target, content, level, created_at
            FROM memories
            WHERE level = 1 AND target IN ({placeholders})
            ORDER BY id DESC
            LIMIT ?
            """,
            (*target_filter, limit),
        )

    rows = cursor.fetchall()
    return [
        {
            "id": r["id"],
            "target": r["target"],
            "content": r["content"],
            "score": None,
            "search_mode": "keyword",
        }
        for r in rows
    ]


def memory_search_tool(
    args: dict,
    db_path: Path = None,
    config: dict = None,
    **kwargs,
) -> str:
    """Tool handler for memory_search."""
    query = args.get("query", "").strip()
    target = args.get("target", "both")
    limit = int(args.get("limit", 5))

    # Allow db_path/config to be passed via kwargs (from agent context)
    if db_path is None:
        db_path = kwargs.get("db_path")
    if config is None:
        config = kwargs.get("config")

    return memory_search_handler(
        query=query,
        target=target,
        limit=limit,
        db_path=db_path,
        config=config,
    )


def check_memory_search_requirements() -> bool:
    """Memory search requires the memories table to exist."""
    try:
        import sqlite3
        db_path = DEFAULT_DB_PATH
        if not db_path.exists():
            return False
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute("SELECT 1 FROM memories LIMIT 0")
            return True
        except sqlite3.OperationalError:
            return False
        finally:
            conn.close()
    except Exception:
        return False


# =============================================================================
# OpenAI Function-Calling Schema
# =============================================================================

MEMORY_SEARCH_SCHEMA = {
    "name": "memory_search",
    "description": (
        "Search persistent memory entries using semantic or keyword search. "
        "Use this to find specific information stored in memory without reading all entries. "
        "Searches both 'memory' (agent notes) and 'user' (user profile) by default.\n\n"
        "Returns matching entries with relevance scores. "
        "Uses vector similarity search when embeddings are configured, "
        "falls back to keyword search otherwise."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query — what to look for in memory entries.",
            },
            "target": {
                "type": "string",
                "enum": ["memory", "user", "both"],
                "description": (
                    "Which store to search: 'memory' (agent notes), "
                    "'user' (user profile), or 'both' (default)."
                ),
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results to return (default: 5, max: 50).",
            },
        },
        "required": ["query"],
    },
}


# --- Registry ---
from tools.registry import registry

registry.register(
    name="memory_search",
    toolset="memory",
    schema=MEMORY_SEARCH_SCHEMA,
    handler=memory_search_tool,
    check_fn=check_memory_search_requirements,
    emoji="🔍",
)
