"""Jina AI Reader plugin — bundled, auto-loaded.

Free web content extraction via the Jina Reader API (https://r.jina.ai/).
No API key required. Extract-only; does not support search.
"""

from __future__ import annotations

from plugins.web.jina.provider import JinaWebSearchProvider


def register(ctx) -> None:
    """Register the Jina provider with the plugin context."""
    ctx.register_web_search_provider(JinaWebSearchProvider())
