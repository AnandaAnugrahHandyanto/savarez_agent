"""Jina web search + content extraction plugin — bundled, auto-loaded.
"""

from __future__ import annotations

from plugins.web.jina.provider import JinaWebSearchProvider


def register(ctx) -> None:
    """Register the Jina provider with the plugin context."""
    ctx.register_web_search_provider(JinaWebSearchProvider())
