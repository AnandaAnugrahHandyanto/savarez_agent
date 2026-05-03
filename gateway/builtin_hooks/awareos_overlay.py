from __future__ import annotations

import hashlib
import time
from typing import Any

from gateway.awareos_bridge import (
    awareos_overlay_enabled,
    record_work_overlay_start,
    record_work_overlay_stop,
)


_ACTIVE: dict[str, dict[str, Any]] = {}


def _stable_overlay_id(ctx: dict[str, Any]) -> str:
    # session_id is already a stable UUID-like identifier.
    session_id = str(ctx.get("session_id") or "").strip()
    platform = str(ctx.get("platform") or "").strip()
    chat_id = str(ctx.get("chat_id") or "").strip()
    if session_id:
        return f"hermes:{platform}:{chat_id}:{session_id}"
    # Fallback: hash session_key + message_id for stability without raw text.
    base = (
        f"{platform}:{chat_id}:"
        f"{str(ctx.get('session_key') or '')}:{str(ctx.get('message_id') or '')}"
    )
    return "hermes:" + hashlib.sha256(base.encode("utf-8")).hexdigest()[:24]


def _is_substantive(ctx: dict[str, Any]) -> bool:
    # Prefer explicit marker (set by gateway/run.py) when available.
    if "substantive" in ctx:
        return bool(ctx.get("substantive"))
    api_calls = int(ctx.get("api_calls") or 0)
    tool_names = ctx.get("tool_names") or []
    return api_calls > 1 or (isinstance(tool_names, list) and len(tool_names) > 0)


async def _handle_agent_start(_event_type: str, ctx: dict[str, Any]) -> None:
    if not awareos_overlay_enabled():
        return
    if (ctx.get("platform") or "") != "telegram":
        return
    if not _is_substantive(ctx):
        # Defer start until we see substantive info (agent:end can still emit stop
        # without start, but we skip for truly trivial turns).
        return
    overlay_id = _stable_overlay_id(ctx)
    source = {
        "platform": ctx.get("platform") or "",
        "chat_id": ctx.get("chat_id") or "",
        "message_id": ctx.get("message_id") or "",
        "session_id": ctx.get("session_id") or "",
        "session_key": ctx.get("session_key") or "",
        "user_id": ctx.get("user_id") or "",
    }
    record_work_overlay_start(
        overlay_id=overlay_id,
        source=source,
        prompt_text=None,
        journal={
            "turn_kind": "hermes_agent",
            "started_at_ms": int(time.time() * 1000),
        },
    )
    _ACTIVE[overlay_id] = {"started_at": time.time(), "source": source}


async def _handle_agent_end(_event_type: str, ctx: dict[str, Any]) -> None:
    if not awareos_overlay_enabled():
        return
    if (ctx.get("platform") or "") != "telegram":
        return
    if not _is_substantive(ctx):
        return
    overlay_id = _stable_overlay_id(ctx)
    active = _ACTIVE.pop(overlay_id, None) or {}
    source = dict(active.get("source") or {})
    if not source:
        source = {
            "platform": ctx.get("platform") or "",
            "chat_id": ctx.get("chat_id") or "",
            "message_id": ctx.get("message_id") or "",
            "session_id": ctx.get("session_id") or "",
            "session_key": ctx.get("session_key") or "",
            "user_id": ctx.get("user_id") or "",
        }
    tool_names = ctx.get("tool_names") if isinstance(ctx.get("tool_names"), list) else []
    record_work_overlay_stop(
        overlay_id=overlay_id,
        source=source,
        result={
            "api_calls": int(ctx.get("api_calls") or 0),
            "response_length": int(ctx.get("response_length") or 0),
            "tool_count": len(tool_names),
        },
        journal={
            "turn_kind": "hermes_agent",
            "ended_at_ms": int(time.time() * 1000),
            "duration_ms": int(((time.time() - float(active.get("started_at") or time.time())) * 1000)),
            "tool_names": tool_names,
            "model": ctx.get("model") or "",
        },
    )


def register_builtin_hooks(registry: Any) -> None:
    """Called by HookRegistry during discover_and_load()."""
    try:
        registry._handlers.setdefault("agent:start", []).append(_handle_agent_start)
        registry._handlers.setdefault("agent:end", []).append(_handle_agent_end)
    except Exception:
        return

