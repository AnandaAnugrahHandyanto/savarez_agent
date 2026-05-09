"""Parallel AI search and extract provider.

Parallel (https://parallel.ai) provides an agentic search API.  This module
wraps the existing ``_parallel_search()`` / ``_parallel_extract()`` functions
from ``web_tools.py`` into proper ``WebSearchProvider`` / ``WebExtractProvider``
implementations so the ``ProviderRegistry`` can auto-discover them.

Configuration::

    # ~/.hermes/.env
    PARALLEL_API_KEY=...

    # Optional: search mode (fast / one-shot / agentic)
    PARALLEL_SEARCH_MODE=agentic
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

from tools.web_providers.base import WebExtractProvider, WebSearchProvider


class ParallelSearchProvider(WebSearchProvider):
    """Search via Parallel AI agentic search."""

    required_env_vars = ["PARALLEL_API_KEY"]

    def provider_name(self) -> str:
        return "parallel"

    def is_configured(self) -> bool:
        return bool(os.getenv("PARALLEL_API_KEY", "").strip())

    def search(self, query: str, limit: int = 5) -> Dict[str, Any]:
        from tools.web_tools import _parallel_search

        return _parallel_search(query, limit)


class ParallelExtractProvider(WebExtractProvider):
    """Extract via Parallel AI."""

    required_env_vars = ["PARALLEL_API_KEY"]

    def provider_name(self) -> str:
        return "parallel"

    def is_configured(self) -> bool:
        return bool(os.getenv("PARALLEL_API_KEY", "").strip())

    async def extract(self, urls: List[str], **kwargs) -> Dict[str, Any]:
        from tools.web_tools import _parallel_extract

        results = await _parallel_extract(urls)
        return {"success": True, "data": results}
