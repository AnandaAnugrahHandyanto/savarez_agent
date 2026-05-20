"""Jina AI Reader — free web content extraction provider.

Subclasses :class:`agent.web_search_provider.WebSearchProvider`.
Uses the public Jina Reader API (https://r.jina.ai/) which requires no
API key and returns clean markdown from any URL.

Config keys this provider responds to::

    web:
      extract_backend: "jina"    # explicit per-capability
      backend: "jina"            # shared fallback

No env vars required.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

from agent.web_search_provider import WebSearchProvider

logger = logging.getLogger(__name__)

JINA_READER_BASE = "https://r.jina.ai"


def _extract_title(text: str) -> str:
    """Pull the title from Jina Reader output or markdown H1."""
    if not text:
        return ""
    # Jina Reader prefixes "Title: <title>" on its own line
    title_match = re.search(r"^Title:\s*(.+)$", text, re.MULTILINE)
    if title_match:
        return title_match.group(1).strip()
    # Fallback: first H1 heading
    for line in text.splitlines()[:10]:
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
        if stripped.startswith("## "):
            return stripped[3:].strip()
    return ""


def _strip_jina_wrapper(text: str) -> str:
    """Remove Jina Reader metadata prefix if present.

    Jina wraps extracted content with::

        Title: ...
        URL Source: ...
        Published Time: ...
        Warning: ...
        Markdown Content:
        <actual markdown>

    Strip everything up to and including 'Markdown Content:' so the
    caller gets clean page content.
    """
    marker = "\nMarkdown Content:\n"
    idx = text.find(marker)
    if idx != -1:
        return text[idx + len(marker):].strip()
    return text.strip()


def _fetch_jina(url: str) -> Dict[str, Any]:
    """GET a single URL via Jina Reader and return a normalized result dict.

    Returns::

        {"url": str, "title": str, "content": str, "raw_content": str,
         "metadata": dict} | {"url": str, "error": str, ...}
    """
    import httpx

    target = url.strip()
    jina_url = f"{JINA_READER_BASE}/{target}"

    try:
        response = httpx.get(jina_url, timeout=60, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.warning("Jina Reader HTTP error for %s: %s", url, exc)
        return {
            "url": url,
            "title": "",
            "content": "",
            "raw_content": "",
            "error": f"Jina Reader returned HTTP {exc.response.status_code}",
            "metadata": {"sourceURL": url},
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("Jina Reader network error for %s: %s", url, exc)
        return {
            "url": url,
            "title": "",
            "content": "",
            "raw_content": "",
            "error": f"Jina Reader request failed: {exc}",
            "metadata": {"sourceURL": url},
        }

    text = response.text.strip()
    if not text:
        return {
            "url": url,
            "title": "",
            "content": "",
            "raw_content": "",
            "error": "Jina Reader returned empty content",
            "metadata": {"sourceURL": url},
        }

    title = _extract_title(text)
    clean_content = _strip_jina_wrapper(text)

    return {
        "url": url,
        "title": title,
        "content": clean_content,
        "raw_content": text,
        "metadata": {"sourceURL": url, "title": title},
    }


class JinaWebSearchProvider(WebSearchProvider):
    """Jina AI Reader — extract-only provider."""

    @property
    def name(self) -> str:
        return "jina"

    @property
    def display_name(self) -> str:
        return "Jina AI (Reader)"

    def is_available(self) -> bool:
        """Always available — Jina Reader requires no API key."""
        return True

    def supports_search(self) -> bool:
        return False

    def supports_extract(self) -> bool:
        return True

    def extract(self, urls: List[str], **kwargs: Any) -> List[Dict[str, Any]]:
        """Extract content from one or more URLs via Jina Reader.

        Sync — one sequential HTTP GET per URL. Returns the legacy
        list-of-results shape; per-URL failures become items with ``error``.
        """
        try:
            from tools.interrupt import is_interrupted
        except ImportError:
            is_interrupted = lambda: False  # noqa: E731

        if is_interrupted():
            return [
                {"url": u, "error": "Interrupted", "title": ""} for u in urls
            ]

        logger.info("Jina Reader extract: %d URL(s)", len(urls))
        results: List[Dict[str, Any]] = []
        for url in urls:
            if is_interrupted():
                results.append({"url": url, "error": "Interrupted", "title": ""})
                continue
            results.append(_fetch_jina(url))
        return results

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": "Jina AI (Reader)",
            "badge": "free",
            "tag": "No API key needed. Extracts clean markdown from any URL.",
            "env_vars": [],
        }
