"""Discord-only tool for reading recent channel/thread history."""

from __future__ import annotations

from tools.registry import registry, tool_error, tool_result


DISCORD_CHANNEL_HISTORY_SCHEMA = {
    "name": "discord_channel_history",
    "description": (
        "Read recent messages from the current Discord channel or thread. "
        "Omit channel_id/thread_id to use the current conversation context. "
        "Returns the most recent messages including other bots, with author/content/timestamp/message_id."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "How many recent messages to fetch. Default 20, max 50.",
            },
            "channel_id": {
                "type": "string",
                "description": "Optional Discord parent channel ID. Omit to use the current channel.",
            },
            "thread_id": {
                "type": "string",
                "description": "Optional Discord thread ID. If provided, reads that thread instead of the parent channel.",
            },
            "before_message_id": {
                "type": "string",
                "description": "Optional message ID anchor. When provided, fetches messages before that message.",
            },
        },
        "required": [],
    },
}


def _run_async_tool(coro):
    from model_tools import _run_async

    return _run_async(coro)


def _check_discord_channel_history():
    """Expose the tool inside Discord sessions, or from CLI when Discord gateway is running."""
    from gateway.session_context import get_session_env

    platform = get_session_env("HERMES_SESSION_PLATFORM", "").strip().lower()
    if platform:
        return platform == "discord"

    try:
        from gateway.status import is_gateway_running
        if not is_gateway_running():
            return False

        from gateway.config import load_gateway_config, Platform

        config = load_gateway_config()
        pconfig = config.platforms.get(Platform.DISCORD)
        return bool(pconfig and pconfig.enabled and pconfig.token)
    except Exception:
        return False


def _resolve_limit(raw_value) -> int:
    if raw_value in (None, ""):
        return 20
    try:
        limit = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError("limit must be an integer") from exc
    return max(1, min(limit, 50))


def _resolve_target_ids(args: dict) -> tuple[str, str]:
    from gateway.session_context import get_session_env

    explicit_thread_id = str(args.get("thread_id") or "").strip()
    explicit_channel_id = str(args.get("channel_id") or "").strip()

    if explicit_thread_id:
        return explicit_thread_id, "explicit_thread"
    if explicit_channel_id:
        return explicit_channel_id, "explicit_channel"

    platform = get_session_env("HERMES_SESSION_PLATFORM", "").strip().lower()
    if platform and platform != "discord":
        raise ValueError("discord_channel_history is only available in Discord sessions")

    current_thread_id = get_session_env("HERMES_SESSION_THREAD_ID", "").strip()
    if current_thread_id:
        return current_thread_id, "current_thread"

    current_chat_id = get_session_env("HERMES_SESSION_CHAT_ID", "").strip()
    if current_chat_id:
        return current_chat_id, "current_channel"

    raise ValueError(
        "No Discord channel context found. Provide channel_id/thread_id explicitly or call this tool from a Discord conversation."
    )


async def _read_discord_channel_history(args: dict) -> dict:
    from gateway.config import load_gateway_config, Platform
    from gateway.platforms.discord import fetch_channel_history_via_api

    limit = _resolve_limit(args.get("limit"))
    channel_id, source = _resolve_target_ids(args)
    before_message_id = args.get("before_message_id")

    config = load_gateway_config()
    pconfig = config.platforms.get(Platform.DISCORD)
    if not pconfig or not pconfig.enabled or not pconfig.token:
        raise RuntimeError("Discord is not configured in the Hermes gateway")

    messages = await fetch_channel_history_via_api(
        pconfig.token,
        channel_id,
        limit=limit,
        before_message_id=before_message_id,
    )

    return {
        "success": True,
        "platform": "discord",
        "channel_id": channel_id,
        "source": source,
        "limit": limit,
        "count": len(messages),
        "order": "oldest_to_newest",
        "messages": messages,
    }


def discord_channel_history_tool(args, **_kw):
    try:
        payload = _run_async_tool(_read_discord_channel_history(args or {}))
        return tool_result(payload)
    except Exception as exc:
        return tool_error(str(exc))


registry.register(
    name="discord_channel_history",
    toolset="messaging",
    schema=DISCORD_CHANNEL_HISTORY_SCHEMA,
    handler=discord_channel_history_tool,
    check_fn=_check_discord_channel_history,
    emoji="🧵",
    max_result_size_chars=50_000,
)
