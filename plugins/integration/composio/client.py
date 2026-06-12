"""Composio REST API client.

Thin async wrapper around the Composio v3 backend.  We deliberately
do **not** depend on the ``composio`` Python SDK so the plugin
remains hermes-installable without an extra dep.  Every method
maps 1:1 to a documented endpoint; if you need to add an endpoint,
match the style below.

Endpoints used (Composio v3, as of 2026-06):

    GET  /api/v3/tools/list            — list tools (filter by toolkit)
    GET  /api/v3/toolkits              — list all toolkits (slug + metadata)
    GET  /api/v3/connected_accounts    — list user's connected OAuth accounts
    POST /api/v3/connected_accounts/link/initiate
                                        — start a managed OAuth flow
    POST /api/v3/connected_accounts/{id}/refresh
                                        — refresh an expired token
    POST /api/v3/tools/execute          — execute a tool by slug

Authentication:  ``X-API-Key: <api_key>``  header on every call.

This module is plugin-internal — anything exported here is part of
the plugin's contract with the MCP server (``mcp_server.py``) and
the CLI setup wizard (``setup.py``).  No public Hermes API surface.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ComposioError(Exception):
    """Base error for any Composio call failure."""

    def __init__(self, message: str, *, status: int = 0, body: Any = None):
        super().__init__(message)
        self.status = status
        self.body = body


class ComposioAuthError(ComposioError):
    """Raised when the API key is missing/invalid (HTTP 401/403)."""


class ComposioNotFoundError(ComposioError):
    """Raised when a toolkit/tool/account does not exist (HTTP 404)."""


class ComposioRateLimitError(ComposioError):
    """Raised when the user exceeded their quota (HTTP 429)."""


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass
class ComposioConfig:
    """Configuration for the Composio client.

    Loaded from ``~/.hermes/composio.json`` (set by
    ``hermes composio setup``) or environment variables.  Fields are
    intentionally flat so they can be JSON-serialized round-trip.
    """

    api_key: str = ""
    base_url: str = "https://backend.composio.dev"
    user_id: str = "default"
    max_tools_per_toolkit: int = 6
    allowed_toolkits: List[str] = field(default_factory=list)
    allowlist_only: bool = False
    # Internal: set to the path of the config file on load
    config_path: str = ""

    @classmethod
    def from_global_config(cls) -> "ComposioConfig":
        """Load from ``~/.hermes/composio.json`` or fall back to env vars.

        Order of precedence (highest first):
          1. $HERMES_HOME/composio.json
          2. COMPOSIO_API_KEY env var (api_key only)
          3. Hardcoded defaults
        """
        from hermes_constants import get_hermes_home
        from pathlib import Path
        import json as _json

        cfg = cls()
        home = get_hermes_home()
        cfg.config_path = str(home / "composio.json")

        path = Path(cfg.config_path)
        if path.exists():
            try:
                raw = _json.loads(path.read_text())
                cfg.api_key = str(raw.get("api_key") or "")
                cfg.base_url = str(raw.get("base_url") or cfg.base_url)
                cfg.user_id = str(raw.get("user_id") or cfg.user_id)
                cfg.max_tools_per_toolkit = int(
                    raw.get("max_tools_per_toolkit", cfg.max_tools_per_toolkit)
                )
                cfg.allowed_toolkits = list(raw.get("allowed_toolkits") or [])
                cfg.allowlist_only = bool(raw.get("allowlist_only", False))
            except Exception as exc:
                logger.warning("composio.json parse error: %s", exc)

        # Env var fallbacks
        if not cfg.api_key:
            cfg.api_key = os.environ.get("COMPOSIO_API_KEY", "")
        cfg.base_url = os.environ.get("COMPOSIO_BASE_URL", cfg.base_url)
        cfg.user_id = os.environ.get("COMPOSIO_USER_ID", cfg.user_id)
        return cfg

    def save(self) -> None:
        """Write config to ``config_path`` (atomic, mode 0600)."""
        from utils import atomic_json_write
        data = {
            "api_key": self.api_key,
            "base_url": self.base_url,
            "user_id": self.user_id,
            "max_tools_per_toolkit": self.max_tools_per_toolkit,
            "allowed_toolkits": self.allowed_toolkits,
            "allowlist_only": self.allowlist_only,
        }
        atomic_json_write(self.config_path, data, mode=0o600)

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def as_dict_safe(self) -> Dict[str, Any]:
        """Return a dict with ``api_key`` redacted (for logging/status)."""
        d = {
            "base_url": self.base_url,
            "user_id": self.user_id,
            "max_tools_per_toolkit": self.max_tools_per_toolkit,
            "allowed_toolkits": self.allowed_toolkits,
            "allowlist_only": self.allowlist_only,
            "api_key_set": bool(self.api_key),
        }
        return d


# ---------------------------------------------------------------------------
# Response dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ComposioTool:
    """A single Composio tool.

    ``input_schema`` is the JSON Schema object Composio returns for
    the tool's arguments; we pass it through verbatim into the MCP
    tool definition.
    """

    slug: str
    toolkit: str
    name: str = ""
    description: str = ""
    input_schema: Dict[str, Any] = field(default_factory=dict)

    def mcp_tool_name(self) -> str:
        """Return the tool name the MCP server will expose.

        Format: ``composio_<slug>`` (e.g. ``composio_gmail_send_email``).
        Composio slugs are globally unique across toolkits, so the
        toolkit prefix is redundant.  Underscores in slug are kept
        — MCP tool names allow alphanumerics, underscores, hyphens,
        dots.
        """
        return f"composio_{self.slug.lower().replace('-', '_')}"


@dataclass
class ComposioConnectedAccount:
    """A user's OAuth connection to a toolkit (e.g. alice@gmail.com on gmail)."""

    id: str
    toolkit: str
    user_id: str = ""
    status: str = "active"  # "active" | "expired" | "revoked"
    email: str = ""


# ---------------------------------------------------------------------------
# Heuristics
# ---------------------------------------------------------------------------

# Verb patterns used to rank tools within a toolkit.  Mirrors
# holaOS's HEURISTIC_VERB_PATTERNS in composio-tool-registry.ts:158.
_VERB_PRIORITY: List[str] = [
    "_FETCH_",
    "_LIST_",
    "_GET_",
    "_SEARCH_",
    "_SEND_",
    "_CREATE_",
    "_UPDATE_",
    "_DELETE_",
    "_EXECUTE_",
]


def rank_tools(tools: List[ComposioTool], limit: int) -> List[ComposioTool]:
    """Order tools within a toolkit by verb priority, then by slug.

    Used to choose the top N tools when a toolkit has hundreds
    (Composio's GMAIL toolkit alone has 50+ actions).  Without
    this filter, the LLM's tool catalog would explode.
    """
    def key(t: ComposioTool):
        upper = t.slug.upper()
        for i, pat in enumerate(_VERB_PRIORITY):
            if pat in upper:
                return (i, t.slug)
        return (len(_VERB_PRIORITY), t.slug)
    return sorted(tools, key=key)[:limit]


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class ComposioClient:
    """Async HTTP client for the Composio v3 backend.

    Holds an ``httpx.AsyncClient`` for the lifetime of the instance;
    callers should use it as an async context manager or call
    :meth:`aclose` on shutdown.  All methods are coroutines.
    """

    def __init__(self, config: ComposioConfig):
        self._config = config
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._config.base_url,
                headers={
                    "X-API-Key": self._config.api_key,
                    "Content-Type": "application/json",
                    "User-Agent": "hermes-agent-composio-plugin/1.0",
                },
                timeout=httpx.Timeout(30.0, connect=10.0),
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "ComposioClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

    # -- error mapping -----------------------------------------------------

    def _raise_for_status(self, resp: httpx.Response) -> None:
        if resp.status_code < 400:
            return
        body: Any
        try:
            body = resp.json()
        except Exception:
            body = resp.text
        msg = (
            (body.get("error", {}).get("message") if isinstance(body, dict) else None)
            or resp.text
            or f"HTTP {resp.status_code}"
        )
        if resp.status_code in (401, 403):
            raise ComposioAuthError(msg, status=resp.status_code, body=body)
        if resp.status_code == 404:
            raise ComposioNotFoundError(msg, status=resp.status_code, body=body)
        if resp.status_code == 429:
            raise ComposioRateLimitError(msg, status=resp.status_code, body=body)
        raise ComposioError(msg, status=resp.status_code, body=body)

    # -- endpoints ---------------------------------------------------------

    async def list_connected_accounts(
        self, user_id: Optional[str] = None
    ) -> List[ComposioConnectedAccount]:
        """Return the user's active OAuth connections.

        ``user_id`` defaults to :attr:`ComposioConfig.user_id`.
        """
        client = await self._get_client()
        uid = user_id or self._config.user_id
        resp = await client.get(
            "/api/v3/connected_accounts",
            params={"user_id": uid, "status": "active"},
        )
        self._raise_for_status(resp)
        data = resp.json()
        items = data.get("items") or data.get("connected_accounts") or []
        out: List[ComposioConnectedAccount] = []
        for raw in items:
            out.append(
                ComposioConnectedAccount(
                    id=str(raw.get("id") or raw.get("nanoid") or ""),
                    toolkit=str(raw.get("toolkit", {}).get("slug") or raw.get("toolkit") or ""),
                    user_id=str(raw.get("user_id") or uid),
                    status=str(raw.get("status") or "active"),
                    email=str(raw.get("email") or ""),
                )
            )
        return out

    async def list_toolkit_tools(
        self, toolkit: str, limit: int = 50
    ) -> List[ComposioTool]:
        """Return all tools for one toolkit (no ranking here).

        Use :func:`rank_tools` to pick the top N for the MCP catalog.
        """
        client = await self._get_client()
        resp = await client.get(
            "/api/v3/tools/list",
            params={"toolkit": toolkit, "limit": limit},
        )
        self._raise_for_status(resp)
        data = resp.json()
        items = data.get("items") or data.get("tools") or []
        out: List[ComposioTool] = []
        for raw in items:
            slug = str(raw.get("slug") or raw.get("name") or "")
            if not slug:
                continue
            out.append(
                ComposioTool(
                    slug=slug,
                    toolkit=toolkit,
                    name=str(raw.get("name") or slug),
                    description=str(raw.get("description") or ""),
                    input_schema=raw.get("input_parameters")
                    or raw.get("input_schema")
                    or {"type": "object", "properties": {}},
                )
            )
        return out

    async def execute_tool(
        self,
        tool_slug: str,
        *,
        connected_account_id: str,
        arguments: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute a tool and return the raw result envelope.

        ``arguments`` is the JSON-object the LLM supplied.  The
        response is a dict with at least ``data`` and
        ``successful`` keys (Composio v3 envelope).  Errors come
        back as ``successful=false`` plus ``error`` field — we do
        NOT raise for those, callers decide how to surface.
        """
        client = await self._get_client()
        body: Dict[str, Any] = {
            "tool_slug": tool_slug,
            "connected_account_id": connected_account_id,
        }
        if arguments:
            body["arguments"] = arguments
        resp = await client.post(
            "/api/v3/tools/execute",
            json=body,
            timeout=httpx.Timeout(120.0, connect=10.0),
        )
        # 4xx with a body of {"error": "..."} is a tool-level error,
        # not a transport failure — return it for the caller.
        if resp.status_code >= 400 and resp.status_code < 500:
            try:
                return resp.json()
            except Exception:
                return {"successful": False, "error": resp.text}
        self._raise_for_status(resp)
        return resp.json()

    async def initiate_oauth(
        self, toolkit: str, *, user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Start a managed OAuth flow and return the redirect URL.

        The user opens the returned ``redirect_url`` in a browser,
        approves, and Composio redirects back to the configured
        callback.  The connection is then visible via
        :meth:`list_connected_accounts`.
        """
        client = await self._get_client()
        uid = user_id or self._config.user_id
        body: Dict[str, Any] = {
            "toolkit": toolkit,
            "user_id": uid,
        }
        resp = await client.post(
            "/api/v3/connected_accounts/link/initiate",
            json=body,
        )
        self._raise_for_status(resp)
        return resp.json()


# ---------------------------------------------------------------------------
# Sync convenience wrappers (for setup wizard which is non-async)
# ---------------------------------------------------------------------------


def _run(coro):
    """Run an async coroutine from a sync context.  Tests use this too."""
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


def list_accounts_sync(config: ComposioConfig) -> List[ComposioConnectedAccount]:
    return _run(_make_client_and_call(config, lambda c: c.list_connected_accounts()))


def list_tools_sync(
    config: ComposioConfig, toolkit: str, limit: int = 50
) -> List[ComposioTool]:
    return _run(_make_client_and_call(config, lambda c: c.list_toolkit_tools(toolkit, limit)))


async def _make_client_and_call(config, fn):
    async with ComposioClient(config) as client:
        return await fn(client)


__all__ = [
    "ComposioConfig",
    "ComposioClient",
    "ComposioTool",
    "ComposioConnectedAccount",
    "ComposioError",
    "ComposioAuthError",
    "ComposioNotFoundError",
    "ComposioRateLimitError",
    "rank_tools",
    "list_accounts_sync",
    "list_tools_sync",
]
