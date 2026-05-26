"""OpenMemory plugin — MemoryProvider for self-hosted Mem0.

OpenMemory is the official self-hosted version of Mem0, providing semantic
memory with vector search, LLM-powered fact extraction, and persistence via
PostgreSQL + Qdrant. Unlike the cloud Mem0 Platform API, OpenMemory runs on
your own infrastructure (NAS, VPS, homelab).

Repository: https://github.com/mem0ai/mem0/tree/main/openmemory
Docker deployment guide: See README.md in this directory

Config via environment variables:
  OPENMEMORY_API_URL     — Base URL (required, e.g., http://localhost:8765)
  OPENMEMORY_APP_ID      — App identifier (default: hermes)
  OPENMEMORY_USER_ID     — User identifier (default: hermes-user)
  OPENMEMORY_API_KEY     — Optional API key for auth

Or via $HERMES_HOME/openmemory.json.
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

logger = logging.getLogger(__name__)

# Circuit breaker: after this many consecutive failures, pause API calls
# for _BREAKER_COOLDOWN_SECS to avoid hammering a down server.
_BREAKER_THRESHOLD = 5
_BREAKER_COOLDOWN_SECS = 120


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _load_config() -> dict:
    """Load config from env vars, with $HERMES_HOME/openmemory.json overrides.

    Environment variables provide defaults; openmemory.json (if present) overrides
    individual keys.  This avoids a silent failure when the JSON file exists
    but is missing fields like ``api_url`` that the user set in ``.env``.
    """
    from hermes_constants import get_hermes_home

    config = {
        "api_url": os.environ.get("OPENMEMORY_API_URL", ""),
        "app_id": os.environ.get("OPENMEMORY_APP_ID", "hermes"),
        "user_id": os.environ.get("OPENMEMORY_USER_ID", "hermes-user"),
        "api_key": os.environ.get("OPENMEMORY_API_KEY", ""),
    }

    config_path = get_hermes_home() / "openmemory.json"
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
    "name": "openmemory_profile",
    "description": (
        "Retrieve all stored memories about the user — preferences, facts, "
        "project context. Fast, no reranking. Use at conversation start."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}

SEARCH_SCHEMA = {
    "name": "openmemory_search",
    "description": (
        "Search memories by meaning. Returns relevant facts ranked by similarity. "
        "Useful for finding specific information from past conversations."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What to search for."},
            "top_k": {"type": "integer", "description": "Max results (default: 10, max: 50)."},
        },
        "required": ["query"],
    },
}

CONCLUDE_SCHEMA = {
    "name": "openmemory_conclude",
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


# ---------------------------------------------------------------------------
# MemoryProvider implementation
# ---------------------------------------------------------------------------

class OpenMemoryProvider(MemoryProvider):
    """Self-hosted Mem0 (OpenMemory) memory with semantic search."""

    def __init__(self):
        self._config = None
        self._api_url = ""
        self._app_id = "hermes"
        self._user_id = "hermes-user"
        self._api_key = ""
        self._prefetch_result = ""
        self._prefetch_lock = threading.Lock()
        self._prefetch_thread = None
        # Circuit breaker state
        self._consecutive_failures = 0
        self._breaker_open_until = 0.0

    @property
    def name(self) -> str:
        return "openmemory"

    def is_available(self) -> bool:
        cfg = _load_config()
        return bool(cfg.get("api_url"))

    def save_config(self, values, hermes_home):
        """Write config to $HERMES_HOME/openmemory.json."""
        import json
        from pathlib import Path
        config_path = Path(hermes_home) / "openmemory.json"
        config_path.write_text(json.dumps(values, indent=2), encoding="utf-8")

    def get_missing_requirements(self) -> List[Dict[str, str]]:
        cfg = _load_config()
        missing = []
        if not cfg.get("api_url"):
            missing.append({
                "var": "OPENMEMORY_API_URL",
                "description": "→ http://localhost:8765 or your NAS IP",
            })
        return missing

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return [PROFILE_SCHEMA, SEARCH_SCHEMA, CONCLUDE_SCHEMA]

    def _ensure_config(self):
        """Lazy-load config on first use."""
        if self._config is None:
            self._config = _load_config()
            self._api_url = self._config.get("api_url", "").rstrip("/")
            self._app_id = self._config.get("app_id", "hermes")
            self._user_id = self._config.get("user_id", "hermes-user")
            self._api_key = self._config.get("api_key", "")

    def _check_circuit_breaker(self) -> bool:
        """Return True if circuit breaker is open (API calls blocked)."""
        if self._breaker_open_until > time.time():
            return True
        return False

    def _record_success(self):
        """Reset circuit breaker on successful API call."""
        self._consecutive_failures = 0
        self._breaker_open_until = 0.0

    def _record_failure(self):
        """Increment failure counter; open breaker if threshold exceeded."""
        self._consecutive_failures += 1
        if self._consecutive_failures >= _BREAKER_THRESHOLD:
            self._breaker_open_until = time.time() + _BREAKER_COOLDOWN_SECS
            logger.warning(
                "OpenMemory circuit breaker opened after %d failures. "
                "Pausing API calls for %ds.",
                _BREAKER_THRESHOLD,
                _BREAKER_COOLDOWN_SECS,
            )

    def _api_request(self, method: str, endpoint: str, json_data: dict | None = None) -> dict:
        """Make HTTP request to OpenMemory API."""
        import requests

        self._ensure_config()

        if self._check_circuit_breaker():
            return {"error": "Circuit breaker open. API temporarily unavailable."}

        url = f"{self._api_url}{endpoint}"
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        try:
            if method == "GET":
                resp = requests.get(url, headers=headers, timeout=10)
            elif method == "POST":
                resp = requests.post(url, headers=headers, json=json_data, timeout=10)
            elif method == "PUT":
                resp = requests.put(url, headers=headers, json=json_data, timeout=10)
            else:
                return {"error": f"Unsupported method: {method}"}

            resp.raise_for_status()
            self._record_success()
            return resp.json()

        except requests.exceptions.Timeout:
            self._record_failure()
            return {"error": "Request timeout. OpenMemory server not responding."}
        except requests.exceptions.ConnectionError:
            self._record_failure()
            return {"error": "Connection failed. Is OpenMemory running?"}
        except requests.exceptions.HTTPError as e:
            self._record_failure()
            return {"error": f"HTTP {e.response.status_code}: {e.response.text[:200]}"}
        except Exception as e:
            self._record_failure()
            return {"error": f"Unexpected error: {str(e)}"}

    def initialize(self, session_id: str, **kwargs) -> None:
        """Initialize for a session."""
        self._ensure_config()
        # No additional setup needed for OpenMemory

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        """Return prefetched memories (non-blocking)."""
        with self._prefetch_lock:
            if self._prefetch_result:
                result = self._prefetch_result
                self._prefetch_result = ""
                return result
        return ""

    def queue_prefetch(self, query: str, *, session_id: str = "") -> None:
        """Queue background prefetch for next turn."""
        def _fetch():
            result = self._get_all_memories()
            with self._prefetch_lock:
                self._prefetch_result = result

        with self._prefetch_lock:
            if self._prefetch_thread and self._prefetch_thread.is_alive():
                return
            self._prefetch_thread = threading.Thread(target=_fetch, daemon=True)
            self._prefetch_thread.start()

    def _get_all_memories(self) -> str:
        """Fetch all memories for the user."""
        endpoint = f"/api/v1/memories/?user_id={self._user_id}&app_id={self._app_id}"
        result = self._api_request("GET", endpoint)

        if "error" in result:
            logger.error("OpenMemory profile fetch failed: %s", result["error"])
            return tool_error(f"Memory fetch failed: {result['error']}")

        memories = result.get("data", [])
        if not memories:
            return "No memories stored yet."

        lines = []
        for mem in memories:
            content = mem.get("memory", "")
            created = mem.get("created_at", "")
            lines.append(f"- {content} (stored: {created[:10]})")

        return "\n".join(lines)

    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs) -> str:
        """Dispatch tool calls to appropriate handlers."""
        self._ensure_config()

        if not self._api_url:
            return tool_error(
                "OpenMemory not configured. Set OPENMEMORY_API_URL in .env or "
                "run: hermes memory setup"
            )

        if tool_name == "openmemory_profile":
            return self._get_all_memories()

        elif tool_name == "openmemory_search":
            return self._search_memories(
                query=args.get("query", ""),
                top_k=args.get("top_k", 10),
            )

        elif tool_name == "openmemory_conclude":
            return self._add_memory(args.get("conclusion", ""))

        else:
            return tool_error(f"Unknown tool: {tool_name}")

    def _search_memories(self, query: str, top_k: int = 10) -> str:
        """Search memories semantically."""
        if not query:
            return tool_error("Search query cannot be empty.")

        endpoint = "/api/v1/memories/filter"
        payload = {
            "user_id": self._user_id,
            "app_id": self._app_id,
            "query": query,
            "limit": min(top_k, 50),
        }

        result = self._api_request("POST", endpoint, payload)

        if "error" in result:
            return tool_error(f"Search failed: {result['error']}")

        memories = result.get("data", [])
        if not memories:
            return "No matching memories found."

        lines = []
        for i, mem in enumerate(memories, 1):
            content = mem.get("memory", "")
            score = mem.get("score", 0.0)
            lines.append(f"{i}. {content} (relevance: {score:.2f})")

        return "\n".join(lines)

    def _add_memory(self, content: str) -> str:
        """Store a new memory."""
        if not content:
            return tool_error("Memory content cannot be empty.")

        endpoint = "/api/v1/memories/"
        payload = {
            "user_id": self._user_id,
            "app_id": self._app_id,
            "memory": content,
        }

        result = self._api_request("POST", endpoint, payload)

        if "error" in result:
            return tool_error(f"Failed to store memory: {result['error']}")

        memory_id = result.get("data", {}).get("id", "")
        return json.dumps({
            "success": True,
            "memory_id": memory_id,
            "stored": content,
        })


# ---------------------------------------------------------------------------
# Plugin registration
# ---------------------------------------------------------------------------

def get_provider() -> MemoryProvider:
    """Entry point for Hermes memory plugin system."""
    return OpenMemoryProvider()
