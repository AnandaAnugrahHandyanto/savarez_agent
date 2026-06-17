"""
Adapter layer: connects ComplianceBotHandler to the Hermes gateway hook.

This module is the SINGLE integration point between the existing
ComplianceBotHandler (which has its own proven interface) and the
Hermes ``pre_gateway_dispatch`` hook convention.

Design principle: Handler logic stays untouched.  All translation
between hook kwargs and handler parameters happens here.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from pharma_compliance.bot_handler import ComplianceBotHandler

logger = logging.getLogger(__name__)


class PharmaCompliancePlugin:
    """Adapter that bridges pre_gateway_dispatch hook → ComplianceBotHandler.

    Lifecycle
    ---------
    1. Instantiated once in ``pharma_compliance/__init__.py:register()``.
    2. ``on_gateway_dispatch`` is called (as an async callback) by the
       Hermes hook invoker for EVERY incoming message on EVERY platform.
    3. Returns ``None`` to let the message pass through, or
       ``{"action": "reply", "text": "..."}`` to have the gateway reply
       directly and terminate dispatch.
    """

    # Only process messages from these platforms (case-insensitive match
    # against Platform.value).
    PLATFORMS: frozenset[str] = frozenset({"qqbot"})

    def __init__(self) -> None:
        # ComplianceBotHandler is stateless aside from its internal
        # SessionManager; single instance is correct.
        self._handler = ComplianceBotHandler()

    # ── Hook callback ───────────────────────────────────────────────────

    async def on_gateway_dispatch(
        self,
        event: Any,             # gateway.protocol.MessageEvent
        gateway: Any,           # gateway.run.GatewayRunner
        session_store: Any = None,
    ) -> Optional[Dict[str, Any]]:
        """``pre_gateway_dispatch`` hook callback.

        Kwargs (passed by ``gateway/run.py:_handle_message`` via
        ``hermes_cli.plugins.invoke_hook``):

            event
                ``MessageEvent`` with ``source.platform``,
                ``source.chat_id``, ``source.user_id``, ``text``.

            gateway
                ``GatewayRunner`` instance holding ``self.adapters``
                dict (not used by this adapter; control returns to the
                gateway for actual sending).

            session_store
                Session persistence store (not used by this adapter).

        Returns
        -------
        Optional[Dict[str, Any]]
            ``None``
                Let the message fall through to normal Agent dispatch.
            ``{"action": "reply", "text": "…"}``
                Instruct the gateway to send *text* as a direct reply
                and then **terminate** further dispatch.
        """
        # ── 1. Validate source ──────────────────────────────────────────
        source = getattr(event, "source", None)
        if source is None:
            return None

        platform_enum = getattr(source, "platform", None)
        if platform_enum is None:
            return None

        # Platform.value is the canonical string (e.g. "qqbot", "feishu")
        platform_str = str(getattr(platform_enum, "value", platform_enum)).lower()
        if platform_str not in self.PLATFORMS:
            # Not our platform — let other plugins / Agent handle it
            return None

        # ── 2. Extract message fields ───────────────────────────────────
        user_id = getattr(source, "user_id", None)
        text = getattr(event, "text", None)

        if not user_id or not text:
            return None

        # ── 3. Call ComplianceBotHandler ────────────────────────────────
        try:
            # Handler signature (bot_handler.py:137-153):
            #   handle_message(user_id, msg_type, content, metadata)
            handler_result = await self._handler.handle_message(
                user_id=str(user_id),
                msg_type="text",
                content=str(text),
                metadata={},
            )
        except Exception:
            logger.exception(
                "Pharma compliance handler error for user %s",
                user_id,
            )
            # On error, let message fall through to Agent (fail-open)
            return None

        # ── 4. Translate handler result → gateway hook action ───────────
        return self._translate_result(handler_result)

    # ── Translation logic ───────────────────────────────────────────────

    def _translate_result(self, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Translate ComplianceBotHandler return dict → hook action dict.

        Handler return keys (from ``bot_handler.py``):
            needs_followup   : bool      — True when handler wants to ask a question
            followup_message : str | None — the question text to send
            merged           : bool      — True when a task was finalized
            text_preview     : str | None — summary text for user confirmation
            warnings         : list[str] — compliance warnings

        Returns
        -------
        Optional[Dict]
            ``None``
                → fall through to Agent
            ``{"action": "reply", "text": "…"}``
                → gateway sends reply, terminates dispatch
        """
        # ── Case 1: Progressive follow-up question ──────────────────────
        if result.get("needs_followup"):
            followup = result.get("followup_message") or ""
            # _notify is a transient hint from bot_handler for skipped
            # fields (retry exhausted); prepend it if present
            notify = result.get("_notify") or ""
            if notify:
                followup = f"{notify}\n\n{followup}" if followup else notify
            if followup.strip():
                return {"action": "reply", "text": followup}
            # needs_followup=True but no message → fall through (edge case)
            return None

        # ── Case 2: Task finalized (merged) ─────────────────────────────
        if result.get("merged"):
            summary = result.get("text_preview") or ""
            warnings = result.get("warnings") or []

            reply = "✅ 记录完成"
            if summary:
                reply += f"\n\n{summary}"
            if warnings:
                reply += "\n\n" + "\n".join(f"  ⚠️ {w}" for w in warnings)

            return {"action": "reply", "text": reply}

        # ── Case 3: Neither follow-up nor merged ────────────────────────
        # (e.g. pending count update, needs_confirmation=True for low-STT-
        # confidence — these are handled by letting the Agent respond)
        return None
