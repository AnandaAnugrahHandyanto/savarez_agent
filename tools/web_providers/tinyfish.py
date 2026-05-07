"""TinyFish Search and Fetch web provider.

TinyFish Search and Fetch are free on every plan (at time of writing) and use a
single ``TINYFISH_API_KEY``. Search returns ranked web results; Fetch renders
URLs with a real browser and returns clean extracted text.

Configuration::

    # ~/.hermes/.env
    TINYFISH_API_KEY=your-key

    # ~/.hermes/config.yaml
    web:
      backend: "tinyfish"

TinyFish does not provide a crawl API through this provider; use Firecrawl or
Tavily for ``web_crawl``.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List

import httpx

from tools.web_providers.base import WebExtractProvider, WebSearchProvider

logger = logging.getLogger(__name__)

_TINYFISH_SEARCH_ENDPOINT = "https://api.search.tinyfish.ai"
_TINYFISH_FETCH_ENDPOINT = "https://api.fetch.tinyfish.ai"


class TinyFishProvider(WebSearchProvider, WebExtractProvider):
    """Search and fetch via TinyFish's REST APIs."""

    def provider_name(self) -> str:
        return "tinyfish"

    def is_configured(self) -> bool:
        return bool(os.getenv("TINYFISH_API_KEY", "").strip())

    def _headers(self) -> Dict[str, str]:
        api_key = os.getenv("TINYFISH_API_KEY", "").strip()
        if not api_key:
            raise ValueError("TINYFISH_API_KEY is not set")
        return {
            "X-API-Key": api_key,
            "Accept": "application/json",
        }

    def search(self, query: str, limit: int = 5) -> Dict[str, Any]:
        """Execute a TinyFish Search request and return normalized results."""
        try:
            limit = max(1, min(int(limit), 100))
        except (TypeError, ValueError):
            limit = 5

        params: Dict[str, Any] = {"query": query}
        location = os.getenv("TINYFISH_SEARCH_LOCATION", "").strip()
        language = os.getenv("TINYFISH_SEARCH_LANGUAGE", "").strip()
        if location:
            params["location"] = location
        if language:
            params["language"] = language

        try:
            resp = httpx.get(
                _TINYFISH_SEARCH_ENDPOINT,
                params=params,
                headers=self._headers(),
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as exc:
            logger.warning("TinyFish Search HTTP error: %s", exc)
            return {
                "success": False,
                "error": f"TinyFish Search returned HTTP {exc.response.status_code}",
            }
        except (httpx.RequestError, ValueError) as exc:
            logger.warning("TinyFish Search request/parse error: %s", exc)
            return {"success": False, "error": f"TinyFish Search failed: {exc}"}

        raw_results = data.get("results", []) or []
        web_results = []
        for i, result in enumerate(raw_results[:limit]):
            web_results.append({
                "title": str(result.get("title", "") or ""),
                "url": str(result.get("url", "") or ""),
                "description": str(result.get("snippet", "") or ""),
                "position": int(result.get("position") or i + 1),
                **({"site_name": result.get("site_name")} if result.get("site_name") else {}),
            })

        logger.info("TinyFish Search '%s': %d results", query, len(web_results))
        return {"success": True, "data": {"web": web_results}}

    def extract(self, urls: List[str], **kwargs) -> Dict[str, Any]:
        """Fetch URL content with TinyFish Fetch and return normalized results."""
        fmt = kwargs.get("format") or "markdown"
        if fmt not in ("markdown", "html", "json"):
            fmt = "markdown"

        payload: Dict[str, Any] = {
            "urls": urls[:10],
            "format": fmt,
        }
        if kwargs.get("links") is not None:
            payload["links"] = bool(kwargs["links"])
        if kwargs.get("image_links") is not None:
            payload["image_links"] = bool(kwargs["image_links"])

        headers = self._headers()
        headers["Content-Type"] = "application/json"

        try:
            resp = httpx.post(
                _TINYFISH_FETCH_ENDPOINT,
                json=payload,
                headers=headers,
                timeout=75,
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as exc:
            logger.warning("TinyFish Fetch HTTP error: %s", exc)
            return {
                "success": False,
                "error": f"TinyFish Fetch returned HTTP {exc.response.status_code}",
            }
        except (httpx.RequestError, ValueError) as exc:
            logger.warning("TinyFish Fetch request/parse error: %s", exc)
            return {"success": False, "error": f"TinyFish Fetch failed: {exc}"}

        results = []
        for page in data.get("results", []) or []:
            text = page.get("text", "")
            if not isinstance(text, str):
                text = json.dumps(text, ensure_ascii=False)
            final_url = page.get("final_url") or page.get("url") or ""
            results.append({
                "url": final_url,
                "title": page.get("title") or "",
                "content": text,
                "raw_content": text,
                "metadata": {
                    "sourceURL": final_url,
                    "requestedURL": page.get("url") or "",
                    "title": page.get("title") or "",
                    "description": page.get("description") or "",
                    "language": page.get("language") or "",
                    "author": page.get("author") or "",
                    "published_date": page.get("published_date") or "",
                    "format": page.get("format") or fmt,
                    "latency_ms": page.get("latency_ms"),
                },
            })

        for error in data.get("errors", []) or []:
            results.append({
                "url": error.get("url", ""),
                "title": "",
                "content": "",
                "raw_content": "",
                "error": error.get("error") or "fetch_error",
                "metadata": {"sourceURL": error.get("url", "")},
            })

        logger.info("TinyFish Fetch: %d result(s), %d error(s)", len(data.get("results", []) or []), len(data.get("errors", []) or []))
        return {"success": True, "data": results}
