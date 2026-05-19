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
    stall-continuation prefix.

    ``content`` may be a plain string or a list of OpenAI-style content
    parts ``{"type": "...", "text": "..."}``; both shapes are inspected.
    Trailing non-user entries (assistant, tool) are skipped — the relevant
    "latest user message" drives the current turn even when later entries
    were appended.
    """
    if not messages:
        return False
    for msg in reversed(list(messages)):
        if not isinstance(msg, dict) or msg.get("role") != "user":
            continue
        content = msg.get("content")
        if isinstance(content, str):
            return content.lstrip().startswith(ACTION_STALL_EVENT_PREFIX)
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    text = part.get("text")
                    if isinstance(text, str) and text.lstrip().startswith(ACTION_STALL_EVENT_PREFIX):
                        return True
        return False
    return False
