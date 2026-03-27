"""Honcho memory provider for Hermes Agent (stub — Phase 2).

Honcho is Hermes Agent's built-in cross-session user modeling system. Its
integration is currently tightly coupled to AIAgent (client management,
session keys, config resolution, migration) and the gateway (persistent
manager caching across short-lived per-message agent instances).

This stub documents the mapping between Honcho's existing hooks and the
MemoryProvider interface. Full migration to MemoryProvider is Phase 2 work
that requires:
    1. Extracting client/session management from AIAgent.__init__
    2. Moving gateway _honcho_managers caching into the provider
    3. Handling the write_frequency="session" semantics

Current Honcho integration points (in run_agent.py):
    - _activate_honcho()           → on_session_start()
    - Honcho profile/context block → get_session_context()
    - _honcho_prefetch()           → get_turn_context()
    - _inject_honcho_turn_context  → inject_provider_context() [already unified]
    - _shutdown_gateway_honcho()   → on_session_end()

NOTE: This file is NOT registered in create_default_registry() yet.
Honcho continues to use its existing direct integration in run_agent.py
until Phase 2 migration is complete.
"""

import logging
from typing import Optional

from memory_provider import MemoryProvider

logger = logging.getLogger(__name__)


class HonchoProvider(MemoryProvider):
    """Honcho cross-session user modeling provider.

    Phase 2: This will replace the direct Honcho hooks in run_agent.py
    and gateway/run.py. For now it serves as documentation and a test
    target proving the MemoryProvider interface accommodates Honcho's
    lifecycle requirements.
    """

    @property
    def name(self) -> str:
        return "honcho"

    def is_available(self) -> bool:
        """Check for honcho config + API key."""
        try:
            from honcho_integration.client import HonchoClientConfig
            hcfg = HonchoClientConfig.from_global_config()
            return bool(hcfg and hcfg.enabled and hcfg.api_key)
        except (ImportError, Exception):
            return False

    def on_session_start(self, session_id: str, label: str = "") -> None:
        """Phase 2: Will replace _activate_honcho() in run_agent.py.

        Requires: client creation, session key resolution, memory migration,
        tool surface rebuild. Currently too coupled to AIAgent internals.
        """
        logger.debug("HonchoProvider.on_session_start() — stub (Phase 2)")

    def get_session_context(self) -> Optional[str]:
        """Phase 2: Will replace the Honcho profile/context system prompt block.

        Currently this context is assembled by Honcho's own session manager
        and injected during system prompt building in run_agent.py.
        """
        logger.debug("HonchoProvider.get_session_context() — stub (Phase 2)")
        return None

    def get_turn_context(self, user_message: str) -> Optional[str]:
        """Phase 2: Will replace _honcho_prefetch() in run_agent.py.

        Note: Honcho prefetch already wraps its output with a [System note:]
        prefix. When migrated, this formatting should move here so the
        inject_provider_context() helper stays format-agnostic.
        """
        logger.debug("HonchoProvider.get_turn_context() — stub (Phase 2)")
        return None

    def on_session_end(self, summary: str = "",
                       transcript: list = None,
                       session_title: str = None) -> None:
        """Phase 2: Will replace _shutdown_gateway_honcho() in gateway/run.py.

        Requires: flushing queued writes (write_frequency="session" semantics),
        proper cleanup of persistent manager state.
        """
        logger.debug("HonchoProvider.on_session_end() — stub (Phase 2)")
