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
import re
import threading
import time
from typing import Any, Dict, List, Optional

from agent.memory_provider import MemoryProvider
from tools.registry import tool_error

logger = logging.getLogger(__name__)

# Circuit breaker: after this many consecutive failures, pause API calls
# for _BREAKER_COOLDOWN_SECS to avoid hammering a down server.
_BREAKER_THRESHOLD = 5
_BREAKER_COOLDOWN_SECS = 120


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

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
    }

    config_path = get_hermes_home() / "mem0.json"
    if config_path.exists():
        try:
            file_cfg = json.loads(config_path.read_text(encoding="utf-8"))
            config.update({k: v for k, v in file_cfg.items()
                           if v is not None and v != ""})
        except Exception:
            pass

    return config


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
        "Use for explicit preferences, corrections, decisions, or operational facts. "
        "Optional metadata lets callers separate preferences, doctrine, facts, and history."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "conclusion": {"type": "string", "description": "The fact to store."},
            "memory_class": {
                "type": "string",
                "enum": ["preference", "doctrine", "factual", "temporal"],
                "description": "Optional class override for the stored memory.",
            },
            "time_scope": {
                "type": "string",
                "enum": ["current", "past", "future", "timeless"],
                "description": "Optional time-scope override for the stored memory.",
            },
            "metadata": {
                "type": "object",
                "description": "Optional extra metadata stored alongside the memory.",
            },
        },
        "required": ["conclusion"],
    },
}

_EXPLICIT_PREFIX_RE = re.compile(r"^\[(?:PREF|RULE|FACT|HIST)(?:/(?:CURRENT|PAST|FUTURE|TIMELESS))?\]\s*")
_MEMORY_CLASS_PREFIX = {
    "preference": "PREF",
    "doctrine": "RULE",
    "factual": "FACT",
    "temporal": "HIST",
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
        self._sync_turn_mode = "full"
        self._prefetch_result = ""
        self._prefetch_lock = threading.Lock()
        self._prefetch_thread = None
        self._sync_thread = None
        self._write_thread = None
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
        config_path.write_text(json.dumps(existing, indent=2))

    def get_config_schema(self):
        return [
            {"key": "api_key", "description": "Mem0 Platform API key", "secret": True, "required": True, "env_var": "MEM0_API_KEY", "url": "https://app.mem0.ai"},
            {"key": "user_id", "description": "User identifier", "default": "hermes-user"},
            {"key": "agent_id", "description": "Agent identifier", "default": "hermes"},
            {"key": "rerank", "description": "Enable reranking for recall", "default": "true", "choices": ["true", "false"]},
            {"key": "sync_turn_mode", "description": "Automatic turn-to-memory extraction mode", "default": "full", "choices": ["full", "off"]},
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
        if "sync_turn_mode" in self._config:
            self._sync_turn_mode = str(self._config.get("sync_turn_mode", "full") or "full").strip().lower()
        elif self._config.get("sync_turns") is False:
            self._sync_turn_mode = "off"
        else:
            self._sync_turn_mode = "full"
        if self._sync_turn_mode not in {"full", "off"}:
            self._sync_turn_mode = "full"

    def _read_filters(self) -> Dict[str, Any]:
        """Filters for search/get_all — scoped to user only for cross-session recall."""
        return {"user_id": self._user_id}

    def _scoped_read_filters(self) -> Dict[str, Any]:
        """Fallback filters for stores that only return agent-scoped memories."""
        filters = self._read_filters().copy()
        if self._agent_id:
            filters["agent_id"] = self._agent_id
        return filters

    def _write_filters(self) -> Dict[str, Any]:
        """Filters for add — scoped to user + agent for attribution."""
        return {"user_id": self._user_id, "agent_id": self._agent_id}

    @staticmethod
    def _unwrap_results(response: Any) -> list:
        """Normalize Mem0 API response — v2 wraps results in {"results": [...]}."""
        if isinstance(response, dict):
            return response.get("results", [])
        if isinstance(response, list):
            return response
        return []

    @staticmethod
    def _strip_explicit_prefix(text: str) -> str:
        return _EXPLICIT_PREFIX_RE.sub("", (text or "").strip())

    @classmethod
    def _normalize_memory_class(cls, value: Optional[str], *, target: str = "memory", content: str = "") -> str:
        raw = str(value or "").strip().lower()
        aliases = {
            "pref": "preference",
            "preference": "preference",
            "user": "preference",
            "rule": "doctrine",
            "doctrine": "doctrine",
            "policy": "doctrine",
            "fact": "factual",
            "factual": "factual",
            "current_fact": "factual",
            "history": "temporal",
            "historical": "temporal",
            "temporal": "temporal",
            "past": "temporal",
        }
        if raw in aliases:
            return aliases[raw]
        if target == "user":
            return "preference"
        base = cls._strip_explicit_prefix(content).lower()
        if re.search(r"\b(do not|don't|never|must|should|unless|only if|expected to|keep .* on)\b", base):
            return "doctrine"
        if re.search(r"\b(previously|earlier|before|used to|was changed|retired|on 20\d{2}-\d{2}-\d{2}|as of)\b", base):
            return "temporal"
        return "factual"

    @staticmethod
    def _normalize_time_scope(value: Optional[str], content: str = "") -> str:
        raw = str(value or "").strip().lower()
        aliases = {
            "current": "current",
            "now": "current",
            "present": "current",
            "past": "past",
            "previous": "past",
            "historical": "past",
            "future": "future",
            "planned": "future",
            "timeless": "timeless",
            "rule": "timeless",
        }
        if raw in aliases:
            return aliases[raw]
        base = Mem0MemoryProvider._strip_explicit_prefix(content).lower()
        if re.search(r"\b(plan|planned|later|upcoming|will|future)\b", base):
            return "future"
        if re.search(r"\b(always|never|must|should|unless|only if|expected to)\b", base):
            return "timeless"
        if re.search(r"\b(previously|earlier|before|used to|was|were|retired|on 20\d{2}-\d{2}-\d{2}|as of)\b", base):
            return "past"
        return "current"

    @classmethod
    def _decorate_explicit_memory(
        cls,
        content: str,
        *,
        target: str = "memory",
        memory_class: Optional[str] = None,
        time_scope: Optional[str] = None,
    ) -> str:
        base = cls._strip_explicit_prefix(content)
        memory_class_norm = cls._normalize_memory_class(memory_class, target=target, content=base)
        time_scope_norm = cls._normalize_time_scope(time_scope, base)
        prefix = _MEMORY_CLASS_PREFIX.get(memory_class_norm, "FACT")
        if memory_class_norm == "preference":
            return f"[{prefix}] {base}"
        return f"[{prefix}/{time_scope_norm.upper()}] {base}"

    @classmethod
    def _build_explicit_metadata(
        cls,
        *,
        target: str,
        content: str,
        memory_class: Optional[str] = None,
        time_scope: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        source: str = "mem0_conclude",
        action: str = "add",
    ) -> Dict[str, Any]:
        merged = dict(metadata or {})
        merged.setdefault("memory_target", target)
        merged.setdefault("source", source)
        merged.setdefault("write_action", action)
        merged["memory_class"] = cls._normalize_memory_class(memory_class, target=target, content=content)
        merged["time_scope"] = cls._normalize_time_scope(time_scope, content)
        merged["explicit_memory"] = True
        return merged

    @classmethod
    def _format_memory_for_display(cls, text: str) -> str:
        return cls._strip_explicit_prefix(text)

    def system_prompt_block(self) -> str:
        return (
            "# Mem0 Memory\n"
            f"Active. User: {self._user_id}.\n"
            "Use mem0_search to find memories, mem0_conclude to store facts, "
            "mem0_profile for a full overview."
        )

    def _search_with_fallback(self, client: Any, *, query: str, rerank: bool, top_k: int) -> list:
        """Search user-wide first, then fall back to agent-scoped reads if empty."""
        results = self._unwrap_results(client.search(
            query=query,
            filters=self._read_filters(),
            rerank=rerank,
            top_k=top_k,
        ))
        if results or not self._agent_id:
            return results
        return self._unwrap_results(client.search(
            query=query,
            filters=self._scoped_read_filters(),
            rerank=rerank,
            top_k=top_k,
        ))

    def _get_all_with_fallback(self, client: Any) -> list:
        """Load user-wide memories first, then fall back to agent-scoped reads if empty."""
        memories = self._unwrap_results(client.get_all(filters=self._read_filters()))
        if memories or not self._agent_id:
            return memories
        return self._unwrap_results(client.get_all(filters=self._scoped_read_filters()))

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        if self._prefetch_thread and self._prefetch_thread.is_alive():
            self._prefetch_thread.join(timeout=3.0)
        with self._prefetch_lock:
            result = self._prefetch_result
            self._prefetch_result = ""
        if not result:
            return ""
        return f"## Mem0 Memory\n{result}"

    def queue_prefetch(self, query: str, *, session_id: str = "") -> None:
        if self._is_breaker_open():
            return

        def _run():
            try:
                client = self._get_client()
                results = self._search_with_fallback(
                    client,
                    query=query,
                    rerank=self._rerank,
                    top_k=5,
                )
                if results:
                    lines = [self._format_memory_for_display(r.get("memory", "")) for r in results if r.get("memory")]
                    with self._prefetch_lock:
                        self._prefetch_result = "\n".join(f"- {l}" for l in lines if l)
                self._record_success()
            except Exception as e:
                self._record_failure()
                logger.debug("Mem0 prefetch failed: %s", e)

        self._prefetch_thread = threading.Thread(target=_run, daemon=True, name="mem0-prefetch")
        self._prefetch_thread.start()

    def sync_turn(self, user_content: str, assistant_content: str, *, session_id: str = "") -> None:
        """Send the turn to Mem0 for server-side fact extraction (non-blocking)."""
        if self._is_breaker_open():
            return
        if self._sync_turn_mode == "off":
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
        return [PROFILE_SCHEMA, SEARCH_SCHEMA, CONCLUDE_SCHEMA]

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
                memories = self._get_all_with_fallback(client)
                self._record_success()
                if not memories:
                    return json.dumps({"result": "No memories stored yet."})
                lines = [self._format_memory_for_display(m.get("memory", "")) for m in memories if m.get("memory")]
                return json.dumps({"result": "\n".join(l for l in lines if l), "count": len(lines)})
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
                results = self._search_with_fallback(
                    client,
                    query=query,
                    rerank=rerank,
                    top_k=top_k,
                )
                self._record_success()
                if not results:
                    return json.dumps({"result": "No relevant memories found."})
                items = [
                    {
                        "memory": self._format_memory_for_display(r.get("memory", "")),
                        "score": r.get("score", 0),
                        "metadata": r.get("metadata", {}),
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
                explicit_text = self._decorate_explicit_memory(
                    conclusion,
                    target="memory",
                    memory_class=args.get("memory_class"),
                    time_scope=args.get("time_scope"),
                )
                explicit_metadata = self._build_explicit_metadata(
                    target="memory",
                    content=conclusion,
                    memory_class=args.get("memory_class"),
                    time_scope=args.get("time_scope"),
                    metadata=args.get("metadata") if isinstance(args.get("metadata"), dict) else None,
                    source="mem0_conclude",
                    action="add",
                )
                client.add(
                    [{"role": "user", "content": explicit_text}],
                    **self._write_filters(),
                    infer=False,
                    metadata=explicit_metadata,
                )
                self._record_success()
                return json.dumps({
                    "result": "Fact stored.",
                    "stored": self._format_memory_for_display(explicit_text),
                    "memory_class": explicit_metadata.get("memory_class"),
                    "time_scope": explicit_metadata.get("time_scope"),
                })
            except Exception as e:
                self._record_failure()
                return tool_error(f"Failed to store: {e}")

        return tool_error(f"Unknown tool: {tool_name}")

    def on_memory_write(
        self,
        action: str,
        target: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Mirror built-in memory writes to Mem0 using explicit classification metadata."""
        if self._is_breaker_open():
            return
        if action not in {"add", "replace"} or not (content or "").strip():
            return

        def _write():
            try:
                client = self._get_client()
                explicit_text = self._decorate_explicit_memory(
                    content,
                    target=target,
                    memory_class=(metadata or {}).get("memory_class") if isinstance(metadata, dict) else None,
                    time_scope=(metadata or {}).get("time_scope") if isinstance(metadata, dict) else None,
                )
                explicit_metadata = self._build_explicit_metadata(
                    target=target,
                    content=content,
                    memory_class=(metadata or {}).get("memory_class") if isinstance(metadata, dict) else None,
                    time_scope=(metadata or {}).get("time_scope") if isinstance(metadata, dict) else None,
                    metadata=metadata,
                    source="builtin_memory_tool",
                    action=action,
                )
                client.add(
                    [{"role": "user", "content": explicit_text}],
                    **self._write_filters(),
                    infer=False,
                    metadata=explicit_metadata,
                )
                self._record_success()
            except Exception as e:
                self._record_failure()
                logger.debug("Mem0 on_memory_write failed: %s", e)

        if self._write_thread and self._write_thread.is_alive():
            self._write_thread.join(timeout=2.0)
        self._write_thread = threading.Thread(target=_write, daemon=True, name="mem0-memwrite")
        self._write_thread.start()

    def shutdown(self) -> None:
        for t in (self._prefetch_thread, self._sync_thread, self._write_thread):
            if t and t.is_alive():
                t.join(timeout=5.0)
        with self._client_lock:
            self._client = None


def register(ctx) -> None:
    """Register Mem0 as a memory provider plugin."""
    ctx.register_memory_provider(Mem0MemoryProvider())
