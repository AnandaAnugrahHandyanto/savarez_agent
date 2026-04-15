"""Firecrawl cloud browser provider."""

import logging
import os
from typing import Dict

import requests

from tools.browser_providers.base import CloudBrowserProvider

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.firecrawl.dev"


class FirecrawlProvider(CloudBrowserProvider):
    """Firecrawl (https://firecrawl.dev) cloud browser backend."""

    def provider_name(self) -> str:
        return "Firecrawl"

    def is_configured(self) -> bool:
        return bool(os.environ.get("FIRECRAWL_API_KEY"))

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def _api_url(self) -> str:
        return os.environ.get("FIRECRAWL_API_URL", _BASE_URL)

    def _headers(self) -> Dict[str, str]:
        api_key = os.environ.get("FIRECRAWL_API_KEY")
        if not api_key:
            raise ValueError(
                "FIRECRAWL_API_KEY environment variable is required. "
                "Get your key at https://firecrawl.dev"
            )
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

    def create_session(self, task_id: str) -> Dict[str, object]:
        ttl = int(os.environ.get("FIRECRAWL_BROWSER_TTL", "300"))

        body: Dict[str, object] = {"ttl": ttl}

        response = requests.post(
            f"{self._api_url()}/v2/browser",
            headers=self._headers(),
            json=body,
            timeout=30,
        )

        if not response.ok:
            raise RuntimeError(
                f"Failed to create Firecrawl browser session: "
                f"{response.status_code} {response.text}"
            )

        data = response.json()
        session_name = self.make_session_name(task_id)

        logger.info("Created Firecrawl browser session %s", session_name)

        return {
            "session_name": session_name,
            "bb_session_id": data["id"],
            "cdp_url": data["cdpUrl"],
            "features": {"firecrawl": True},
        }

    def close_session(self, session_id: str) -> bool:
        def _make_request(_config=None):
            return requests.delete(
                f"{self._api_url()}/v2/browser/{session_id}",
                headers=self._headers(),
                timeout=10,
            )
        # Firecrawl uses _headers() directly, so pass a dummy get_config
        def _get_config():
            self._headers()  # raises ValueError if missing
            return {}  # not used by _make_request
        return self._close_session_template(session_id, _get_config, _make_request)

    def emergency_cleanup(self, session_id: str) -> None:
        def _get_config_or_none():
            try:
                self._headers()
                return {}
            except ValueError:
                return None
        def _fire_and_forget(_config):
            requests.delete(
                f"{self._api_url()}/v2/browser/{session_id}",
                headers=self._headers(),
                timeout=5,
            )
        self._emergency_cleanup_template(
            session_id, _get_config_or_none, _fire_and_forget,
        )
