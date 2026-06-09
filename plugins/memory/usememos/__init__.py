"""Memos memory plugin — MemoryProvider interface.

Self-hosted lightweight note service (usememos/memos) for user-owned memory.
No pip dependencies — uses stdlib urllib for HTTP calls.

Config via environment variables:
  MEMOS_API_URL    — Memos instance URL (e.g. https://memos.example.com)
  MEMOS_ACCESS_TOKEN — API access token (required)

Or via $HERMES_HOME/usememos.json.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List

from agent.memory_provider import MemoryProvider
from tools.registry import tool_error

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _load_config() -> dict:
    """Load config from env vars, with $HERMES_HOME/usememos.json overrides."""
    from hermes_constants import get_hermes_home

    config = {
        "api_url": os.environ.get("MEMOS_API_URL", ""),
        "access_token": os.environ.get("MEMOS_ACCESS_TOKEN", ""),
        "default_visibility": "PRIVATE",
    }

    config_path = get_hermes_home() / "usememos.json"
    if config_path.exists():
        try:
            file_cfg = json.loads(config_path.read_text(encoding="utf-8"))
            config.update({k: v for k, v in file_cfg.items()
                           if v is not None and v != ""})
        except Exception:
            pass

    return config


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _api_request(base_url: str, token: str, method: str, path: str,
                 body: dict | None = None, params: dict | None = None) -> dict:
    """Make an authenticated request to the Memos API."""
    url = f"{base_url.rstrip('/')}/api/v1{path}"
    if params:
        url += "?" + urllib.parse.urlencode(
            {k: v for k, v in params.items() if v is not None}
        )

    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"HTTP {e.code}: {error_body}") from e


# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

LIST_SCHEMA = {
    "name": "memos_list",
    "description": (
        "List recent memos from the Memos instance. "
        "Returns the most recent notes stored by the user."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Max memos to return (default: 20, max: 50).",
            },
        },
        "required": [],
    },
}

SEARCH_SCHEMA = {
    "name": "memos_search",
    "description": (
        "Search memos by content keyword. Returns matching memos "
        "from the Memos instance."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Keyword to search for."},
            "limit": {
                "type": "integer",
                "description": "Max results (default: 10, max: 50).",
            },
        },
        "required": ["query"],
    },
}

ADD_SCHEMA = {
    "name": "memos_add",
    "description": (
        "Store a new memo/note in Memos. Use for durable facts, preferences, "
        "or observations the user wants to keep."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "The memo content to store (Markdown supported).",
            },
            "visibility": {
                "type": "string",
                "description": "Memo visibility: PRIVATE (default), PROTECTED, or PUBLIC.",
                "enum": ["PRIVATE", "PROTECTED", "PUBLIC"],
            },
        },
        "required": ["content"],
    },
}


# ---------------------------------------------------------------------------
# MemoryProvider implementation
# ---------------------------------------------------------------------------

class MemosMemoryProvider(MemoryProvider):
    """Memos self-hosted note service memory provider."""

    def __init__(self):
        self._config = None
        self._api_url = ""
        self._access_token = ""
        self._default_visibility = "PRIVATE"
        self._prefetch_result = ""
        self._prefetch_lock = threading.Lock()
        self._prefetch_thread = None

    @property
    def name(self) -> str:
        return "usememos"

    def is_available(self) -> bool:
        cfg = _load_config()
        return bool(cfg.get("api_url") and cfg.get("access_token"))

    def save_config(self, values, hermes_home):
        """Write config to $HERMES_HOME/usememos.json."""
        import json
        from pathlib import Path
        config_path = Path(hermes_home) / "usememos.json"
        existing = {}
        if config_path.exists():
            try:
                existing = json.loads(config_path.read_text())
            except Exception:
                pass
        existing.update(values)
        from utils import atomic_json_write
        atomic_json_write(config_path, existing, mode=0o600)

    def get_config_schema(self):
        return [
            {
                "key": "api_url",
                "description": "Memos instance URL (e.g. https://memos.example.com)",
                "required": True,
                "env_var": "MEMOS_API_URL",
                "url": "https://usememos.com",
            },
            {
                "key": "access_token",
                "description": "API access token from Memos settings",
                "secret": True,
                "required": True,
                "env_var": "MEMOS_ACCESS_TOKEN",
            },
            {
                "key": "default_visibility",
                "description": "Default visibility for new memos",
                "default": "PRIVATE",
                "choices": ["PRIVATE", "PROTECTED", "PUBLIC"],
            },
        ]

    def initialize(self, session_id: str, **kwargs) -> None:
        self._config = _load_config()
        self._api_url = self._config.get("api_url", "")
        self._access_token = self._config.get("access_token", "")
        self._default_visibility = self._config.get("default_visibility", "PRIVATE")

    def _list_memos(self, limit: int = 20) -> list:
        """Fetch recent memos from the Memos API."""
        result = _api_request(
            self._api_url, self._access_token, "GET", "/memos",
            params={"pageSize": str(limit)},
        )
        # API returns {"memos": [...]} or {"memos": [...], "nextPageToken": "..."}
        return result.get("memos", [])

    def system_prompt_block(self) -> str:
        return (
            "# Memos Memory\n"
            "Active. Self-hosted Memos instance.\n"
            "Use memos_list to browse recent notes, memos_search to find specific ones, "
            "memos_add to store new facts."
        )

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        if self._prefetch_thread and self._prefetch_thread.is_alive():
            self._prefetch_thread.join(timeout=3.0)
        with self._prefetch_lock:
            result = self._prefetch_result
            self._prefetch_result = ""
        if not result:
            return ""
        return f"## Memos Memory\n{result}"

    def queue_prefetch(self, query: str, *, session_id: str = "") -> None:
        def _run():
            try:
                memos = self._list_memos(limit=5)
                if memos:
                    lines = [m.get("content", "") for m in memos if m.get("content")]
                    with self._prefetch_lock:
                        self._prefetch_result = "\n".join(f"- {l}" for l in lines)
            except Exception as e:
                logger.debug("Memos prefetch failed: %s", e)

        self._prefetch_thread = threading.Thread(
            target=_run, daemon=True, name="memos-prefetch"
        )
        self._prefetch_thread.start()

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return [LIST_SCHEMA, SEARCH_SCHEMA, ADD_SCHEMA]

    def handle_tool_call(self, tool_name: str, args: dict, **kwargs) -> str:
        if not self._api_url or not self._access_token:
            return tool_error("Memos not configured. Run: hermes memory setup")

        if tool_name == "memos_list":
            limit = min(int(args.get("limit", 20)), 50)
            try:
                memos = self._list_memos(limit=limit)
                if not memos:
                    return json.dumps({"result": "No memos found."})
                items = [
                    {
                        "content": m.get("content", ""),
                        "created": m.get("createTime", ""),
                        "visibility": m.get("visibility", ""),
                    }
                    for m in memos
                ]
                return json.dumps({"results": items, "count": len(items)})
            except Exception as e:
                return tool_error(f"Failed to list memos: {e}")

        elif tool_name == "memos_search":
            query = args.get("query", "")
            if not query:
                return tool_error("Missing required parameter: query")
            limit = min(int(args.get("limit", 10)), 50)
            try:
                # Memos v1 API: list with content search via filter
                # Fallback: list all and filter client-side
                memos = self._list_memos(limit=50)
                query_lower = query.lower()
                matched = [
                    m for m in memos
                    if query_lower in m.get("content", "").lower()
                ][:limit]
                if not matched:
                    return json.dumps({"result": "No matching memos found."})
                items = [
                    {
                        "content": m.get("content", ""),
                        "created": m.get("createTime", ""),
                    }
                    for m in matched
                ]
                return json.dumps({"results": items, "count": len(items)})
            except Exception as e:
                return tool_error(f"Search failed: {e}")

        elif tool_name == "memos_add":
            content = args.get("content", "")
            if not content:
                return tool_error("Missing required parameter: content")
            visibility = args.get("visibility", self._default_visibility)
            try:
                result = _api_request(
                    self._api_url, self._access_token, "POST", "/memos",
                    body={"content": content, "visibility": visibility},
                )
                memo_name = result.get("name", result.get("uid", ""))
                return json.dumps({"result": "Memo stored.", "id": memo_name})
            except Exception as e:
                return tool_error(f"Failed to store memo: {e}")

        return tool_error(f"Unknown tool: {tool_name}")

    def shutdown(self) -> None:
        if self._prefetch_thread and self._prefetch_thread.is_alive():
            self._prefetch_thread.join(timeout=5.0)


def register(ctx) -> None:
    """Register Memos as a memory provider plugin."""
    ctx.register_memory_provider(MemosMemoryProvider())
