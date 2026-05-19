"""Wire-protocol shared between the gateway's action-stall guard and the
codex/xAI transport.

When ``gateway.run`` detects an assistant turn that promises action but
emits no tool call, it enqueues a corrective continuation as the next
user message, prefixed with :data:`ACTION_STALL_EVENT_PREFIX`.  The
codex transport recognises that prefix on the inbound message list and
forces ``tool_choice=required`` so the retry cannot narrate its way
through again.

The constant lives here (not in ``gateway.run`` or in the transport) so
the producer and the consumer share a single source of truth.
"""

from __future__ import annotations

from typing import Any

ACTION_STALL_EVENT_PREFIX = "[System corrective continuation: tool execution required]"


def latest_user_message_is_stall_continuation(messages: Any) -> bool:
    """Return ``True`` iff the most recent user message starts with the
    stall-continuation prefix AND the prior assistant turn (if any) emitted
    no tool_calls — meaning this turn really is a stall-recovery situation
    where forcing a tool call is safe.

    ``content`` may be a plain string or a list of OpenAI-style content
    parts ``{"type": "...", "text": "..."}``; both shapes are inspected.
    Trailing non-user entries (assistant, tool) are skipped while finding
    the latest user message.

    The prior-tool-calls check defends future callers from accidentally
    forcing ``tool_choice=required`` on a turn that follows real tool
    activity — which would either loop or invalidate the just-completed
    work.
    """
    if not messages:
        return False
    messages_list = list(messages)
    latest_user_idx = None
    for i in range(len(messages_list) - 1, -1, -1):
        msg = messages_list[i]
        if isinstance(msg, dict) and msg.get("role") == "user":
            latest_user_idx = i
            break
    if latest_user_idx is None:
        return False
    if not _content_starts_with_prefix(messages_list[latest_user_idx].get("content")):
        return False
    # Walk back from the user message to the most recent assistant entry;
    # if it emitted tool_calls, the prior turn already did real work and
    # this should not be a stall force.
    for i in range(latest_user_idx - 1, -1, -1):
        msg = messages_list[i]
        if not isinstance(msg, dict):
            continue
        if msg.get("role") == "assistant":
            return not msg.get("tool_calls")
    return True


def _content_starts_with_prefix(content: Any) -> bool:
    if isinstance(content, str):
        return content.lstrip().startswith(ACTION_STALL_EVENT_PREFIX)
    if isinstance(content, list):
        for part in content:
            if isinstance(part, dict):
                text = part.get("text")
                if isinstance(text, str) and text.lstrip().startswith(ACTION_STALL_EVENT_PREFIX):
                    return True
    return False
