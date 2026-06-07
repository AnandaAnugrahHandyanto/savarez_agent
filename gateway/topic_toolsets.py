"""Source-aware gateway toolset resolution.

Messaging gateways usually have a broad platform-level fallback such as
``platform_toolsets.telegram``. Forum topics/channels can optionally narrow
that via ``<platform>.channel_toolsets`` without changing the global fallback.
"""

from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
from typing import Any


def _as_toolset_list(value: Any) -> list[str] | None:
    """Normalize a channel-toolset config value.

    ``None`` means absent/invalid. An empty list is a valid explicit value;
    it is passed through to the platform resolver unchanged.
    """
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray, dict)):
        return [str(part).strip() for part in value if str(part).strip()]
    return None


def _channel_toolset_candidates(platform_key: str, source: Any) -> list[str]:
    """Return route keys from most-specific to least-specific."""
    chat_id = getattr(source, "chat_id", None)
    parent_chat_id = getattr(source, "parent_chat_id", None)
    thread_id = getattr(source, "thread_id", None)
    chat_type = getattr(source, "chat_type", None)

    candidates: list[str] = []

    def add(value: Any) -> None:
        if value is None:
            return
        key = str(value).strip()
        if key and key not in candidates:
            candidates.append(key)

    if chat_id is not None and thread_id is not None:
        add(f"{chat_id}:{thread_id}")
    if parent_chat_id is not None and thread_id is not None:
        add(f"{parent_chat_id}:{thread_id}")
    if thread_id is not None:
        add(thread_id)

    # Telegram may omit message_thread_id for forum General. The Telegram
    # adapter normalizes this for normal messages, but keep the resolver robust
    # for synthetic/resumed sends and tests.
    if platform_key == "telegram" and thread_id is None and chat_type == "group":
        add("1")

    add(chat_id)
    add(parent_chat_id)
    add("default")
    return candidates


def resolve_channel_toolset_names(
    config: dict[str, Any] | None,
    platform_key: str,
    source: Any,
) -> list[str] | None:
    """Resolve raw toolset names for a source-specific channel/topic.

    Config format::

        telegram:
          channel_toolsets:
            default: [web, skills, no_mcp]
            "255": [web, terminal, file, no_mcp]
            "-100123:260": [web, lighthouse]

    Precedence:
      1. exact ``chat_id:thread_id``;
      2. exact ``parent_chat_id:thread_id``;
      3. ``thread_id``;
      4. Telegram forum General fallback ``1`` when thread id is absent;
      5. ``chat_id``;
      6. ``parent_chat_id``;
      7. ``default``.
    """
    cfg = config or {}
    platform_cfg = cfg.get(platform_key) or {}
    if not isinstance(platform_cfg, dict):
        return None
    channel_toolsets = platform_cfg.get("channel_toolsets") or {}
    if not isinstance(channel_toolsets, dict):
        return None

    for key in _channel_toolset_candidates(platform_key, source):
        if key not in channel_toolsets:
            continue
        names = _as_toolset_list(channel_toolsets.get(key))
        if names is not None:
            return names
    return None


def resolve_gateway_toolsets(
    config: dict[str, Any] | None,
    platform_key: str,
    source: Any,
) -> set[str]:
    """Resolve effective toolsets for a gateway turn.

    Falls back to ``platform_toolsets.<platform>`` exactly as before when no
    source-specific ``<platform>.channel_toolsets`` entry matches.
    """
    from hermes_cli.tools_config import _get_platform_tools

    cfg = config or {}
    channel_toolsets = resolve_channel_toolset_names(cfg, platform_key, source)
    if channel_toolsets is None:
        return _get_platform_tools(cfg, platform_key)

    overlay = deepcopy(cfg)
    platform_toolsets = overlay.get("platform_toolsets")
    if not isinstance(platform_toolsets, dict):
        platform_toolsets = {}
    else:
        platform_toolsets = dict(platform_toolsets)
    platform_toolsets[platform_key] = channel_toolsets
    overlay["platform_toolsets"] = platform_toolsets
    return _get_platform_tools(overlay, platform_key)
