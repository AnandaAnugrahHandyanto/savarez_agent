"""Carbon Voice platform package.

Carbon Voice is a voice-first messaging platform: it transcribes voice
messages to text (STT) before delivery and can re-synthesize the agent's
text replies as voice memos (TTS), so from Hermes' side it is a text-in /
text-out platform. The adapter connects over Socket.IO (primary) with a
REST polling fallback — no public webhook or tunnel required.

Re-exports the main adapter symbols so the gateway factory and CLI can do::

    from gateway.platforms.carbonvoice import (
        CarbonVoiceAdapter,
        check_carbonvoice_requirements,
        standalone_send,
    )

Modules (ported from the external hermes-plugin-carbonvoice):
    - ``adapter``       — CarbonVoiceAdapter (orchestrator)
    - ``api``           — REST client + ``standalone_send``
    - ``transport``     — Socket.IO + polling lifecycle
    - ``state``         — disk-persisted cursor
    - ``dedupe``        — in-memory seen-message TTL cache
    - ``reactions``     — visual ack + one-tap approval reactions
    - ``channels``      — chat_type + participant roster cache
    - ``audit``         — deny-by-default allow-list gate + ignored-sender log
    - ``permits``       — ApprovalStore (PairingStore wrapper) + command parser
    - ``parse``         — payload-shape helpers (pure)
    - ``gate``          — @mention gate
    - ``conversations`` — per-thread reply anchors + parent-text cache
    - ``constants``     — shared defaults
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Optional dependencies, probed once at import. httpx is mandatory (REST
# transport); python-socketio is optional (without it we fall back to REST
# polling only). Mirrors the external plugin's setup.check_requirements.
try:
    import httpx  # noqa: F401
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

try:
    import socketio  # noqa: F401
    SOCKETIO_AVAILABLE = True
except ImportError:
    SOCKETIO_AVAILABLE = False


def check_carbonvoice_requirements() -> bool:
    """Verify import-time deps. httpx is required; socketio is optional
    (polling-only fallback). Returns False only when a hard dep is missing."""
    if not HTTPX_AVAILABLE:
        logger.error("carbonvoice: httpx not installed")
        return False
    if not SOCKETIO_AVAILABLE:
        logger.warning(
            "carbonvoice: python-socketio not installed — running in "
            "polling-only mode (install with: "
            "pip install 'python-socketio[asyncio_client]')"
        )
    return True


from gateway.platforms.carbonvoice.adapter import (  # noqa: E402,F401
    CarbonVoiceAdapter,
)
from gateway.platforms.carbonvoice.api import (  # noqa: E402,F401
    CarbonVoiceAPI,
    standalone_send,
)

__all__ = [
    "CarbonVoiceAdapter",
    "CarbonVoiceAPI",
    "standalone_send",
    "check_carbonvoice_requirements",
    "HTTPX_AVAILABLE",
    "SOCKETIO_AVAILABLE",
]
