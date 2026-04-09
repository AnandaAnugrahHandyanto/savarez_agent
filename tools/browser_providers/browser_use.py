"""Browser Use cloud browser provider."""

import logging
import os
import uuid
from typing import Dict

import requests

from tools.browser_providers.base import CloudBrowserProvider

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.browser-use.com/api/v2"


class BrowserUseProvider(CloudBrowserProvider):
    """Browser Use (https://browser-use.com) cloud browser backend."""

    def provider_name(self) -> str:
        return "Browser Use"

    def is_configured(self) -> bool:
        return bool(os.environ.get("BROWSER_USE_API_KEY"))

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def _headers(self) -> Dict[str, str]:
        api_key = os.environ.get("BROWSER_USE_API_KEY")
        if not api_key:
            raise ValueError(
                "BROWSER_USE_API_KEY environment variable is required. "
                "Get your key at https://browser-use.com"
            )
        return {
            "Content-Type": "application/json",
            "X-Browser-Use-API-Key": api_key,
        }

    def create_session(self, task_id: str) -> Dict[str, object]:
        response = requests.post(
            f"{_BASE_URL}/browsers",
            headers=self._headers(),
            json={},
            timeout=30,
        )

        if not response.ok:
            raise RuntimeError(
                f"Failed to create Browser Use session: "
                f"{response.status_code} {response.text}"
            )

        session_data = response.json()
        session_name = f"hermes_{task_id}_{uuid.uuid4().hex[:8]}"

        # The API returns an HTTPS discovery endpoint in ``cdpUrl``, not a
        # ``wss://`` URL.  agent-browser's CDP client (cdp_use) expects the
        # concrete websocket URL, so resolve it via the standard
        # ``/json/version`` endpoint before returning.
        https_cdp_url = session_data["cdpUrl"]
        try:
            discovery = requests.get(
                f"{https_cdp_url}/json/version",
                timeout=10,
            )
            discovery.raise_for_status()
            ws_url = discovery.json()["webSocketDebuggerUrl"]
        except Exception as exc:
            # Best effort cleanup — don't leak the session on failure.
            try:
                self.close_session(session_data["id"])
            except Exception:
                pass
            raise RuntimeError(
                f"Failed to resolve Browser Use CDP websocket URL from "
                f"{https_cdp_url}: {exc}"
            ) from exc

        logger.info(
            "Created Browser Use session %s (cost=%s, ws=%s)",
            session_name,
            session_data.get("browserCost", "?"),
            ws_url,
        )

        return {
            "session_name": session_name,
            "bb_session_id": session_data["id"],
            "cdp_url": ws_url,
            "features": {"browser_use": True},
        }

    def close_session(self, session_id: str) -> bool:
        try:
            response = requests.patch(
                f"{_BASE_URL}/browsers/{session_id}",
                headers=self._headers(),
                json={"action": "stop"},
                timeout=10,
            )
            if response.status_code in (200, 201, 204):
                logger.debug("Successfully closed Browser Use session %s", session_id)
                return True
            else:
                logger.warning(
                    "Failed to close Browser Use session %s: HTTP %s - %s",
                    session_id,
                    response.status_code,
                    response.text[:200],
                )
                return False
        except Exception as e:
            logger.error("Exception closing Browser Use session %s: %s", session_id, e)
            return False

    def emergency_cleanup(self, session_id: str) -> None:
        api_key = os.environ.get("BROWSER_USE_API_KEY")
        if not api_key:
            logger.warning("Cannot emergency-cleanup Browser Use session %s — missing credentials", session_id)
            return
        try:
            requests.patch(
                f"{_BASE_URL}/browsers/{session_id}",
                headers={
                    "Content-Type": "application/json",
                    "X-Browser-Use-API-Key": api_key,
                },
                json={"action": "stop"},
                timeout=5,
            )
        except Exception as e:
            logger.debug("Emergency cleanup failed for Browser Use session %s: %s", session_id, e)
