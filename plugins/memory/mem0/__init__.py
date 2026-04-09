"""Mem0 memory plugin — MemoryProvider interface.

Server-side LLM fact extraction, semantic search with reranking, and
automatic deduplication via the Mem0 Platform API.

Original PR #2933 by kartik-mem0, adapted to MemoryProvider ABC.

Config via environment variables:
  MEM0_API_KEY       — Mem0 Platform API key (required)
  MEM0_USER_ID       — User identifier (default: hermes-user)
  MEM0_AGENT_ID      — Agent identifier (default: hermes)

Or via $HERMES_HOME/mem0.json.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any, Dict, List

from agent.memory_provider import MemoryProvider
from tools.registry import tool_error
from utils import is_truthy_value

logger = logging.getLogger(__name__)

# Circuit breaker: after this many consecutive failures, pause API calls
# for _BREAKER_COOLDOWN_SECS to avoid hammering a down server.
_BREAKER_THRESHOLD = 5
_BREAKER_COOLDOWN_SECS = 120

# Curation thresholds for on_memory_write deduplication.
# When the built-in memory store writes a fact, we search Mem0 for similar
# existing memories.  These thresholds determine how we act:
#   UPDATE — best-match score >= this → update existing memory instead of adding
_CURATE_UPDATE_THRESHOLD = 0.7
#   DELETE — additional matches scoring >= this are treated as stale duplicates
_CURATE_DELETE_THRESHOLD = 0.85


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_CAMEL_TO_SNAKE = {
    "topK": "top_k",
    "searchThreshold": "search_threshold",
    "autoCapture": "auto_capture",
    "autoRecall": "auto_recall",
}


def _normalize_config_values(config: dict) -> dict:
    """Normalize bool-ish fields and camelCase aliases into canonical snake_case."""
    normalized = dict(config)

    # Accept camelCase aliases from config — map to snake_case canonical keys.
    # Important: base defaults may already contain snake_case keys, so precedence
    # must be decided from the *incoming* config rather than the copied dict.
    for camel, snake in _CAMEL_TO_SNAKE.items():
        incoming_has_snake = snake in config
        if camel in normalized and not incoming_has_snake:
            normalized[snake] = normalized.pop(camel)
        elif camel in normalized:
            normalized.pop(camel)  # explicit snake_case input takes precedence

    # Boolean coercion
    normalized["rerank"] = is_truthy_value(normalized.get("rerank"), default=True)
    normalized["keyword_search"] = is_truthy_value(
        normalized.get("keyword_search"), default=False
    )
    normalized["auto_capture"] = is_truthy_value(
        normalized.get("auto_capture"), default=False
    )
    normalized["auto_recall"] = is_truthy_value(
        normalized.get("auto_recall"), default=True
    )

    # Numeric coercion with bounds
    try:
        normalized["top_k"] = max(1, min(int(normalized.get("top_k", 3)), 50))
    except (TypeError, ValueError):
        normalized["top_k"] = 3
    try:
        normalized["search_threshold"] = max(
            0.0, min(float(normalized.get("search_threshold", 0.5)), 1.0)
        )
    except (TypeError, ValueError):
        normalized["search_threshold"] = 0.5

    return normalized


def _load_config() -> dict:
    """Load config from env vars, with $HERMES_HOME/mem0.json overrides.

    Environment variables provide defaults; mem0.json (if present) overrides
    individual keys.  This avoids a silent failure when the JSON file exists
    but is missing fields like ``api_key`` that the user set in ``.env``.
    """
    from hermes_constants import get_hermes_home

    config = {
        "api_key": os.environ.get("MEM0_API_KEY", ""),
        "user_id": os.environ.get("MEM0_USER_ID", "hermes-user"),
        "agent_id": os.environ.get("MEM0_AGENT_ID", "hermes"),
        "rerank": True,
        "keyword_search": False,
        "top_k": 3,
        "search_threshold": 0.5,
        "auto_capture": False,
        "auto_recall": True,
    }

    config_path = get_hermes_home() / "mem0.json"
    if config_path.exists():
        try:
            file_cfg = json.loads(config_path.read_text(encoding="utf-8"))
            # Canonicalize file-local aliases before merging onto defaults so a
            # camelCase override can beat the built-in snake_case default.
            for camel, snake in _CAMEL_TO_SNAKE.items():
                if camel in file_cfg and snake not in file_cfg:
                    file_cfg[snake] = file_cfg.pop(camel)
                elif camel in file_cfg:
                    file_cfg.pop(camel)
            config.update({k: v for k, v in file_cfg.items()
                           if v is not None and v != ""})
        except Exception:
            pass

    return _normalize_config_values(config)


# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

PROFILE_SCHEMA = {
    "name": "mem0_profile",
    "description": (
        "Retrieve all stored memories about the user — preferences, facts, "
        "project context. Fast, no reranking. Use at conversation start."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}

SEARCH_SCHEMA = {
    "name": "mem0_search",
    "description": (
        "Search memories by meaning. Returns relevant facts ranked by similarity. "
        "Set rerank=true for higher accuracy on important queries."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What to search for."},
            "rerank": {"type": "boolean", "description": "Enable reranking for precision (default: false)."},
            "top_k": {"type": "integer", "description": "Max results (default: 10, max: 50)."},
        },
        "required": ["query"],
    },
}

CONCLUDE_SCHEMA = {
    "name": "mem0_conclude",
    "description": (
        "Store a durable fact about the user. Stored verbatim (no LLM extraction). "
        "Use for explicit preferences, corrections, or decisions."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "conclusion": {"type": "string", "description": "The fact to store."},
        },
        "required": ["conclusion"],
    },
}

UPDATE_SCHEMA = {
    "name": "mem0_update",
    "description": (
        "Update an existing Mem0 memory by ID. Use this when a stored fact is wrong, stale, "
        "or needs correction without keeping the old version."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "memory_id": {"type": "string", "description": "The Mem0 memory ID to update."},
            "text": {"type": "string", "description": "The replacement memory text."},
        },
        "required": ["memory_id", "text"],
    },
}

DELETE_SCHEMA = {
    "name": "mem0_delete",
    "description": (
        "Delete an existing Mem0 memory by ID. Use this to remove wrong, duplicate, or stale memories."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "memory_id": {"type": "string", "description": "The Mem0 memory ID to delete."},
        },
        "required": ["memory_id"],
    },
}


# ---------------------------------------------------------------------------
# MemoryProvider implementation
# ---------------------------------------------------------------------------

class Mem0MemoryProvider(MemoryProvider):
    """Mem0 Platform memory with server-side extraction and semantic search."""

    def __init__(self):
        self._config = None
        self._client = None
        self._client_lock = threading.Lock()
        self._api_key = ""
        self._user_id = "hermes-user"
        self._agent_id = "hermes"
        self._rerank = True
        self._top_k = 3
        self._search_threshold = 0.5
        self._auto_capture = False
        self._auto_recall = True
        self._prefetch_result = ""
        self._prefetch_lock = threading.Lock()
        self._prefetch_thread = None
        self._sync_thread = None
        self._curate_thread = None
        # Circuit breaker state
        self._consecutive_failures = 0
        self._breaker_open_until = 0.0

    @property
    def name(self) -> str:
        return "mem0"

    def is_available(self) -> bool:
        cfg = _load_config()
        return bool(cfg.get("api_key"))

    def save_config(self, values, hermes_home):
        """Write config to $HERMES_HOME/mem0.json."""
        import json
        from pathlib import Path
        config_path = Path(hermes_home) / "mem0.json"
        existing = {}
        if config_path.exists():
            try:
                existing = json.loads(config_path.read_text())
            except Exception:
                pass
        existing.update(values)
        config_path.write_text(json.dumps(_normalize_config_values(existing), indent=2))

    def get_config_schema(self):
        return [
            {"key": "api_key", "description": "Mem0 Platform API key", "secret": True, "required": True, "env_var": "MEM0_API_KEY", "url": "https://app.mem0.ai"},
            {"key": "user_id", "description": "User identifier", "default": "hermes-user"},
            {"key": "agent_id", "description": "Agent identifier", "default": "hermes"},
            {"key": "rerank", "description": "Enable reranking for recall", "default": "true", "choices": ["true", "false"]},
            {"key": "top_k", "description": "Max memories returned by auto-recall prefetch (1-50)", "default": "3"},
            {"key": "search_threshold", "description": "Min similarity score for auto-recall filtering (0.0-1.0). Only applied when scores are present.", "default": "0.5"},
            {"key": "auto_capture", "description": "Automatically capture facts from each turn (sync_turn). Disable to save API usage on hobby plans.", "default": "false", "choices": ["true", "false"]},
            {"key": "auto_recall", "description": "Automatically recall relevant memories before each turn (prefetch). Disable to use manual mem0_search only.", "default": "true", "choices": ["true", "false"]},
        ]

    def _get_client(self):
        """Thread-safe client accessor with lazy initialization."""
        with self._client_lock:
            if self._client is not None:
                return self._client
            try:
                from mem0 import MemoryClient
                self._client = MemoryClient(api_key=self._api_key)
                return self._client
            except ImportError:
                raise RuntimeError("mem0 package not installed. Run: pip install mem0ai")

    def _is_breaker_open(self) -> bool:
        """Return True if the circuit breaker is tripped (too many failures)."""
        if self._consecutive_failures < _BREAKER_THRESHOLD:
            return False
        if time.monotonic() >= self._breaker_open_until:
            # Cooldown expired — reset and allow a retry
            self._consecutive_failures = 0
            return False
        return True

    def _record_success(self):
        self._consecutive_failures = 0

    def _record_failure(self):
        self._consecutive_failures += 1
        if self._consecutive_failures >= _BREAKER_THRESHOLD:
            self._breaker_open_until = time.monotonic() + _BREAKER_COOLDOWN_SECS
            logger.warning(
                "Mem0 circuit breaker tripped after %d consecutive failures. "
                "Pausing API calls for %ds.",
                self._consecutive_failures, _BREAKER_COOLDOWN_SECS,
            )

    def initialize(self, session_id: str, **kwargs) -> None:
        self._config = _load_config()
        self._api_key = self._config.get("api_key", "")
        # Prefer gateway-provided user_id for per-user memory scoping;
        # fall back to config/env default for CLI (single-user) sessions.
        self._user_id = kwargs.get("user_id") or self._config.get("user_id", "hermes-user")
        self._agent_id = self._config.get("agent_id", "hermes")
        self._rerank = self._config.get("rerank", True)
        self._top_k = self._config.get("top_k", 3)
        self._search_threshold = self._config.get("search_threshold", 0.5)
        self._auto_capture = self._config.get("auto_capture", False)
        self._auto_recall = self._config.get("auto_recall", True)

    def _read_filters(self) -> Dict[str, Any]:
        """Filters for search/get_all — scoped to user only for cross-session recall."""
        return {"user_id": self._user_id}

    def _write_filters(self) -> Dict[str, Any]:
        """Filters for add — scoped to user + agent for attribution."""
        return {"user_id": self._user_id, "agent_id": self._agent_id}

    @staticmethod
    def _unwrap_results(response: Any) -> list:
        """Normalize Mem0 API response — v2 wraps results in {"results": [...]}"""
        if isinstance(response, dict):
            return response.get("results", [])
        if isinstance(response, list):
            return response
        return []

    @staticmethod
    def _memory_id(item: dict) -> str:
        """Extract Mem0 memory ID across response variants."""
        return str(item.get("id") or item.get("memory_id") or "")

    def system_prompt_block(self) -> str:
        return (
            "# Mem0 Memory\n"
            f"Active. User: {self._user_id}.\n"
            "Use mem0_search to find memories, mem0_conclude to store facts, "
            "mem0_profile for a full overview."
        )

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        if self._prefetch_thread and self._prefetch_thread.is_alive():
            self._prefetch_thread.join(timeout=3.0)
        with self._prefetch_lock:
            result = self._prefetch_result
            self._prefetch_result = ""
        if not result:
            return ""
        return f"## Mem0 Memory\n{result}"

    def _filter_by_threshold(self, results: list) -> list:
        """Drop results below search_threshold when scores are present.

        If a result has no ``score`` key, it passes through — we never invent
        scores or discard results that simply lack scoring metadata.
        """
        threshold = self._search_threshold
        return [
            r for r in results
            if "score" not in r or r["score"] >= threshold
        ]

    def queue_prefetch(self, query: str, *, session_id: str = "") -> None:
        if not self._auto_recall:
            return
        if self._is_breaker_open():
            return

        def _run():
            try:
                client = self._get_client()
                results = self._unwrap_results(client.search(
                    query=query,
                    filters=self._read_filters(),
                    rerank=self._rerank,
                    top_k=self._top_k,
                ))
                results = self._filter_by_threshold(results)
                if results:
                    lines = [r.get("memory", "") for r in results if r.get("memory")]
                    with self._prefetch_lock:
                        self._prefetch_result = "\n".join(f"- {l}" for l in lines)
                self._record_success()
            except Exception as e:
                self._record_failure()
                logger.debug("Mem0 prefetch failed: %s", e)

        self._prefetch_thread = threading.Thread(target=_run, daemon=True, name="mem0-prefetch")
        self._prefetch_thread.start()

    def sync_turn(self, user_content: str, assistant_content: str, *, session_id: str = "") -> None:
        """Send the turn to Mem0 for server-side fact extraction (non-blocking)."""
        if not self._auto_capture:
            return
        if self._is_breaker_open():
            return

        def _sync():
            try:
                client = self._get_client()
                messages = [
                    {"role": "user", "content": user_content},
                    {"role": "assistant", "content": assistant_content},
                ]
                client.add(messages, **self._write_filters())
                self._record_success()
            except Exception as e:
                self._record_failure()
                logger.warning("Mem0 sync failed: %s", e)

        # Wait for any previous sync before starting a new one
        if self._sync_thread and self._sync_thread.is_alive():
            self._sync_thread.join(timeout=5.0)

        self._sync_thread = threading.Thread(target=_sync, daemon=True, name="mem0-sync")
        self._sync_thread.start()

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return [PROFILE_SCHEMA, SEARCH_SCHEMA, CONCLUDE_SCHEMA, UPDATE_SCHEMA, DELETE_SCHEMA]

    def handle_tool_call(self, tool_name: str, args: dict, **kwargs) -> str:
        if self._is_breaker_open():
            return json.dumps({
                "error": "Mem0 API temporarily unavailable (multiple consecutive failures). Will retry automatically."
            })

        try:
            client = self._get_client()
        except Exception as e:
            return tool_error(str(e))

        if tool_name == "mem0_profile":
            try:
                memories = self._unwrap_results(client.get_all(filters=self._read_filters()))
                self._record_success()
                if not memories:
                    return json.dumps({"result": "No memories stored yet."})
                items = [
                    {"id": self._memory_id(m), "memory": m.get("memory", "")}
                    for m in memories if m.get("memory")
                ]
                lines = [item["memory"] for item in items]
                return json.dumps({"result": "\n".join(lines), "count": len(items), "items": items})
            except Exception as e:
                self._record_failure()
                return tool_error(f"Failed to fetch profile: {e}")

        elif tool_name == "mem0_search":
            query = args.get("query", "")
            if not query:
                return tool_error("Missing required parameter: query")
            rerank = args.get("rerank", False)
            top_k = min(int(args.get("top_k", 10)), 50)
            try:
                results = self._unwrap_results(client.search(
                    query=query,
                    filters=self._read_filters(),
                    rerank=rerank,
                    top_k=top_k,
                ))
                self._record_success()
                if not results:
                    return json.dumps({"result": "No relevant memories found."})
                items = [
                    {
                        "id": self._memory_id(r),
                        "memory": r.get("memory", ""),
                        "score": r.get("score", 0),
                    }
                    for r in results
                ]
                return json.dumps({"results": items, "count": len(items)})
            except Exception as e:
                self._record_failure()
                return tool_error(f"Search failed: {e}")

        elif tool_name == "mem0_conclude":
            conclusion = args.get("conclusion", "")
            if not conclusion:
                return tool_error("Missing required parameter: conclusion")
            try:
                client.add(
                    [{"role": "user", "content": conclusion}],
                    **self._write_filters(),
                    infer=False,
                )
                self._record_success()
                return json.dumps({"result": "Fact stored."})
            except Exception as e:
                self._record_failure()
                return tool_error(f"Failed to store: {e}")

        elif tool_name == "mem0_update":
            memory_id = str(args.get("memory_id", "")).strip()
            text = str(args.get("text", "")).strip()
            if not memory_id:
                return tool_error("Missing required parameter: memory_id")
            if not text:
                return tool_error("Missing required parameter: text")
            try:
                client.update(memory_id=memory_id, text=text)
                self._record_success()
                return json.dumps({"result": "Memory updated.", "id": memory_id})
            except Exception as e:
                self._record_failure()
                return tool_error(f"Failed to update: {e}")

        elif tool_name == "mem0_delete":
            memory_id = str(args.get("memory_id", "")).strip()
            if not memory_id:
                return tool_error("Missing required parameter: memory_id")
            try:
                client.delete(memory_id)
                self._record_success()
                return json.dumps({"result": "Memory deleted.", "id": memory_id})
            except Exception as e:
                self._record_failure()
                return tool_error(f"Failed to delete: {e}")

        return tool_error(f"Unknown tool: {tool_name}")

    # -- Curation: dedupe/update/delete on built-in memory writes ----------

    def _curate_memory_write(self, content: str) -> Dict[str, Any]:
        """Search Mem0 for similar facts and dedupe/update/conclude.

        Synchronous — callers that need non-blocking behaviour should run
        this in a background thread (see :meth:`on_memory_write`).

        Returns a dict describing what happened::

            {"action": "concluded"}           — new fact stored
            {"action": "updated", "id": ...}  — existing memory updated
            {"action": "skipped"}             — exact duplicate, no-op
            {"action": "failed", ...}         — error (logged, non-fatal)

        Extra key ``deleted_ids`` lists any stale duplicates removed.
        """
        try:
            client = self._get_client()
        except Exception as exc:
            return {"action": "failed", "error": str(exc)}

        try:
            results = self._unwrap_results(client.search(
                query=content,
                filters=self._read_filters(),
                rerank=True,
                top_k=3,
            ))
        except Exception as exc:
            self._record_failure()
            return {"action": "failed", "error": str(exc)}

        deleted_ids: list = []

        if not results:
            # No existing memories — store as new fact.
            try:
                client.add(
                    [{"role": "user", "content": content}],
                    **self._write_filters(),
                    infer=False,
                )
                self._record_success()
                return {"action": "concluded"}
            except Exception as exc:
                self._record_failure()
                return {"action": "failed", "error": str(exc)}

        best = results[0]
        best_score = best.get("score", 0)
        best_id = self._memory_id(best)
        best_text = best.get("memory", "")

        if best_score >= _CURATE_UPDATE_THRESHOLD and best_id:
            # High similarity — same semantic fact.
            if best_text.strip().lower() == content.strip().lower():
                # Exact duplicate — nothing to do.
                self._record_success()
                return {"action": "skipped", "deleted_ids": deleted_ids}

            # Reworded/corrected — update the existing memory.
            try:
                client.update(memory_id=best_id, text=content)
            except Exception as exc:
                self._record_failure()
                return {"action": "failed", "error": str(exc)}

            # Clean up additional near-duplicates beyond the primary match.
            for extra in results[1:]:
                extra_score = extra.get("score", 0)
                extra_id = self._memory_id(extra)
                if (extra_score >= _CURATE_DELETE_THRESHOLD
                        and extra_id
                        and extra_id != best_id):
                    try:
                        client.delete(extra_id)
                        deleted_ids.append(extra_id)
                    except Exception:
                        logger.debug(
                            "Mem0 curate: failed to delete stale duplicate %s",
                            extra_id,
                        )

            self._record_success()
            return {"action": "updated", "id": best_id, "deleted_ids": deleted_ids}

        # No strong match — store as genuinely new fact.
        try:
            client.add(
                [{"role": "user", "content": content}],
                **self._write_filters(),
                infer=False,
            )
            self._record_success()
            return {"action": "concluded"}
        except Exception as exc:
            self._record_failure()
            return {"action": "failed", "error": str(exc)}

    def on_memory_write(self, action: str, target: str, content: str) -> None:
        """Curate Mem0 state when the built-in memory store writes.

        Searches for semantically similar existing memories and prefers
        updating or deleting stale entries over appending duplicates.
        Runs in a background thread so the main loop is never blocked.
        """
        if not content or action not in ("add", "replace"):
            return
        if self._is_breaker_open():
            return

        def _run():
            result = self._curate_memory_write(content)
            logger.debug("Mem0 curate result: %s", result)

        self._curate_thread = threading.Thread(
            target=_run, daemon=True, name="mem0-curate",
        )
        self._curate_thread.start()

    def shutdown(self) -> None:
        for t in (self._prefetch_thread, self._sync_thread, self._curate_thread):
            if t and t.is_alive():
                t.join(timeout=5.0)
        with self._client_lock:
            self._client = None


def register(ctx) -> None:
    """Register Mem0 as a memory provider plugin."""
    ctx.register_memory_provider(Mem0MemoryProvider())
