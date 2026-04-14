"""Abstract base class for cloud browser providers."""

import logging
import uuid
from abc import ABC, abstractmethod
from typing import Dict

logger = logging.getLogger(__name__)


class CloudBrowserProvider(ABC):
    """Interface for cloud browser backends (Browserbase, Steel, etc.).

    Implementations live in sibling modules and are registered in
    ``browser_tool._PROVIDER_REGISTRY``.  The user selects a provider via
    ``hermes setup`` / ``hermes tools``; the choice is persisted as
    ``config["browser"]["cloud_provider"]``.
    """

    @abstractmethod
    def provider_name(self) -> str:
        """Short, human-readable name shown in logs and diagnostics."""

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True when all required env vars / credentials are present.

        Called at tool-registration time (``check_browser_requirements``) to
        gate availability.  Must be cheap — no network calls.
        """

    @abstractmethod
    def create_session(self, task_id: str) -> Dict[str, object]:
        """Create a cloud browser session and return session metadata.

        Must return a dict with at least::

            {
                "session_name": str,   # unique name for agent-browser --session
                "bb_session_id": str,  # provider session ID (for close/cleanup)
                "cdp_url": str,        # CDP websocket URL
                "features": dict,      # feature flags that were enabled
            }

        ``bb_session_id`` is a legacy key name kept for backward compat with
        the rest of browser_tool.py — it holds the provider's session ID
        regardless of which provider is in use.
        """

    @abstractmethod
    def close_session(self, session_id: str) -> bool:
        """Release / terminate a cloud session by its provider session ID.

        Returns True on success, False on failure.  Should not raise.
        """

    @abstractmethod
    def emergency_cleanup(self, session_id: str) -> None:
        """Best-effort session teardown during process exit.

        Called from atexit / signal handlers.  Must tolerate missing
        credentials, network errors, etc. — log and move on.
        """

    # ------------------------------------------------------------------
    # Shared helpers — reduce duplication across provider implementations
    # ------------------------------------------------------------------

    def make_session_name(self, task_id: str) -> str:
        """Generate a consistent, unique session name.

        All providers use the same ``hermes_{task_id}_{random}`` pattern.
        """
        return f"hermes_{task_id}_{uuid.uuid4().hex[:8]}"

    def _close_session_template(
        self,
        session_id: str,
        get_config,
        http_request_fn,
    ) -> bool:
        """Template method for close_session with standardized error handling.

        Args:
            session_id: Provider session ID.
            get_config: Callable returning config dict, or raising ValueError.
            http_request_fn: Callable(config) -> requests.Response.

        Returns True on success (HTTP 200/201/204), False otherwise.
        """
        name = self.provider_name() if callable(self.provider_name) else getattr(self, '_provider_name', 'unknown')
        try:
            config = get_config()
        except (ValueError, KeyError):
            logger.warning(
                "Cannot close %s session %s — missing credentials",
                name, session_id,
            )
            return False

        try:
            response = http_request_fn(config)
            if response.status_code in (200, 201, 204):
                logger.debug("Successfully closed %s session %s", name, session_id)
                return True
            else:
                logger.warning(
                    "Failed to close %s session %s: HTTP %s - %s",
                    name, session_id,
                    response.status_code,
                    response.text[:200],
                )
                return False
        except Exception as e:
            logger.error("Exception closing %s session %s: %s", name, session_id, e)
            return False

    def _emergency_cleanup_template(
        self,
        session_id: str,
        get_config_or_none,
        http_request_fn,
    ) -> None:
        """Template method for emergency_cleanup with standardized error handling.

        Args:
            session_id: Provider session ID.
            get_config_or_none: Callable returning config dict or None.
            http_request_fn: Callable(config) -> None (fire-and-forget).
        """
        name = self.provider_name() if callable(self.provider_name) else getattr(self, '_provider_name', 'unknown')
        config = get_config_or_none()
        if config is None:
            logger.warning(
                "Cannot emergency-cleanup %s session %s — missing credentials",
                name, session_id,
            )
            return
        try:
            http_request_fn(config)
        except Exception as e:
            logger.debug(
                "Emergency cleanup failed for %s session %s: %s",
                name, session_id, e,
            )
