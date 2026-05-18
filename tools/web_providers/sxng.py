"""Local sxng-search wrapper web search provider.

This provider integrates a local command-line search broker (``sxng-search``)
into Hermes' web provider framework.  It is intentionally search-only: use a
separate extract backend (Firecrawl, Tavily, Exa, Parallel, or native) for page
content extraction.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Any, Dict, List

from .base import WebSearchProvider


class SxngSearchProvider(WebSearchProvider):
    """Search provider backed by the local ``sxng-search`` command."""

    def provider_name(self) -> str:
        return "sxng"

    def _resolve_command(self) -> str:
        explicit = os.getenv("SXNG_SEARCH_COMMAND", "").strip()
        if explicit:
            return explicit
        return shutil.which("sxng-search") or ""

    def is_configured(self) -> bool:
        return bool(self._resolve_command())

    @property
    def command(self) -> str:
        """Configured command name/path, for diagnostics only."""
        return self._resolve_command()

    def search(self, query: str, limit: int = 5) -> Dict[str, Any]:
        command = self._resolve_command()
        if not command:
            return {
                "success": False,
                "error": "sxng-search command not found. Set SXNG_SEARCH_COMMAND or install sxng-search on PATH.",
            }

        try:
            limit_int = int(limit)
        except (TypeError, ValueError):
            limit_int = 5
        limit_int = min(max(limit_int, 1), 100)

        timeout = _timeout_seconds()
        args = [command, str(query or ""), "--limit", str(limit_int), "--json"]
        try:
            completed = subprocess.run(
                args,
                text=True,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"sxng-search timed out after {timeout} seconds"}
        except OSError as exc:
            return {"success": False, "error": f"sxng-search failed to start: {exc}"}

        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "sxng-search failed").strip()
            return {"success": False, "error": detail[:1000]}

        try:
            payload = json.loads(completed.stdout or "{}")
        except json.JSONDecodeError as exc:
            return {"success": False, "error": f"Failed to parse sxng-search JSON output: {exc}"}

        return {"success": True, "data": {"web": _normalize_sxng_results(payload, limit_int)}}


def _timeout_seconds() -> int:
    raw = os.getenv("SXNG_SEARCH_TIMEOUT", "45").strip()
    try:
        value = int(raw)
    except ValueError:
        value = 45
    return min(max(value, 1), 300)


def _candidate_results(payload: Dict[str, Any]) -> List[Any]:
    if isinstance(payload.get("results"), list):
        return payload["results"]
    data = payload.get("data")
    if isinstance(data, dict) and isinstance(data.get("web"), list):
        return data["web"]
    if isinstance(payload.get("web"), list):
        return payload["web"]
    return []


def _normalize_sxng_results(payload: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
    web_results: List[Dict[str, Any]] = []
    for item in _candidate_results(payload):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("name") or "").strip()
        url = str(item.get("url") or item.get("link") or "").strip()
        if not title and not url:
            continue
        description = str(
            item.get("description")
            or item.get("content")
            or item.get("snippet")
            or item.get("summary")
            or ""
        ).strip()
        web_results.append({
            "title": title,
            "url": url,
            "description": description,
            "position": len(web_results) + 1,
        })
        if len(web_results) >= limit:
            break
    return web_results
