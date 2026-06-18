"""Anthropic prompt caching strategy.

Single layout: ``system_and_3``. 4 cache_control breakpoints — system
prompt + last 3 non-system messages, all at the same TTL (5m or 1h).
Reduces input token costs by ~75% on multi-turn conversations within a
single session.

Pure functions -- no class state, no AIAgent dependency.
"""

from typing import Any, Dict, List


def _apply_cache_marker(msg: dict, cache_marker: dict, native_anthropic: bool = False) -> None:
    """Add cache_control to a single message, handling all format variations."""
    role = msg.get("role", "")
    content = msg.get("content")

    if role == "tool":
        if native_anthropic:
            msg["cache_control"] = cache_marker
        return

    if content is None or content == "":
        msg["cache_control"] = cache_marker
        return

    if isinstance(content, str):
        msg["content"] = [
            {"type": "text", "text": content, "cache_control": cache_marker}
        ]
        return

    if isinstance(content, list) and content:
        last = content[-1]
        if isinstance(last, dict):
            last["cache_control"] = cache_marker


def _build_marker(ttl: str) -> Dict[str, str]:
    """Build a cache_control marker dict for the given TTL ('5m' or '1h')."""
    marker: Dict[str, str] = {"type": "ephemeral"}
    if ttl == "1h":
        marker["ttl"] = "1h"
    return marker


def apply_anthropic_cache_control(
    api_messages: List[Dict[str, Any]],
    cache_ttl: str = "5m",
    native_anthropic: bool = False,
) -> List[Dict[str, Any]]:
    """Apply system_and_3 caching strategy to messages for Anthropic models.

    Places up to 4 cache_control breakpoints: system prompt + last 3 non-system
    messages, all at the same TTL.

    Mutates shallow copies of only the messages that receive breakpoints.
    ``api_messages`` must already be an API-only copy (as built by
    ``conversation_loop``) — callers must not pass the persisted session list.
    """
    if not api_messages:
        return api_messages

    marker = _build_marker(cache_ttl)

    indices_to_mark: List[int] = []
    breakpoints_used = 0

    if api_messages[0].get("role") == "system":
        indices_to_mark.append(0)
        breakpoints_used += 1

    remaining = 4 - breakpoints_used
    non_sys = [i for i in range(len(api_messages)) if api_messages[i].get("role") != "system"]
    indices_to_mark.extend(non_sys[-remaining:])

    if not indices_to_mark:
        return api_messages

    messages = list(api_messages)
    for idx in indices_to_mark:
        if messages[idx] is api_messages[idx]:
            messages[idx] = api_messages[idx].copy()
        _apply_cache_marker(messages[idx], marker, native_anthropic=native_anthropic)

    return messages
