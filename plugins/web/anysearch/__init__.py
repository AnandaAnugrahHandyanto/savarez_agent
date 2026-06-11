"""AnySearch web search plugin — bundled, auto-loaded.

Backed by the public AnySearch MCP server (``api.anysearch.com/mcp``).
No API key required — free tier works reliably in mainland China and
other regions where DuckDuckGo is blocked or slow.
"""

from __future__ import annotations

from plugins.web.anysearch.provider import AnySearchWebSearchProvider


def register(ctx) -> None:
    """Register the AnySearch provider with the plugin context."""
    ctx.register_web_search_provider(AnySearchWebSearchProvider())
