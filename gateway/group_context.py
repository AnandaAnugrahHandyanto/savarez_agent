"""
Group-aware context inference for Hermes gateway.

When a Hermes session resets in a group/channel, this module:
1. Loads the previous session's message history for that channel
2. Formats it with extracted sender names and readable structure
3. Injects it into the new session's context_prompt

This module is called from gateway/run.py when:
- was_auto_reset=True (idle or daily reset, NOT manual /new)
- source.chat_type in ("group", "channel")
- session_reset.group_context_on_reset > 0 in config

The messages schema from load_transcript() / get_messages_as_conversation():
    role: "user" | "assistant" | "system" | "tool" | "session_meta"
    content: str | list[dict]  (text, or multi-part with type/text dicts)
    tool_call_id: optional
    tool_calls: optional
    tool_name: optional
    observed: bool (Telegram observed-but-not-addressed messages)

Sender names are embedded in user-message content as "[Name] message text"
when shared_multi_user_session=True (group_sessions_per_user=False).

Response Targeting
------------------
This module also implements ``should_respond()``, a platform-agnostic filter
that decides whether Hermes should reply in a group/channel context.

Four rules are evaluated in order:

1. **Explicit mention** — If Hermes is directly addressed (by name, @mention,
   or the message is a direct reply to a Hermes message), always respond.
2. **Active thread continuation** — If the current session already contains
   Hermes turns (Hermes is actively participating), respond to keep the
   thread coherent.
3. **Side conversation** — If the message is a conversation between other
   users with no question or address to Hermes, stay silent.
4. **Proactive mode** — If ``proactive=True``, Hermes will also respond to
   messages that appear to be unresolved open questions directed at the
   group (questions containing "?", "who", "what", "how", "when", "why",
   "can anyone", "does anyone", etc.) even without an explicit mention.
   This mode is off by default.

Configurable via ``ChannelContext.proactive`` or the ``proactive_in_groups``
gateway config key (not yet wired — consumers pass the flag explicitly).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# ------------------------------------------------------------------ #
# Sender extraction                                                    #
# ------------------------------------------------------------------ #

_SENDER_PREFIX_RE = re.compile(r"^\[([^\]]{1,64})\]\s+(.+)$", re.DOTALL)


def _extract_sender(content: str) -> Tuple[Optional[str], str]:
    """Return (sender_name, body) from a [SenderName] prefixed message.

    If there is no prefix, returns (None, content).
    """
    m = _SENDER_PREFIX_RE.match(content.strip())
    if m:
        return m.group(1), m.group(2).strip()
    return None, content.strip()


def _text_from_content(content: Any) -> str:
    """Extract plain text from a message content field.

    Handles both str and list-of-parts (OpenAI multi-modal format).
    Returns empty string if no text found.
    """
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                t = part.get("text", "")
                if t:
                    parts.append(str(t).strip())
        return " ".join(parts).strip()
    return ""


# ------------------------------------------------------------------ #
# History formatting                                                   #
# ------------------------------------------------------------------ #

_CONTEXT_HEADER = (
    "[Prior group conversation — loaded after session reset. "
    "Review to understand ongoing discussion and avoid repeating information already given.]"
)
_CONTEXT_FOOTER = "[End of prior conversation history]"


def format_group_history(
    messages: List[Dict[str, Any]],
    max_messages: int = 20,
    max_assistant_chars: int = 500,
) -> str:
    """Format transcript messages as a readable group history block.

    Args:
        messages: Messages from load_transcript() / get_messages_as_conversation()
        max_messages: Maximum user/assistant turns to include (most recent)
        max_assistant_chars: Truncate assistant replies beyond this length

    Returns:
        Formatted string, or empty string if nothing to show.
    """
    # Filter: text-bearing user/assistant turns only; skip tool plumbing
    usable = [
        m for m in messages
        if m.get("role") in {"user", "assistant"}
        and not m.get("tool_calls")
        and not m.get("tool_call_id")
        and not m.get("observed")
    ]

    if not usable:
        return ""

    # Most recent N turns
    tail = usable[-max_messages:]

    lines = [_CONTEXT_HEADER, ""]

    for msg in tail:
        role = msg.get("role", "")
        raw_content = msg.get("content")
        if not raw_content:
            continue

        text = _text_from_content(raw_content)
        if not text:
            continue

        if role == "user":
            sender, body = _extract_sender(text)
            label = sender if sender else "User"
            lines.append(f"{label}: {body}")

        elif role == "assistant":
            body = text
            if len(body) > max_assistant_chars:
                body = body[:max_assistant_chars].rstrip() + "… [truncated]"
            lines.append(f"Hermes: {body}")

    if len(lines) <= 2:
        # Nothing was added beyond the header
        return ""

    lines.extend(["", _CONTEXT_FOOTER])
    return "\n".join(lines)


# ------------------------------------------------------------------ #
# Topic inference                                                      #
# ------------------------------------------------------------------ #

def infer_current_topic(messages: List[Dict[str, Any]], window: int = 6) -> Optional[str]:
    """Infer what the group is currently discussing from recent messages.

    Returns a short description of the latest topic, or None.
    Used to build a one-line orientation note in the system context.
    """
    recent_user = [
        m for m in messages[-window:]
        if m.get("role") == "user"
        and not m.get("observed")
        and m.get("content")
        and not m.get("tool_calls")
    ]
    if not recent_user:
        return None

    last = recent_user[-1]
    text = _text_from_content(last.get("content", ""))
    if not text:
        return None

    _, body = _extract_sender(text)
    body = body.strip()
    if len(body) > 100:
        body = body[:100].rstrip() + "…"
    return body if body else None


# ------------------------------------------------------------------ #
# Main entry point                                                     #
# ------------------------------------------------------------------ #

def build_group_reset_context(
    messages: List[Dict[str, Any]],
    n_messages: int = 20,
) -> Optional[str]:
    """Build the group context block to inject after a session reset.

    Args:
        messages: Full transcript from load_transcript()
        n_messages: How many recent turns to include

    Returns:
        Formatted context block string, or None if nothing useful.
    """
    if not messages:
        return None

    block = format_group_history(messages, max_messages=n_messages)
    return block if block else None


# ------------------------------------------------------------------ #
# Response targeting                                                   #
# ------------------------------------------------------------------ #

# Patterns that suggest an open question directed at the group
# (not necessarily at Hermes, but answerable by anyone present).
_OPEN_QUESTION_RE = re.compile(
    r"(\?|"
    r"\b(who|what|how|when|where|why|which|"
    r"can\s+anyone|does\s+anyone|did\s+anyone|"
    r"has\s+anyone|could\s+someone|would\s+anyone|"
    r"is\s+there\s+anyone|anyone\s+know|"
    r"any\s+ideas|any\s+thoughts|any\s+suggestions)\b)",
    re.IGNORECASE,
)

# Patterns indicating an attempt to address a named entity (not Hermes).
# We match a leading "@" or trailing ":" typical of addressing someone.
_NAMED_RECIPIENT_RE = re.compile(
    r"@\w+|^\s*\w[\w\s]{0,30}:",  # "@alice" or "Alice:" at start of message
    re.IGNORECASE,
)


@dataclass
class ChannelContext:
    """Context about the group/channel session passed to should_respond().

    Attributes:
        bot_names: Names/handles the bot is known by in this channel
            (e.g. ["Hermes", "fergus", "@hermes_bot"]). Used for explicit
            mention detection.  Matching is case-insensitive.
        history: Current session transcript (list of message dicts in the
            standard gateway format: {role, content, ...}).  Used to detect
            whether Hermes is already actively participating.
        reply_to_message_id: The message_id of the message this event is
            replying to, if any (from MessageEvent.reply_to_message_id).
        bot_last_message_id: The message_id of the most recent message
            Hermes sent in this channel, if known.  Used to detect when the
            incoming message is a direct reply to Hermes.
        proactive: If True, Hermes will also respond to apparent open
            group questions even without an explicit mention.  Default False.
    """

    bot_names: List[str] = field(default_factory=list)
    history: List[Dict[str, Any]] = field(default_factory=list)
    reply_to_message_id: Optional[str] = None
    bot_last_message_id: Optional[str] = None
    proactive: bool = False


def _is_explicitly_mentioned(text: str, bot_names: List[str]) -> bool:
    """Return True if the message text explicitly addresses the bot.

    Detects:
    - "@<name>" style mentions
    - Plain-name mentions: "hermes, ..." or "hey Hermes..."
    - Case-insensitive
    """
    if not text or not bot_names:
        return False
    text_lower = text.lower()
    for name in bot_names:
        if not name:
            continue
        n = name.lstrip("@").lower()
        # @-mention
        if f"@{n}" in text_lower:
            return True
        # Name followed by punctuation/space or at end
        pattern = rf"\b{re.escape(n)}\b"
        if re.search(pattern, text_lower):
            return True
    return False


def _is_reply_to_bot(
    reply_to_message_id: Optional[str],
    bot_last_message_id: Optional[str],
    history: List[Dict[str, Any]],
) -> bool:
    """Return True when the incoming message is a direct reply to a Hermes message.

    Checks:
    1. reply_to_message_id matches bot_last_message_id (fast path).
    2. The replied-to message_id appears in assistant turns in history
       (slower but accurate when bot_last_message_id is unavailable).
    """
    if not reply_to_message_id:
        return False
    if bot_last_message_id and reply_to_message_id == bot_last_message_id:
        return True
    # Check history for assistant turns that carry this message_id
    for msg in history:
        if msg.get("role") == "assistant":
            mid = msg.get("message_id") or msg.get("id")
            if mid and str(mid) == str(reply_to_message_id):
                return True
    return False


def _hermes_is_active_participant(history: List[Dict[str, Any]]) -> bool:
    """Return True when Hermes has already responded at least once in the session.

    An active participant means there is at least one assistant turn in the
    current session transcript (not counting tool-call relay turns or empty
    content).
    """
    for msg in history:
        if (
            msg.get("role") == "assistant"
            and not msg.get("tool_calls")
            and msg.get("content")
        ):
            return True
    return False


def _looks_like_open_group_question(text: str) -> bool:
    """Return True when the message looks like an open question to the group.

    Used for the optional proactive mode (rule 4).
    The heuristic is intentionally coarse — we look for interrogative
    markers and question punctuation but do NOT try to parse the message.
    """
    if not text:
        return False
    return bool(_OPEN_QUESTION_RE.search(text))


def should_respond(
    message_text: str,
    context: ChannelContext,
) -> bool:
    """Decide whether Hermes should respond in a group/channel context.

    Evaluates four rules in priority order:

    1. **Explicit mention** — always respond.
    2. **Reply to bot or active thread** — respond to maintain continuity.
    3. **Side conversation** — stay silent (default fall-through).
    4. **Proactive open question** — respond only when context.proactive=True.

    Args:
        message_text: The incoming message text (already rendered, with
            @mentions substituted to readable form if applicable).
        context: Contextual metadata about the channel session.

    Returns:
        True if Hermes should respond, False to stay silent.
    """
    # Rule 1 — explicit mention: always respond.
    if _is_explicitly_mentioned(message_text, context.bot_names):
        return True

    # Rule 1b — direct reply to a Hermes message: always respond.
    if _is_reply_to_bot(
        context.reply_to_message_id,
        context.bot_last_message_id,
        context.history,
    ):
        return True

    # Rule 2 — active thread continuation: Hermes is already in the conversation.
    if _hermes_is_active_participant(context.history):
        return True

    # Rule 4 — proactive mode: open group question (before rule 3 fall-through).
    if context.proactive and _looks_like_open_group_question(message_text):
        return True

    # Rule 3 — side conversation: stay silent.
    return False
