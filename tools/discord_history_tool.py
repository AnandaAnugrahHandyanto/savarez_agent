"""Discord channel history reader.

Exposes a `read_channel_history` tool that fetches recent messages from a
Discord channel (or thread) via the REST API.  Complements `send_message`:
lets the model see what was said in a channel before a live on_message
event fired — essential for threaded agent-to-agent conversation where
another bot may have posted while Hermes was offline.
"""

from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)


READ_HISTORY_SCHEMA = {
    "name": "read_channel_history",
    "description": (
        "Read recent messages from a Discord channel or thread.\n\n"
        "Useful to catch up on context before replying, or to check what "
        "another bot/user posted in a channel Hermes is not actively watching. "
        "Returns newest-first. Use `before` to paginate further back."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": (
                    "Discord channel. Numeric ID ('1494048456719859894'), "
                    "'#channel-name', or 'GuildName/channel-name'. Thread IDs "
                    "work directly (threads are channels in Discord)."
                ),
            },
            "limit": {
                "type": "integer",
                "description": "Max messages to return (1-100). Default 50.",
            },
            "before": {
                "type": "string",
                "description": "Message ID cursor — return messages older than this ID.",
            },
        },
        "required": ["target"],
    },
}


def _error(message: str) -> dict:
    return {"success": False, "error": message}


async def _fetch_history(token: str, chat_id: str, limit: int, before: str | None):
    try:
        import aiohttp
    except ImportError:
        return _error("aiohttp not installed. Run: pip install aiohttp")

    try:
        from gateway.platforms.base import resolve_proxy_url, proxy_kwargs_for_aiohttp
        _proxy = resolve_proxy_url(platform_env_var="DISCORD_PROXY")
        _sess_kw, _req_kw = proxy_kwargs_for_aiohttp(_proxy)
    except Exception:
        _sess_kw, _req_kw = {}, {}

    headers = {"Authorization": f"Bot {token}"}
    url = f"https://discord.com/api/v10/channels/{chat_id}/messages"
    params = {"limit": str(max(1, min(limit, 100)))}
    if before:
        params["before"] = str(before)

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30), **_sess_kw) as session:
            async with session.get(url, headers=headers, params=params, **_req_kw) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    return _error(f"Discord history fetch failed ({resp.status}): {body[:500]}")
                raw = await resp.json()
    except Exception as e:
        return _error(f"Discord history request failed: {e}")

    messages = []
    for m in raw:
        author = m.get("author") or {}
        messages.append({
            "id": m.get("id"),
            "timestamp": m.get("timestamp"),
            "author_id": author.get("id"),
            "author": author.get("username") or author.get("global_name") or "?",
            "is_bot": bool(author.get("bot")),
            "content": m.get("content", ""),
            "reply_to": (m.get("referenced_message") or {}).get("id"),
            "attachments": [a.get("url") for a in m.get("attachments", []) if a.get("url")],
        })
    return {"success": True, "chat_id": chat_id, "count": len(messages), "messages": messages}


def read_channel_history_tool(args, **kw):
    """Handle read_channel_history tool calls."""
    target = (args.get("target") or "").strip()
    if not target:
        from tools.registry import tool_error
        return tool_error("'target' is required")

    limit = args.get("limit")
    try:
        limit = int(limit) if limit is not None else 50
    except (TypeError, ValueError):
        limit = 50
    before = args.get("before") or None

    # Accept 'discord:' prefix for symmetry with send_message, but this tool
    # is Discord-only so the prefix is optional.
    raw = target
    if ":" in raw:
        plat, _, rest = raw.partition(":")
        if plat.strip().lower() == "discord":
            raw = rest.strip()

    chat_id = None
    if raw.lstrip("-").isdigit():
        chat_id = raw
    else:
        try:
            from gateway.channel_directory import resolve_channel_name
            chat_id = resolve_channel_name("discord", raw)
        except Exception:
            chat_id = None
        if not chat_id:
            return json.dumps(_error(
                f"Could not resolve Discord channel '{target}'. "
                "Use send_message(action='list') to see available targets, "
                "or pass a numeric channel ID."
            ))

    try:
        from gateway.config import load_gateway_config, Platform
        config = load_gateway_config()
    except Exception as e:
        return json.dumps(_error(f"Failed to load gateway config: {e}"))

    pconfig = config.platforms.get(Platform.DISCORD)
    if not pconfig or not pconfig.enabled or not pconfig.token:
        return json.dumps(_error("Discord platform is not configured or has no token."))

    from tools.interrupt import is_interrupted
    if is_interrupted():
        from tools.registry import tool_error
        return tool_error("Interrupted")

    try:
        from model_tools import _run_async
        result = _run_async(_fetch_history(pconfig.token, chat_id, limit, before))
        return json.dumps(result)
    except Exception as e:
        return json.dumps(_error(f"read_channel_history failed: {e}"))


def _check_read_history():
    """Available on messaging platforms or whenever the gateway is running."""
    try:
        from gateway.session_context import get_session_env
        platform = get_session_env("HERMES_SESSION_PLATFORM", "")
        if platform and platform != "local":
            return True
        from gateway.status import is_gateway_running
        return is_gateway_running()
    except Exception:
        return False


# --- Registry ---
from tools.registry import registry

registry.register(
    name="read_channel_history",
    toolset="messaging",
    schema=READ_HISTORY_SCHEMA,
    handler=read_channel_history_tool,
    check_fn=_check_read_history,
    emoji="📜",
)
