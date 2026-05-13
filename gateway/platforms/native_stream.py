"""Native Telegram streaming via sendMessageDraft (Bot API 9.5+).

This module encapsulates all logic for Telegram's native text streaming,
keeping the core telegram.py adapter minimal.  The ``NativeStreamProvider``
class provides:

  * ``is_supported`` — probe whether the current bot/chat supports drafts
  * ``send_frame``   — emit a single animated draft frame
  * ``resolve``      — factory that decides draft vs edit per-chat

Usage in the stream consumer::

    from gateway.platforms.native_stream import NativeStreamProvider

    provider = NativeStreamProvider.resolve(adapter, chat_type, metadata)
    if provider:
        ok = await provider.send_frame(chat_id, text)

The provider is intentionally decoupled from ``BasePlatformAdapter`` so it
can be tested and swapped independently.

Reference: https://core.telegram.org/bots/api#sendmessagedraft
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from gateway.platforms.base import SendResult

logger = logging.getLogger("gateway.native_stream")

# Class-wide monotonic counter for draft IDs.  Telegram animates a draft
# when the same draft_id is reused across consecutive calls in the same
# chat, so each response needs a fresh non-zero id.
_draft_id_counter: int = 0


def _next_draft_id() -> int:
    """Return a fresh, globally-unique draft_id for a new response."""
    global _draft_id_counter
    _draft_id_counter += 1
    return _draft_id_counter


class NativeStreamProvider:
    """Manages native sendMessageDraft streaming for a single response.

    Instances are short-lived — one per streamed agent response.  On any
    failure, ``disabled`` flips to True and the caller falls back to the
    edit-based path for the remainder of that response.
    """

    def __init__(self, adapter: Any, draft_id: int):
        self._adapter = adapter
        self._draft_id = draft_id
        self._failures = 0
        self.disabled = False
        self._last_sent_text = ""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def send_frame(
        self,
        chat_id: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Emit a single animated draft frame.

        Returns True if the frame landed.  On any failure, permanently
        disables this provider so subsequent calls are no-ops (the caller
        should switch to edit-based transport).
        """
        if self.disabled:
            return False

        # No-op: skip identical text
        if text == self._last_sent_text:
            return True

        try:
            result = await self._adapter.send_draft(
                chat_id=chat_id,
                draft_id=self._draft_id,
                content=text,
                metadata=metadata,
            )
        except Exception as e:
            logger.debug(
                "send_draft raised, disabling native stream for this run: %s", e,
            )
            self._failures += 1
            self.disabled = True
            return False

        if not getattr(result, "success", False):
            logger.debug(
                "send_draft returned success=False, disabling: %s",
                getattr(result, "error", "unknown"),
            )
            self._failures += 1
            self.disabled = True
            return False

        # Frame landed
        self._last_sent_text = text
        return True

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @staticmethod
    def supports(adapter: Any, chat_type: Optional[str] = None,
                 metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Check if the adapter supports native draft streaming for this chat.

        Delegates to ``adapter.supports_draft_streaming`` which gates on:
          - Bot API version (python-telegram-bot 22.6+)
          - Chat type (private/DM only for Telegram)
        """
        probe = getattr(adapter, "supports_draft_streaming", None)
        if probe is None:
            return False
        try:
            return bool(probe(chat_type=chat_type, metadata=metadata))
        except Exception:
            logger.debug("supports_draft_streaming probe raised", exc_info=True)
            return False

    @classmethod
    def resolve(
        cls,
        adapter: Any,
        transport: str,
        chat_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional["NativeStreamProvider"]:
        """Resolve the appropriate streaming provider for this response.

        Returns a ``NativeStreamProvider`` if native drafts should be used,
        or ``None`` to fall back to the edit-based path.

        ``transport`` is one of ``"auto"``, ``"draft"``, ``"edit"``.
        """
        transport = (transport or "auto").lower()

        if transport in ("edit", "off"):
            return None

        if not cls.supports(adapter, chat_type=chat_type, metadata=metadata):
            if transport == "draft":
                logger.debug(
                    "Draft streaming requested but unsupported (type=%r) — "
                    "falling back to edit",
                    chat_type,
                )
            return None

        draft_id = _next_draft_id()
        logger.debug(
            "Native stream provider created (draft_id=%s, chat_type=%r)",
            draft_id, chat_type,
        )
        return cls(adapter, draft_id)
