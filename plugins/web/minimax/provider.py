"""MiniMax search — plugin form using direct API calls.

Subclasses the plugin-facing :class:`agent.web_search_provider.WebSearchProvider`.
Mirrors the behavior of the official mmx CLI:
  - API: POST /v1/coding_plan/search
  - Auth: Bearer token from ~/.mmx/config.json
  - Returns raw results without HTML cleaning (consistent with mmx CLI)
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict

import httpx

from agent.web_search_provider import WebSearchProvider

logger = logging.getLogger(__name__)


# MiniMax search API endpoint
_SEARCH_ENDPOINT = "https://api.minimax.io/v1/coding_plan/search"
_CN_SEARCH_ENDPOINT = "https://api.minimaxi.com/v1/coding_plan/search"


def _get_config_path() -> Path:
    """Get the mmx config file path."""
    return Path.home() / ".mmx" / "config.json"


def _load_api_key() -> tuple[str | None, str | None]:
    """Load API key and region from mmx config file.

    Returns:
        tuple of (api_key, region) — region is 'cn' or 'global'
    """
    config_path = _get_config_path()
    if not config_path.exists():
        return None, None

    try:
        with open(config_path) as f:
            config = json.load(f)
        api_key = config.get("apiKey") or config.get("api_key")
        region = config.get("region", "global")
        return api_key, region
    except (json.JSONDecodeError, IOError):
        return None, None


def _get_search_endpoint(region: str) -> str:
    """Get the appropriate search endpoint based on region."""
    if region == "cn":
        return _CN_SEARCH_ENDPOINT
    return _SEARCH_ENDPOINT


class MiniMaxWebSearchProvider(WebSearchProvider):
    """MiniMax web search provider using direct API calls.

    Requires:
        - MiniMax API key configured in ~/.mmx/config.json
        - Valid API key with search permissions
    """

    @property
    def name(self) -> str:
        return "minimax"

    @property
    def display_name(self) -> str:
        return "MiniMax (mmx)"

    def is_available(self) -> bool:
        """Check if mmx CLI is installed (for reference), plus verify config exists."""
        has_mmx = shutil.which("mmx") is not None
        has_config = _get_config_path().exists()
        return has_mmx or has_config

    def supports_search(self) -> bool:
        return True

    def supports_extract(self) -> bool:
        return False

    def search(self, query: str, limit: int = 5) -> Dict[str, Any]:
        """Execute a MiniMax search via direct API call.

        Mimics mmx CLI behavior:
          - POST to /v1/coding_plan/search with { q: query }
          - Returns raw results with title, link, snippet, date
        """
        api_key, region = _load_api_key()

        if not api_key:
            # Fallback: try MINIMAX_API_KEY env var
            api_key = os.getenv("MINIMAX_API_KEY")
            if api_key:
                region = os.getenv("MINIMAX_REGION", "global")
            else:
                return {
                    "success": False,
                    "error": "No MiniMax API key found. Run `mmx auth login --api-key sk-xxxxx` or set MINIMAX_API_KEY env var.",
                }

        safe_limit = max(1, int(limit))
        endpoint = _get_search_endpoint(region)

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        body = {
            "q": query,
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(endpoint, headers=headers, json=body)
        except httpx.TimeoutException:
            logger.warning("MiniMax search timed out")
            return {"success": False, "error": "MiniMax search timed out after 30s"}
        except Exception as exc:
            logger.warning("MiniMax search HTTP error: %s", exc)
            return {"success": False, "error": f"MiniMax search failed: {exc}"}

        if response.status_code != 200:
            logger.warning("MiniMax search HTTP %d: %s", response.status_code, response.text[:200])
            return {"success": False, "error": f"MiniMax search failed with status {response.status_code}"}

        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            logger.warning("MiniMax search JSON parse error: %s", exc)
            return {"success": False, "error": f"Invalid JSON response: {exc}"}

        # Check for API-level errors
        base_resp = data.get("base_resp", {})
        if base_resp.get("status_code") and base_resp["status_code"] != 0:
            error_msg = base_resp.get("status_msg", f"API error {base_resp['status_code']}")
            return {"success": False, "error": f"MiniMax search API error: {error_msg}"}

        # Return raw mmx CLI format: { organic: [...], base_resp: {...} }
        # This matches the exact output of `mmx search query --output json`
        organic = data.get("organic", [])
        limited = organic[:safe_limit]
        logger.info("MiniMax search '%s': %d results (limit %d)", query, len(limited), limit)
        return {
            "success": True,
            "organic": limited,
            "base_resp": data.get("base_resp", {"status_code": 0, "status_msg": "success"}),
        }

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": "MiniMax (mmx)",
            "badge": "search only",
            "tag": "Search via MiniMax AI platform — requires mmx-cli and MiniMax API key",
            "env_vars": [
                {"key": "MINIMAX_API_KEY",
                 "prompt": "MiniMax API key",
                 "url": "https://platform.minimax.io/"},
            ],
        }
