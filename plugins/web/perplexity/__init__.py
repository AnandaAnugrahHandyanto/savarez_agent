"""Perplexity web search plugin — bundled, auto-loaded.

Backed by Perplexity's Search API (``POST /search``). Search only; the
dispatcher in :mod:`tools.web_tools` handles the async wrap when the caller
is async.
"""

from __future__ import annotations

from plugins.web.perplexity.provider import PerplexityWebSearchProvider


def register(ctx) -> None:
    """Register the Perplexity provider with the plugin context."""
    ctx.register_web_search_provider(PerplexityWebSearchProvider())
