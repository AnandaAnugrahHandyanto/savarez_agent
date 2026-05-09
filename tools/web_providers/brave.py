"""Brave Search API provider.

Brave Search is a privacy-focused search engine with an independent index
(35B+ pages).  The API returns clean JSON — no CAPTCHAs, no JS redirects.

This provider implements ``WebSearchProvider`` only — search capability.
There is no extract endpoint; pair with Firecrawl/Tavily for extraction.

Features: web, news, images, videos, LLM-optimized context endpoint.

Configuration::

    # ~/.hermes/.env
    BRAVE_API_KEY=BSA...

    # ~/.hermes/config.yaml
    web:
      search_backend: "brave"
      extract_backend: "firecrawl"  # or any extract provider

Free tier: $5/mo credit (≈1,000 web searches).  No credit card required
for the free plan.  Sign up at https://api-dashboard.search.brave.com.

Rate limits: 50 QPS (web), 2 QPS (answers/LLM).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

from tools.web_providers.base import WebSearchProvider

logger = logging.getLogger(__name__)

BRAVE_API_BASE = "https://api.search.brave.com"


class BraveSearchProvider(WebSearchProvider):
    """Search via Brave Search API.

    Requires ``BRAVE_API_KEY`` in ``~/.hermes/.env``.
    Uses ``/res/v1/web/search`` endpoint with ``extra_snippets=True``
    for richer descriptions.
    """

    # ── ProviderRegistry metadata ────────────────────────────────────────
    required_env_vars = ["BRAVE_API_KEY"]

    def provider_name(self) -> str:
        return "brave"

    def is_configured(self) -> bool:
        """Return True when ``BRAVE_API_KEY`` is set."""
        return bool(os.getenv("BRAVE_API_KEY", "").strip())

    def search(self, query: str, limit: int = 5) -> Dict[str, Any]:
        """Execute a web search via Brave Search API.

        Returns normalized results::

            {
                "success": True,
                "data": {
                    "web": [
                        {
                            "title": str,
                            "url": str,
                            "description": str,
                            "position": int,
                        },
                        ...
                    ]
                }
            }

        On failure returns ``{"success": False, "error": str}``.
        """
        import httpx

        api_key = os.getenv("BRAVE_API_KEY", "").strip()
        if not api_key:
            return {"success": False, "error": "BRAVE_API_KEY is not set"}

        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": api_key,
        }

        params: Dict[str, Any] = {
            "q": query,
            "count": min(limit, 20),
            "extra_snippets": True,
        }

        try:
            resp = httpx.get(
                f"{BRAVE_API_BASE}/res/v1/web/search",
                params=params,
                headers=headers,
                timeout=15,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning("Brave Search HTTP %s: %s", exc.response.status_code, exc)
            return {
                "success": False,
                "error": f"Brave Search returned HTTP {exc.response.status_code}",
            }
        except httpx.RequestError as exc:
            logger.warning("Brave Search request error: %s", exc)
            return {
                "success": False,
                "error": f"Could not reach Brave Search API: {exc}",
            }

        try:
            data = resp.json()
        except Exception:
            logger.warning("Brave Search response parse error")
            return {
                "success": False,
                "error": "Could not parse Brave Search response as JSON",
            }

        # Brave returns "web" → "results" array, and optionally "news" results.
        # We also check the top-level "results" key for backward compat.
        web_raw = data.get("web", {})
        if isinstance(web_raw, dict):
            raw_results = web_raw.get("results", [])
        else:
            raw_results = data.get("results", [])

        # Map to normalized format — Brave uses "description" (not "content"/"snippet").
        web_results = []
        for i, r in enumerate(raw_results[:limit]):
            web_results.append(
                {
                    "title": str(r.get("title", "")),
                    "url": str(r.get("url", "")),
                    "description": str(r.get("description", "")),
                    "position": i + 1,
                }
            )

        logger.info(
            "Brave Search '%s': %d results (from %d raw, limit %d)",
            query,
            len(web_results),
            len(raw_results),
            limit,
        )

        return {"success": True, "data": {"web": web_results}}
