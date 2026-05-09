"""Tavily search and extract provider.

Tavily (https://tavily.com) provides a search API optimized for AI agents.
This module wraps the existing ``_tavily_request()`` / normalization functions
from ``web_tools.py`` into proper ``WebSearchProvider`` / ``WebExtractProvider``
implementations so the ``ProviderRegistry`` can auto-discover them.

Configuration::

    # ~/.hermes/.env
    TAVILY_API_KEY=...
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

from tools.web_providers.base import WebExtractProvider, WebSearchProvider


class TavilySearchProvider(WebSearchProvider):
    """Search via Tavily AI search API."""

    required_env_vars = ["TAVILY_API_KEY"]

    def provider_name(self) -> str:
        return "tavily"

    def is_configured(self) -> bool:
        return bool(os.getenv("TAVILY_API_KEY", "").strip())

    def search(self, query: str, limit: int = 5) -> Dict[str, Any]:
        from tools.web_tools import _normalize_tavily_search_results, _tavily_request

        raw = _tavily_request(
            "search",
            {
                "query": query,
                "max_results": min(limit, 20),
                "include_raw_content": False,
                "include_images": False,
            },
        )
        return _normalize_tavily_search_results(raw)


class TavilyExtractProvider(WebExtractProvider):
    """Extract via Tavily content API."""

    required_env_vars = ["TAVILY_API_KEY"]

    def provider_name(self) -> str:
        return "tavily"

    def is_configured(self) -> bool:
        return bool(os.getenv("TAVILY_API_KEY", "").strip())

    async def extract(self, urls: List[str], **kwargs) -> Dict[str, Any]:
        from tools.web_tools import _normalize_tavily_documents, _tavily_request

        raw = _tavily_request("extract", {"urls": urls})
        results = _normalize_tavily_documents(raw)
        return {"success": True, "data": results}
