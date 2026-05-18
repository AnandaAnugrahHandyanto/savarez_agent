"""Vendored approval helper for the NATS plugin.

Mirrors the surface of ``gateway.platforms.base`` + ``tools.approval`` that
the NATS adapter uses for mid-stream dangerous-command approval round-trips.
The plugin imports from here instead of from core so it can load and function
on a stock NousResearch/hermes-agent checkout where the Core PR (Stage 6) has
not landed. See master plan §4 Dependency Point A.

When the Core PR HAS landed (working clone, post-Stage-6 upstream), the
helpers opportunistically delegate to the canonical core symbols via lazy
``import`` + ``hasattr`` feature detection — keeping a single source of truth
when both ship the same function. The fallback path runs the vendored copy.

This module MUST NOT top-level-import any of the Core-PR symbols listed in
``tests/gateway/test_nats_no_core_pr_dependency.py`` — every reference to
core must be lazy (function-local) and guarded by ``ImportError`` or
``hasattr``/``getattr``.
"""

from __future__ import annotations

import asyncio
import contextvars
import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from gateway.platforms.base import BasePlatformAdapter

logger = logging.getLogger(__name__)

# ── Approval reply tokens (verbatim from gateway/platforms/base.py:495-504) ──
_APPROVAL_REPLY_ONCE = frozenset(
    {"once", "o", "yes", "y", "ok", "okay", "approve", "approved", "allow", "1"}
)
_APPROVAL_REPLY_SESSION = frozenset({"session", "s"})
_APPROVAL_REPLY_ALWAYS = frozenset(
    {"always", "a", "permanent", "perm", "persist"}
)
_APPROVAL_REPLY_DENY = frozenset(
    {"deny", "d", "no", "n", "nope", "reject", "cancel", "stop", "block", "0"}
)

# ── Entry-id contextvar (vendored from tools/approval.py:534-537) ──
# Plugin-local — exists for symmetry with the core symbol surface. The gateway
# (when Core PR has landed) sets its OWN ``tools.approval._current_approval_entry_id``
# before invoking notify_cb; the plugin's ``get_current_approval_entry_id`` below
# reads core's value when present, falls back to this when not.
_current_approval_entry_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "_current_approval_entry_id_nats_plugin",
    default=None,
)


def get_current_approval_entry_id() -> Optional[str]:
    """Return entry id for the approval currently being notified.

    Delegates to ``tools.approval.get_current_approval_entry_id`` when that
    symbol exists (working clone + Stage-6 upstream) so the plugin reads the
    same contextvar the gateway sets. Falls back to the plugin's local
    contextvar otherwise — which on the reference clone is always ``None``,
    leading ``resolve_gateway_approval`` into its FIFO-oldest fallback. That
    degraded mode is the expected reference-clone behavior per master plan §4.
    """
    try:
        import tools.approval as _tap  # noqa: PLC0415 — lazy on purpose
    except ImportError:
        _tap = None
    if _tap is not None:
        _core_fn = getattr(_tap, "get_current_approval_entry_id", None)
        if _core_fn is not None:
            try:
                return _core_fn()
            except Exception:  # noqa: BLE001
                pass
    return _current_approval_entry_id.get()


def _format_approval_prompt(approval_data: Dict[str, Any]) -> str:
    """Render an approval request as a short prompt for ``request_interaction``.

    Verbatim from ``gateway/platforms/base.py``. Shape is intentionally
    transport-agnostic: plain text, no markdown fences that would be
    miscounted by callers counting code-block state. Long commands are
    truncated to 500 chars.
    """
    cmd = str(approval_data.get("command") or "")
    desc = str(approval_data.get("description") or "dangerous command")
    if len(cmd) > 500:
        cmd_preview = cmd[:500] + "…"
    else:
        cmd_preview = cmd
    return (
        f"⚠️ Dangerous command requires approval: {desc}\n\n"
        f"Command:\n{cmd_preview}\n\n"
        f"Reply with: once | session | always | deny"
    )


def _parse_approval_reply(reply: Optional[str]) -> str:
    """Map a free-form user reply to the canonical approval choice.

    Verbatim from ``gateway/platforms/base.py``. Returns one of
    ``"once"`` / ``"session"`` / ``"always"`` / ``"deny"``. Unknown / empty
    / ``None`` replies fall to ``"deny"`` — fail-safe matches the
    "no answer ⇒ blocked" semantic in ``tools/approval.py``.
    """
    if not isinstance(reply, str):
        return "deny"
    normalized = reply.strip().lower()
    if not normalized:
        return "deny"
    token = normalized.split()[0]
    if token in _APPROVAL_REPLY_ALWAYS:
        return "always"
    if token in _APPROVAL_REPLY_SESSION:
        return "session"
    if token in _APPROVAL_REPLY_ONCE:
        return "once"
    if token in _APPROVAL_REPLY_DENY:
        return "deny"
    return "deny"


def adapter_supports_request_interaction(adapter: "BasePlatformAdapter") -> bool:
    """True iff the adapter's concrete class overrides ``request_interaction``.

    Vendored from ``gateway/platforms/base.py``. Class-level comparison (not
    ``hasattr`` or instance-level ``getattr``) so ``MagicMock`` adapters in
    tests don't produce false positives — every attribute access on a mock
    returns a new mock, which would spuriously claim capability.

    ``BasePlatformAdapter`` itself is upstream (non-Core); the lazy import keeps
    AST-scan-friendly (no top-level import of base) but is harmless — base.py is
    always present in any Hermes checkout.
    """
    # The adapter must at minimum have a ``request_interaction`` attribute
    # on its concrete class; otherwise it can't be invoked regardless of
    # what the base declares.
    if not hasattr(type(adapter), "request_interaction"):
        return False
    try:
        from gateway.platforms.base import BasePlatformAdapter  # noqa: PLC0415
        base_method = BasePlatformAdapter.request_interaction
    except (ImportError, AttributeError):
        # Upstream base predates the ``request_interaction`` stub (Stage 3
        # reverted that addition; the Core PR re-adds it). If the adapter
        # has its own ``request_interaction``, there is no inherited default
        # to mistake it for — treat any present method as an override.
        return True
    return type(adapter).request_interaction is not base_method


def dispatch_approval_via_request_interaction(
    adapter: "BasePlatformAdapter",
    chat_id: str,
    session_key: str,
    approval_data: Dict[str, Any],
    loop: "asyncio.AbstractEventLoop",
    *,
    timeout: float = 300.0,
    entry_id: Optional[str] = None,
) -> bool:
    """Route a dangerous-command approval through ``adapter.request_interaction``.

    Vendored from ``gateway/platforms/base.py``. Returns ``True`` iff the
    adapter supports the hook and the coroutine was scheduled on ``loop``;
    the agent thread that called the notify bridge will then block on its
    ``_ApprovalEntry.event`` until the scheduled task resolves the approval
    via :func:`tools.approval.resolve_gateway_approval`. Returns ``False``
    when the adapter inherits the base default — the caller should then
    fall back to the legacy flow.

    Opportunistic upgrade: if
    ``gateway.platforms.base.dispatch_approval_via_request_interaction``
    exists in core (Stage-6 Core PR landed), delegate to it so both surfaces
    stay in lockstep. Else run the vendored copy below.

    ``entry_id`` is the process-unique tag of the ``_ApprovalEntry`` this
    dispatch is resolving. Caller MUST capture it synchronously via
    :func:`get_current_approval_entry_id` inside the notify callback BEFORE
    invoking this helper — contextvars don't propagate through
    ``asyncio.run_coroutine_threadsafe``.
    """
    try:
        from gateway.platforms import base as _gpb  # noqa: PLC0415
    except ImportError:
        _gpb = None
    if _gpb is not None:
        _core_fn = getattr(_gpb, "dispatch_approval_via_request_interaction", None)
        if _core_fn is not None:
            return _core_fn(
                adapter,
                chat_id,
                session_key,
                approval_data,
                loop,
                timeout=timeout,
                entry_id=entry_id,
            )

    # ── Vendored implementation (verbatim behavior from gateway/platforms/base.py:571-642) ──
    if not adapter_supports_request_interaction(adapter):
        return False

    prompt_text = _format_approval_prompt(approval_data)

    async def _run() -> None:
        reply: Optional[str] = None
        try:
            reply = await adapter.request_interaction(
                chat_id, prompt_text, kind="approval", timeout=timeout,
            )
        except Exception as exc:
            logger.warning(
                "request_interaction raised for approval (chat_id=%s): %s",
                chat_id,
                exc,
            )
        choice = _parse_approval_reply(reply)
        try:
            from tools.approval import resolve_gateway_approval  # noqa: PLC0415
            try:
                resolve_gateway_approval(session_key, choice, entry_id=entry_id)
            except TypeError:
                # Upstream ``resolve_gateway_approval`` predates the
                # ``entry_id`` kwarg (Core PR re-adds it). Fall back to
                # the FIFO signature so the approval still resolves —
                # parallel-subagent routing degrades to oldest-wins until
                # the Core PR lands. Mirrors the transport_authed
                # feature-detection pattern in adapter.py:register().
                resolve_gateway_approval(session_key, choice)
        except Exception as exc:
            logger.error(
                "Failed to resolve gateway approval for session %s: %s",
                session_key,
                exc,
            )

    try:
        asyncio.run_coroutine_threadsafe(_run(), loop)
    except Exception as exc:
        logger.error(
            "Failed to schedule request_interaction approval: %s", exc,
        )
        return False
    return True
