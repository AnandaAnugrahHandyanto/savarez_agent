"""Gateway-backed visible session control tool."""

from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import Callable

from gateway.config import Platform
from gateway.platforms.base import MessageEvent
from gateway.run import _gateway_runner_ref
from gateway.session_context import get_trusted_session_context
from gateway.session import SessionSource
from tools.registry import registry, tool_error


VISIBLE_SESSION_SCHEMA = {
    "name": "visible_session",
    "description": "Manage gateway-backed visible child sessions (Telegram topics/threads).",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["create", "prompt", "list", "status", "close"]},
            "platform": {"type": "string"},
            "parent_chat_id": {"type": "string"},
            "parent_thread_id": {"type": "string"},
            "topic_name": {"type": "string"},
            "prompt": {"type": "string"},
            "handle": {"type": "string"},
            "mode": {"type": "string", "enum": ["queue", "interrupt", "steer", "send_only"]},
            "provider": {"type": "string"},
            "model": {"type": "string"},
            "reasoning_effort": {"type": "string"},
            "profile": {"type": "string"},
            "workdir": {"type": "string"},
        },
        "required": ["action"],
    },
}


LIVE_GATEWAY_ERROR = (
    "Visible sessions require a live gateway context; use /spawn-topic from Telegram or run through the gateway."
)


_VISIBLE_SESSION_LOOP_TIMEOUT_S = 30


def _run_on_gateway_loop(runner, coro_factory: Callable[[], object]):
    loop = getattr(runner, "_gateway_loop", None)
    if loop is None or loop.is_closed() or not loop.is_running():
        raise RuntimeError("visible_session requires live gateway event loop")

    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    if current_loop is loop:
        raise RuntimeError("visible_session cannot be invoked from gateway event loop thread")

    coro = coro_factory()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result(timeout=_VISIBLE_SESSION_LOOP_TIMEOUT_S)


def _chat_type_from_session_key(session_key: str, platform: Platform) -> str:
    parts = str(session_key or "").split(":")
    if len(parts) >= 4 and parts[0] == "agent" and parts[2] == platform.value and parts[3]:
        return parts[3]
    return "group"


def _parent_event(args: dict) -> MessageEvent:
    trusted = get_trusted_session_context()
    if trusted is None:
        raise ValueError("visible_session requires gateway session context")

    platform = Platform(str(trusted["platform"]).strip().lower())
    chat_id = str(trusted["chat_id"]).strip()
    thread_id = str(trusted.get("thread_id") or "").strip() or None
    user_id = str(trusted.get("user_id") or "").strip() or None
    user_name = str(trusted.get("user_name") or "").strip() or None
    session_key = str(trusted.get("session_key") or "").strip()
    chat_type = _chat_type_from_session_key(session_key, platform)

    source = SessionSource(
        platform=platform,
        chat_id=chat_id,
        chat_type=chat_type,
        thread_id=thread_id,
        user_id=user_id,
        user_name=user_name,
    )
    return MessageEvent(text="visible_session_tool", source=source, message_id="visible-session-tool")


def _serialize_handle(handle) -> dict:
    return {
        "platform": handle.platform,
        "chat_id": handle.chat_id,
        "thread_id": handle.thread_id,
        "topic_name": handle.topic_name,
        "session_key": handle.session_key,
        "session_id": handle.session_id,
        "target": handle.target,
    }


def visible_session_tool(args, **_kw):
    action = str(args.get("action") or "").strip().lower()
    runner = _gateway_runner_ref()
    if runner is None:
        return json.dumps({"error": LIVE_GATEWAY_ERROR})

    try:
        if action == "create":
            event = _parent_event(args)
            handle = _run_on_gateway_loop(
                runner,
                lambda: runner.create_visible_session(
                    parent_event=event,
                    platform=str(args.get("platform") or "telegram"),
                    parent_chat_id=str(args.get("parent_chat_id") or ""),
                    topic_name=str(args.get("topic_name") or ""),
                    prompt=str(args.get("prompt") or ""),
                    provider=args.get("provider"),
                    model=args.get("model"),
                    reasoning_effort=args.get("reasoning_effort"),
                    profile=args.get("profile"),
                    workdir=args.get("workdir"),
                ),
            )
            return json.dumps({"ok": True, "action": "create", "handle": _serialize_handle(handle)})

        if action == "prompt":
            event = _parent_event(args)
            handle = _run_on_gateway_loop(
                runner,
                lambda: runner.prompt_visible_session(
                    parent_event=event,
                    handle=str(args.get("handle") or ""),
                    prompt=str(args.get("prompt") or ""),
                    mode=str(args.get("mode") or "queue"),
                ),
            )
            return json.dumps({"ok": True, "action": "prompt", "handle": _serialize_handle(handle)})

        if action == "list":
            event = _parent_event(args)
            handles_or_awaitable = runner.list_visible_sessions(parent_event=event)
            if inspect.isawaitable(handles_or_awaitable):
                handles = _run_on_gateway_loop(runner, lambda: handles_or_awaitable)
            else:
                handles = handles_or_awaitable
            return json.dumps({"ok": True, "action": "list", "handles": [_serialize_handle(h) for h in handles]})

        if action == "status":
            event = _parent_event(args)
            handle = runner.status_visible_session(parent_event=event, handle=str(args.get("handle") or ""))
            return json.dumps({"ok": True, "action": "status", "handle": _serialize_handle(handle)})

        if action == "close":
            event = _parent_event(args)
            handle = _run_on_gateway_loop(
                runner,
                lambda: runner.close_visible_session(parent_event=event, handle=str(args.get("handle") or "")),
            )
            return json.dumps({"ok": True, "action": "close", "handle": _serialize_handle(handle)})

        return tool_error("action must be one of: create, prompt, list, status, close")
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def _check_visible_session_tool() -> bool:
    return True


registry.register(
    name="visible_session",
    toolset="messaging",
    schema=VISIBLE_SESSION_SCHEMA,
    handler=visible_session_tool,
    check_fn=_check_visible_session_tool,
    emoji="🧵",
)
