"""AnySearch web search — plugin form.

Subclasses :class:`agent.web_search_provider.WebSearchProvider`. Calls the
AnySearch MCP server (``api.anysearch.com/mcp``) via Streamable HTTP using
the MCP ``tools/call`` JSON-RPC method. No API key required — the public
endpoint is free and works reliably in regions where DuckDuckGo is blocked
(mainland China, some corporate networks).

Config keys this provider responds to::

    web:
      search_backend: "anysearch"   # explicit per-capability
      backend: "anysearch"          # shared fallback

The MCP endpoint URL can be overridden via env var::

    ANYSEARCH_MCP_URL=https://api.anysearch.com/mcp
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List

from agent.web_search_provider import WebSearchProvider

logger = logging.getLogger(__name__)

_DEFAULT_URL = "https://api.anysearch.com/mcp"


def _anysearch_url() -> str:
    """Return the AnySearch MCP URL from env, falling back to default."""
    try:
        from hermes_cli.config import get_env_value

        val = get_env_value("ANYSEARCH_MCP_URL")
    except Exception:
        val = None
    if val is None:
        val = os.getenv("ANYSEARCH_MCP_URL", "")
    return (val or "").strip() or _DEFAULT_URL


def _call_mcp_tool(
    tool_name: str, arguments: Dict[str, Any], *, timeout: int = 30
) -> Dict[str, Any]:
    """Call a tool on the AnySearch MCP server via Streamable HTTP.

    Sends a JSON-RPC ``tools/call`` request and returns the parsed result.
    Falls back gracefully on network / protocol errors.
    """
    import httpx

    url = _anysearch_url()
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }
    headers = {"Content-Type": "application/json", "Accept": "application/json"}

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException:
        return {"success": False, "error": f"AnySearch MCP request timed out ({timeout}s)"}
    except httpx.HTTPStatusError as exc:
        return {"success": False, "error": f"AnySearch HTTP {exc.response.status_code}: {exc.response.text[:200]}"}
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error": f"AnySearch MCP call failed: {exc}"}

    # Extract the result from JSON-RPC response
    if "error" in data:
        err = data["error"]
        return {"success": False, "error": f"AnySearch MCP error: {err.get('message', err)}"}

    result = data.get("result", {})
    content = result.get("content", [])

    # MCP tool results come as a list of content blocks; extract text
    text_parts = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            text_parts.append(block.get("text", ""))
        elif isinstance(block, str):
            text_parts.append(block)

    if not text_parts:
        return {"success": False, "error": "AnySearch returned empty result"}

    combined = "\n".join(text_parts)

    # Try to parse as JSON (structured search results)
    try:
        return json.loads(combined)
    except (json.JSONDecodeError, TypeError):
        pass

    # Return as plain text content
    return {"success": True, "data": {"web": [{"title": "Result", "url": "", "description": combined, "position": 1}]}}


class AnySearchWebSearchProvider(WebSearchProvider):
    """Web search via the AnySearch MCP API.

    Free, no API key required. Works reliably in mainland China and other
    regions where DuckDuckGo is blocked. Supports both search and extract
    via the MCP tools/call protocol.
    """

    @property
    def name(self) -> str:
        return "anysearch"

    @property
    def display_name(self) -> str:
        return "AnySearch (MCP)"

    def is_available(self) -> bool:
        """Always available — no API key required.

        The public MCP endpoint is free. We check for ``httpx`` importability
        as the only hard dependency.
        """
        try:
            import httpx  # noqa: F401

            return True
        except ImportError:
            return False

    def supports_search(self) -> bool:
        return True

    def supports_extract(self) -> bool:
        return True

    def search(self, query: str, limit: int = 5) -> Dict[str, Any]:
        """Execute a web search via AnySearch MCP."""
        result = _call_mcp_tool("search", {"query": query, "limit": limit})

        # Normalize the response to match the expected shape
        if result.get("success"):
            return result

        # If the raw result has a different shape, try to normalize
        if "data" in result and "web" in result.get("data", {}):
            return {"success": True, "data": result["data"]}

        return result

    def extract(self, urls: List[str], **kwargs: Any) -> Any:
        """Extract content from URLs via AnySearch MCP."""
        result = _call_mcp_tool("extract", {"urls": urls}, timeout=60)

        if result.get("success"):
            return result.get("data", [])

        # Return error in the expected list shape
        return [{"url": u, "title": "", "content": "", "error": result.get("error", "Unknown error")} for u in urls]

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": "AnySearch (MCP)",
            "badge": "free · no key · search + extract",
            "tag": "Free MCP-based search — works in China without VPN. No API key needed.",
            "env_vars": [
                {
                    "key": "ANYSEARCH_MCP_URL",
                    "prompt": "AnySearch MCP endpoint URL (optional, defaults to api.anysearch.com/mcp)",
                    "required": False,
                },
            ],
        }
