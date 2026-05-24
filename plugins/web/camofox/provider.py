"""Camofox web extraction — plugin form.

Subclasses :class:`agent.web_search_provider.WebSearchProvider`. Talks to a
local Camofox REST API server, creates one ephemeral session per URL,
renders the accessibility snapshot to deterministic Markdown, and returns
web-tool result objects.

Camofox differs from other extract providers in three ways:

1. **No LLM post-processing.** The returned Markdown is already clean and
   deterministic — ``requires_llm_processing()`` returns False so the
   dispatcher skips the auxiliary-model summarization step.

2. **Per-URL policy gates.** Each URL is checked against the website
   access policy before extraction. Blocked URLs return a policy-blocked
   result rather than raising.

3. **Interrupt checks.** Extraction can be interrupted mid-batch; each
   URL is checked before dispatch so a cancelled batch doesn't waste
   Camofox sessions.

4. **Result guarding.** Results are validated (URL safety, redirect
   policy re-check) before being returned to the caller.

Config keys this provider responds to::

    web:
      extract_backend: "camofox"     # explicit per-capability
      backend: "camofox"             # shared fallback

Env vars::

    CAMOFOX_URL=...    # URL of the Camofox REST API server

The previous in-tree implementation lived at
``tools.camofox_web_extract`` with a special-case branch in
``tools/web_tools.py``; this file is the canonical replacement.
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import Any, Dict, List

import requests

from agent.web_search_provider import WebSearchProvider

logger = logging.getLogger(__name__)

_HEALTH_TIMEOUT = (3, 3)
_TAB_TIMEOUT = (10, 60)
_WAIT_TIMEOUT = (5, 15)
_SNAPSHOT_TIMEOUT = (10, 60)
_CLEANUP_TIMEOUT = (3, 10)


def _get_camofox_url() -> str:
    return os.getenv("CAMOFOX_URL", "").strip().rstrip("/")


def _camofox_health_check() -> bool:
    """Return True when the Camofox server is reachable."""
    base = _get_camofox_url()
    if not base:
        return False
    try:
        response = requests.get(f"{base}/health", timeout=_HEALTH_TIMEOUT)
        return response.status_code == 200
    except Exception:
        return False


def _extract_single(url: str) -> Dict[str, Any]:
    """Extract a single URL through an ephemeral Camofox tab."""
    from tools.web_accessibility_markdown import render_accessibility_markdown

    base = _get_camofox_url()
    if not base:
        return _error_result(url, "CAMOFOX_URL is not configured")

    user_id = f"web_extract_{uuid.uuid4().hex[:12]}"
    session_key = f"extract_{uuid.uuid4().hex[:12]}"
    tab_id = ""

    try:
        tab_response = requests.post(
            f"{base}/tabs",
            json={"userId": user_id, "sessionKey": session_key, "url": url},
            timeout=_TAB_TIMEOUT,
        )
        tab_response.raise_for_status()
        tab_data = _safe_json(tab_response)
        tab_id = str(tab_data.get("tabId") or tab_data.get("id") or "")
        if not tab_id:
            raise RuntimeError("Camofox did not return a tabId")

        _best_effort_wait(base, tab_id, user_id)

        snapshot_response = requests.get(
            f"{base}/tabs/{tab_id}/snapshot",
            params={"userId": user_id},
            timeout=_SNAPSHOT_TIMEOUT,
        )
        snapshot_response.raise_for_status()
        snapshot_data = _safe_json(snapshot_response)
        snapshot_text = str(snapshot_data.get("snapshot") or "")

        final_url = (
            snapshot_data.get("url")
            or snapshot_data.get("finalUrl")
            or snapshot_data.get("sourceURL")
            or tab_data.get("url")
            or url
        )
        title = str(snapshot_data.get("title") or tab_data.get("title") or "")
        markdown = render_accessibility_markdown(
            snapshot_text,
            url=str(final_url),
            title=title,
            emit_refs=False,
            emit_controls=False,
        )

        return {
            "url": str(final_url),
            "title": title,
            "content": markdown,
            "raw_content": markdown,
            "metadata": {
                "sourceURL": str(final_url),
                "extractor": "camofox",
            },
        }
    except Exception as exc:
        logger.debug("Camofox extraction failed for %s: %s", url, exc)
        return _error_result(url, str(exc))
    finally:
        _cleanup_session(base, user_id, session_key)


def _best_effort_wait(base: str, tab_id: str, user_id: str) -> None:
    """Call Camofox readiness wait when available; ignore unsupported routes."""
    try:
        response = requests.post(
            f"{base}/tabs/{tab_id}/wait",
            json={"userId": user_id},
            timeout=_WAIT_TIMEOUT,
        )
        if response.status_code in (404, 405):
            return
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.debug("Camofox wait unavailable/failed for tab %s: %s", tab_id, exc)
    except Exception as exc:
        logger.debug("Camofox wait failed for tab %s: %s", tab_id, exc)


def _cleanup_session(base: str, user_id: str, session_key: str) -> None:
    if not base:
        return
    try:
        requests.delete(
            f"{base}/sessions/{user_id}",
            json={"userId": user_id, "sessionKey": session_key},
            timeout=_CLEANUP_TIMEOUT,
        )
    except Exception as exc:
        logger.debug("Camofox session cleanup failed for %s: %s", user_id, exc)


def _safe_json(response: requests.Response) -> Dict[str, Any]:
    try:
        data = response.json()
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _error_result(url: str, error: str) -> Dict[str, Any]:
    return {
        "url": url,
        "title": "",
        "content": "",
        "raw_content": "",
        "error": error,
    }


def _policy_blocked_result(url: str, blocked: Dict[str, Any], title: str = "") -> Dict[str, Any]:
    """Build a result dict for a URL blocked by website access policy."""
    return {
        "url": url,
        "title": title,
        "content": "",
        "raw_content": "",
        "error": blocked["message"],
        "blocked_by_policy": {
            "host": blocked["host"],
            "rule": blocked["rule"],
            "source": blocked["source"],
        },
    }


def _unsafe_url_result(url: str, title: str = "") -> Dict[str, Any]:
    """Build a result dict for a URL that targets a private/internal address."""
    return {
        "url": url,
        "title": title,
        "content": "",
        "raw_content": "",
        "error": "Blocked: URL targets a private or internal network address",
    }


def _guard_extract_result(result: Dict[str, Any], requested_url: str) -> Dict[str, Any]:
    """Apply final URL guards before exposing Camofox-extracted content.

    Re-checks SSRF safety and website-access policy on the final URL
    (which may differ from the requested URL due to server-side redirects).
    """
    from tools.url_safety import is_safe_url
    from tools.website_policy import check_website_access

    final_url = str(result.get("url") or requested_url)
    title = str(result.get("title") or "")
    has_content = bool(result.get("content") or result.get("raw_content"))

    # Preserve backend per-URL errors that do not expose content.
    if result.get("error") and not has_content:
        result.setdefault("url", final_url)
        result.setdefault("title", title)
        result.setdefault("content", "")
        result.setdefault("raw_content", "")
        return result

    if not is_safe_url(final_url):
        return _unsafe_url_result(final_url, title)

    blocked = check_website_access(final_url)
    if blocked:
        logger.info(
            "Blocked redirected Camofox web_extract for %s by rule %s",
            blocked["host"], blocked["rule"],
        )
        return _policy_blocked_result(final_url, blocked, title)

    result["url"] = final_url
    result.setdefault("title", title)
    return result


class CamofoxWebSearchProvider(WebSearchProvider):
    """Camofox extract-only provider.

    Async extract with per-URL policy gates, interrupt checks, and
    result guarding. Bypasses LLM post-processing since Camofox returns
    deterministic Markdown from accessibility snapshots.
    """

    @property
    def name(self) -> str:
        return "camofox"

    @property
    def display_name(self) -> str:
        return "Camofox"

    def is_available(self) -> bool:
        """Return True when a configured Camofox server is reachable."""
        return _camofox_health_check()

    def supports_search(self) -> bool:
        return False

    def supports_extract(self) -> bool:
        return True

    def requires_llm_processing(self) -> bool:
        """Camofox returns deterministic Markdown — skip LLM summarization."""
        return False

    async def extract(self, urls: List[str], **kwargs: Any) -> List[Dict[str, Any]]:
        """Extract content from one or more URLs via Camofox.

        Handles per-URL policy gates, interrupt checks, and result
        guarding internally. One URL's failure does not kill the batch.
        """
        from tools.interrupt import is_interrupted as _is_interrupted
        from tools.website_policy import check_website_access

        logger.info("Camofox extract: %d URL(s)", len(urls))

        result_slots: List[Dict[str, Any] | None] = [None] * len(urls)
        extract_urls: List[str] = []
        extract_indices: List[int] = []

        for idx, url in enumerate(urls):
            if _is_interrupted():
                result_slots[idx] = {
                    "url": url, "title": "", "content": "",
                    "raw_content": "", "error": "Interrupted",
                }
                continue

            blocked = check_website_access(url)
            if blocked:
                logger.info(
                    "Blocked Camofox web_extract for %s by rule %s",
                    blocked["host"], blocked["rule"],
                )
                result_slots[idx] = _policy_blocked_result(url, blocked)
                continue

            extract_indices.append(idx)
            extract_urls.append(url)

        if extract_urls:
            tasks = [asyncio.to_thread(_extract_single, url) for url in extract_urls]
            extracted = list(await asyncio.gather(*tasks))
            for idx, extracted_result in zip(extract_indices, extracted):
                result_slots[idx] = _guard_extract_result(
                    extracted_result, urls[idx]
                )
            # Handle the unlikely case where gather returns fewer results
            for idx in extract_indices[len(extracted):]:
                result_slots[idx] = {
                    "url": urls[idx],
                    "title": "",
                    "content": "",
                    "raw_content": "",
                    "error": "Camofox extraction returned no result for this URL",
                }

        return [r for r in result_slots if r is not None]

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": "Camofox",
            "badge": "local",
            "tag": "Local accessibility-snapshot extraction. No API key — requires a running Camofox server.",
            "env_vars": [
                {
                    "key": "CAMOFOX_URL",
                    "prompt": "Camofox server URL",
                    "url": "",
                },
            ],
        }
