"""Exa AI search and extract provider.

Exa (https://exa.ai) provides semantic search and content extraction APIs.
This module wraps the existing ``_exa_search()`` / ``_exa_extract()`` functions
from ``web_tools.py`` into proper ``WebSearchProvider`` / ``WebExtractProvider``
implementations so the ``ProviderRegistry`` can auto-discover them.

Configuration::

    # ~/.hermes/.env
    EXA_API_KEY=...
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

from tools.web_providers.base import WebExtractProvider, WebSearchProvider


class ExaSearchProvider(WebSearchProvider):
    """Search via Exa semantic search API."""

    required_env_vars = ["EXA_API_KEY"]

    def provider_name(self) -> str:
        return "exa"

    def is_configured(self) -> bool:
        return bool(os.getenv("EXA_API_KEY", "").strip())

    def search(self, query: str, limit: int = 5) -> Dict[str, Any]:
        from tools.web_tools import _exa_search

        return _exa_search(query, limit)


class ExaExtractProvider(WebExtractProvider):
    """Extract via Exa content API."""

    required_env_vars = ["EXA_API_KEY"]

    def provider_name(self) -> str:
        return "exa"

    def is_configured(self) -> bool:
        return bool(os.getenv("EXA_API_KEY", "").strip())

    async def extract(self, urls: List[str], **kwargs) -> Dict[str, Any]:
        from tools.web_tools import _exa_extract

        results = _exa_extract(urls)
        return {"success": True, "data": results}
