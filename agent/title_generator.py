"""Auto-generate short session titles from the first user/assistant exchange.

Runs asynchronously after the first response is delivered so it never
adds latency to the user-facing reply.
"""

import logging
import threading
from typing import Optional

from agent.auxiliary_client import call_llm

logger = logging.getLogger(__name__)

_TITLE_PROMPT = (
    "You are a title generator. Read the conversation below and output a single short title "
    "(3-7 words) that captures the main topic or intent. "
    "RULES: Output ONLY the title — no quotes, no punctuation, no prefixes like 'Title:', no explanation, no formatting. "
    "Example valid outputs:\n"
    "  Debugging Python import errors\n"
    "  Setting up Docker environment\n"
    "  Fixing session title generation\n"
)


def generate_title(user_message: str, assistant_response: str, timeout: float = 30.0) -> Optional[str]:
    """Generate a session title from the first exchange.

    Uses the auxiliary LLM client (cheapest/fastest available model).
    Returns the title string or None on failure.
    """
    # Truncate long messages to keep the request small
    user_snippet = user_message[:500] if user_message else ""
    assistant_snippet = assistant_response[:500] if assistant_response else ""

    messages = [
        {"role": "system", "content": _TITLE_PROMPT},
        {"role": "user", "content": f"User: {user_snippet}\n\nAssistant: {assistant_snippet}"},
    ]

    try:
        response = call_llm(
            task="title_generation",
            messages=messages,
            max_tokens=500,
            temperature=0.3,
            timeout=timeout,
        )
        title = (response.choices[0].message.content or "").strip()
        # Strip MiniMax reasoning token prefix if it leaks into content
        if title.startswith("一致"):
            title = title[2:].strip()
        # Discard responses that look like the instruction prompt itself
        # (model failed to follow instructions and echoed the input back)
        prompt_fragments = [
            "generate a short",
            "return only the title",
            "no quotes, no punctuation",
            "no prefixes",
            "the title should capture",
        ]
        title_lower = title.lower()
        if any(frag in title_lower for frag in prompt_fragments):
            logger.warning("Title generation produced prompt-like output, discarding.")
            return None
        # Clean up: remove quotes, trailing punctuation, prefixes like "Title: "
        title = title.strip('"\'')
        if title.lower().startswith("title:"):
            title = title[6:].strip()
        # Enforce reasonable length
        if len(title) > 80:
            title = title[:77] + "..."
        return title if title else None
    except Exception as e:
        logger.debug("Title generation failed: %s", e)
        return None


def auto_title_session(
    session_db,
    session_id: str,
    user_message: str,
    assistant_response: str,
) -> None:
    """Generate and set a session title if one doesn't already exist.

    Called in a background thread after the first exchange completes.
    Silently skips if:
    - session_db is None
    - session already has a title (user-set or previously auto-generated)
    - title generation fails
    """
    if not session_db or not session_id:
        return

    # Check if title already exists (user may have set one via /title before first response)
    try:
        existing = session_db.get_session_title(session_id)
        if existing:
            return
    except Exception:
        return

    title = generate_title(user_message, assistant_response)
    if not title:
        return

    try:
        session_db.set_session_title(session_id, title)
        logger.debug("Auto-generated session title: %s", title)
    except Exception as e:
        logger.debug("Failed to set auto-generated title: %s", e)


def maybe_auto_title(
    session_db,
    session_id: str,
    user_message: str,
    assistant_response: str,
    conversation_history: list,
) -> None:
    """Fire-and-forget title generation after the first exchange.

    Only generates a title when:
    - This appears to be the first user→assistant exchange
    - No title is already set
    """
    if not session_db or not session_id or not user_message or not assistant_response:
        return

    # Count user messages in history to detect first exchange.
    # conversation_history includes the exchange that just happened,
    # so for a first exchange we expect exactly 1 user message
    # (or 2 counting system). Be generous: generate on first 2 exchanges.
    user_msg_count = sum(1 for m in (conversation_history or []) if m.get("role") == "user")
    if user_msg_count > 2:
        return

    thread = threading.Thread(
        target=auto_title_session,
        args=(session_db, session_id, user_message, assistant_response),
        daemon=True,
        name="auto-title",
    )
    thread.start()
