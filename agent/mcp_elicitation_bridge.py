"""Bridge between MCP server elicitation requests and platform-side button UIs.

When an external MCP server calls the standard
``elicitation/create`` request via rmcp's ``peer.create_elicitation``, the
mcp Python SDK's ``ClientSession`` invokes the ``elicitation_callback``
registered by ``tools/mcp_tool.py``. That callback delegates here.

This module:
  - Extracts enum choices from the elicitation schema (single-property
    string-enum, with optional enum_titles via the ``oneOf``/``const``/``title``
    layout the MCP spec defines for titled enums).
  - Calls a platform adapter's ``send_approval`` (registered at startup)
    to render the choices as inline-keyboard buttons.
  - Awaits the user's button tap on an asyncio.Future.
  - Returns the chosen value to the elicitation callback, which wraps it
    into an ``ElicitResult(action="accept", content={"choice": value})``.

Cross-loop note: Hermes runs MCP servers on a **dedicated background
event loop** (``tools/mcp_tool.py::_mcp_loop``), separate from the gateway
loop where the Telegram adapter (and ``self._bot``) lives. The send
callback is therefore invoked from a different loop than the one that
owns python-telegram-bot's internal asyncio primitives — naively
awaiting it would crash with "Event is bound to a different event loop".
We bridge by storing the platform's event loop at registration time and
using ``asyncio.run_coroutine_threadsafe`` to dispatch the send onto it.

All state is per-call; no allowlist or session memory is persisted. Each
elicitation gets its own button prompt with the action arguments shown.
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import uuid
from typing import Any, Awaitable, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Module state ──────────────────────────────────────────────────────────

_dict_lock = threading.Lock()
_pending: Dict[str, "asyncio.Future"] = {}

# Send-approval callback + the event loop it must be invoked on.
SendApprovalCallback = Callable[..., Awaitable[Any]]
_send_callback: Optional[SendApprovalCallback] = None
_send_loop: Optional[asyncio.AbstractEventLoop] = None


def register_send_callback(
    cb: SendApprovalCallback,
    loop: Optional[asyncio.AbstractEventLoop] = None,
) -> None:
    """Called by a platform adapter (Telegram, etc.) once it's running.

    The callback signature must be:

        async cb(*, chat_id: str, title: str, body: str,
                 approval_id: str, choices: list[dict[str, str]]) -> SendResult

    where each ``choices`` entry has ``{"label": str, "value": str}`` and the
    rendered buttons must carry callback_data of the form
    ``extappr:<idx>:<approval_id>`` so this module's
    :func:`resolve_elicitation` can be invoked when the user taps.

    ``loop`` is the platform's event loop. We dispatch the callback onto
    it via ``run_coroutine_threadsafe`` because the elicitation handler
    (and therefore this module's ``request_elicitation``) runs on a
    different loop. If ``loop`` is None, we'll grab the running loop the
    first time ``request_elicitation`` invokes us — but registering with
    an explicit loop from the platform's startup path is more reliable.
    """
    global _send_callback, _send_loop
    _send_callback = cb
    _send_loop = loop


def resolve_elicitation(approval_id: str, choice_value: str) -> bool:
    """Called by the platform adapter when a user taps an extappr: button.

    Returns True if the approval was found and resolved (the awaiting
    coroutine in :func:`request_elicitation` will wake up and return
    ``choice_value``). Returns False on stale / unknown / already-resolved.
    Safe to call from any thread; the future is woken via the loop's
    threadsafe channel.
    """
    with _dict_lock:
        fut = _pending.pop(approval_id, None)
    if fut is None or fut.done():
        return False
    try:
        fut.get_loop().call_soon_threadsafe(fut.set_result, choice_value)
    except Exception:
        logger.exception("[elicit] failed to set future result for %s", approval_id)
        return False
    return True


def has_pending_elicitation(approval_id: str) -> bool:
    with _dict_lock:
        return approval_id in _pending


def cancel_pending(reason: str = "cancelled") -> int:
    """Resolve every pending elicitation as the given reason. Useful on
    gateway shutdown so blocked MCP elicitations don't hang. Returns the
    number cancelled."""
    with _dict_lock:
        outstanding = list(_pending.items())
        _pending.clear()
    for _id, fut in outstanding:
        if not fut.done():
            try:
                fut.get_loop().call_soon_threadsafe(fut.set_result, reason)
            except Exception:
                pass
    return len(outstanding)


# ── Public API used by the elicitation callback ───────────────────────────

async def _dispatch_send(coro: "Awaitable[Any]") -> Any:
    """Run ``coro`` on the platform adapter's event loop.

    The send callback is bound to the platform's loop (Telegram bot uses
    its own loop's primitives internally). The MCP elicitation handler
    runs on a different loop, so we cross the boundary with
    ``run_coroutine_threadsafe`` + ``wrap_future`` — the awaiting coroutine
    suspends correctly until the platform side completes.

    Falls back to direct await when no loop was registered, which only
    happens in tests or single-loop deployments.
    """
    if _send_loop is None:
        return await coro
    try:
        running = asyncio.get_running_loop()
    except RuntimeError:
        running = None
    if running is _send_loop:
        return await coro
    cf = asyncio.run_coroutine_threadsafe(coro, _send_loop)
    return await asyncio.wrap_future(cf)


async def request_elicitation(
    *,
    chat_id: str,
    title: str,
    body: str,
    choices: List[Dict[str, str]],
    timeout_s: float = 60.0,
) -> Optional[str]:
    """Surface a button prompt to the user and await their tap.

    Returns the chosen value, or ``None`` on timeout / send failure / no
    callback registered. The caller (an elicitation_callback) should map
    ``None`` to ``ElicitResult(action="cancel")`` so the MCP server sees a
    definitive non-accept outcome.
    """
    if _send_callback is None:
        logger.error("[elicit] no send callback registered; cannot prompt user")
        return None
    if not choices:
        logger.error("[elicit] empty choices list")
        return None

    approval_id = uuid.uuid4().hex[:16]
    fut: asyncio.Future = asyncio.get_running_loop().create_future()
    with _dict_lock:
        _pending[approval_id] = fut

    try:
        coro = _send_callback(
            chat_id=chat_id,
            title=title,
            body=body,
            approval_id=approval_id,
            choices=choices,
        )
        send_result = await _dispatch_send(coro)
    except Exception:
        logger.exception("[elicit] send callback raised")
        with _dict_lock:
            _pending.pop(approval_id, None)
        return None

    if not getattr(send_result, "success", False):
        err = getattr(send_result, "error", "?")
        logger.warning("[elicit] send_result reported failure: %s", err)
        with _dict_lock:
            _pending.pop(approval_id, None)
        return None

    try:
        return await asyncio.wait_for(fut, timeout=timeout_s)
    except asyncio.TimeoutError:
        with _dict_lock:
            _pending.pop(approval_id, None)
        logger.info("[elicit] %s timed out after %.1fs", approval_id, timeout_s)
        return None


# ── Schema introspection ──────────────────────────────────────────────────

def extract_enum_choices(schema: Any) -> List[Dict[str, str]]:
    """Find the first property in the schema that has a string-enum and
    return it as a list of ``{label, value}`` dicts.

    Supports both untitled enums (``"enum": [...]``) and titled enums
    (``"oneOf": [{"const": ..., "title": ...}, ...]``) — the latter is
    what rmcp's ``EnumSchemaBuilder::enum_titles`` emits.

    Returns an empty list when no enum property is found, in which case
    the caller should decline the elicitation (we don't render free-form
    inputs as buttons).
    """
    if not isinstance(schema, dict):
        return []
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return []
    for prop in properties.values():
        if not isinstance(prop, dict):
            continue
        # Untitled enum: {"type": "string", "enum": ["a", "b", ...]}
        if "enum" in prop and isinstance(prop["enum"], list):
            return [
                {"label": str(v), "value": str(v)}
                for v in prop["enum"]
                if isinstance(v, (str, int, float, bool))
            ]
        # Titled enum: {"type": "string", "oneOf": [{"const": "a", "title": "Apple"}, ...]}
        if "oneOf" in prop and isinstance(prop["oneOf"], list):
            choices: List[Dict[str, str]] = []
            for opt in prop["oneOf"]:
                if isinstance(opt, dict) and "const" in opt:
                    label = opt.get("title") or opt["const"]
                    choices.append({"label": str(label), "value": str(opt["const"])})
            if choices:
                return choices
    return []


# ── Chat-ID resolver ──────────────────────────────────────────────────────

def resolve_chat_id(session_key: Optional[str] = None) -> Optional[str]:
    """Pick a chat_id for the approval message.

    Single-user mode: ``TELEGRAM_HOME_CHANNEL`` is the source of truth.
    Multi-user routing can be added by parsing session_key (Hermes
    formats it as e.g. ``telegram:-1001234567890``).
    """
    if session_key and ":" in session_key:
        _, _, candidate = session_key.partition(":")
        if candidate.strip():
            return candidate.strip()
    return os.environ.get("TELEGRAM_HOME_CHANNEL") or None
