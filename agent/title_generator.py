"""Auto-generate short session titles from the first user/assistant exchange.

Runs asynchronously after the first response is delivered so it never
adds latency to the user-facing reply.
"""

import json
import logging
import threading
import time
from typing import Any, Callable, Dict, Optional

from agent.auxiliary_client import call_llm

logger = logging.getLogger(__name__)

# Callback signature: (task_name, exception) -> None. Used to surface
# auxiliary failures to the user through AIAgent._emit_auxiliary_failure
# so silent-drops (e.g. OpenRouter 402 exhausting the fallback chain)
# become visible instead of piling up as NULL session titles.
FailureCallback = Callable[[str, BaseException], None]
TitleCallback = Callable[[str], None]

_TITLE_PROMPT = (
    "Generate a short, descriptive title (3-7 words) for a conversation that starts with the "
    "following exchange. The title should capture the main topic or intent. "
    "Return ONLY the title text, nothing else. No quotes, no punctuation at the end, no prefixes."
)

_REFINE_TITLE_PROMPT = (
    "Generate an improved short, descriptive title (3-7 words) for a conversation whose real "
    "topic has become clearer after several turns. Prefer the actual current objective over the "
    "initial vague request. Return ONLY the title text, nothing else. No quotes, no punctuation "
    "at the end, no prefixes."
)

_TITLE_METADATA_KEY = "title_metadata"
_AUTO_TITLE_SOURCES = {"auto_initial", "auto_refined"}
_DEFAULT_TITLE_CONFIG = {
    "enabled": True,
    "initial_auto_title": True,
    "adaptive_retitle": True,
    "retitle_after_user_turns": 4,
    "retitle_after_compression": True,
    "retitle_auto_titles_only": True,
    "lock_manual_titles": True,
    "max_words": 7,
}


def _clean_title(title: str) -> Optional[str]:
    """Normalize an LLM-produced title and enforce the legacy 80-char cap."""
    title = (title or "").strip()
    title = title.strip('"\'')
    if title.lower().startswith("title:"):
        title = title[6:].strip()
    if len(title) > 80:
        title = title[:77] + "..."
    return title if title else None


def _effective_title_config(title_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Return merged session-title config without making config import mandatory."""
    cfg = dict(_DEFAULT_TITLE_CONFIG)
    if title_config is None:
        try:
            from hermes_cli.config import load_config

            title_config = (load_config() or {}).get("session_titles", {})
        except Exception:
            title_config = {}
    if isinstance(title_config, dict):
        cfg.update(title_config)
    return cfg


def _conversation_excerpt(conversation_history: list, max_messages: int = 12, max_chars: int = 4000) -> str:
    """Compact recent user/assistant context for adaptive retitling."""
    parts = []
    for msg in (conversation_history or [])[-max_messages:]:
        role = msg.get("role")
        if role not in {"user", "assistant"}:
            continue
        content = msg.get("content") or ""
        if not isinstance(content, str):
            content = str(content)
        content = content.strip()
        if not content:
            continue
        parts.append(f"{role.title()}: {content[:600]}")
    excerpt = "\n\n".join(parts)
    return excerpt[:max_chars]


def _parse_model_config(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _get_title_metadata(session_db, session_id: str) -> Dict[str, Any]:
    try:
        get_session = getattr(session_db, "get_session", None)
        if get_session is None:
            return {}
        row = get_session(session_id)
        if not row:
            return {}
        model_config = _parse_model_config(row.get("model_config"))
        metadata = model_config.get(_TITLE_METADATA_KEY)
        return dict(metadata) if isinstance(metadata, dict) else {}
    except Exception:
        return {}


def _merge_title_metadata(session_db, session_id: str, metadata: Dict[str, Any]) -> None:
    try:
        merge = getattr(session_db, "merge_session_model_config", None)
        if merge is None:
            return
        merge(session_id, {_TITLE_METADATA_KEY: metadata})
    except Exception:
        logger.debug("Failed to merge session title metadata", exc_info=True)


def mark_session_title_manual(session_db, session_id: str) -> None:
    """Record that the current session title came from explicit user intent."""
    if not session_db or not session_id:
        return
    metadata = _get_title_metadata(session_db, session_id)
    metadata.update(
        {
            "title_source": "manual",
            "title_locked": True,
            "title_updated_at": time.time(),
        }
    )
    _merge_title_metadata(session_db, session_id, metadata)


def generate_title(
    user_message: str,
    assistant_response: str,
    timeout: float = 30.0,
    failure_callback: Optional[FailureCallback] = None,
    main_runtime: Optional[dict] = None,
) -> Optional[str]:
    """Generate a session title from the first exchange.

    Uses the main runtime's model when available, falling back to the
    auxiliary LLM client (cheapest/fastest available model).
    Returns the title string or None on failure.

    ``failure_callback`` is invoked with ``(task, exception)`` when the
    auxiliary call raises — the caller typically wires this to
    ``AIAgent._emit_auxiliary_failure`` so the user sees a warning instead
    of silently accumulating untitled sessions.
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
            main_runtime=main_runtime,
        )
        title = _clean_title(response.choices[0].message.content or "")
        return title
    except Exception as e:
        # Log at WARNING so this shows up in agent.log without debug mode.
        # Full detail at debug level for operators who need the stack.
        logger.warning("Title generation failed: %s", e)
        logger.debug("Title generation traceback", exc_info=True)
        if failure_callback is not None:
            try:
                failure_callback("title generation", e)
            except Exception:
                logger.debug("Title generation failure_callback raised", exc_info=True)
        return None


def generate_refined_title(
    existing_title: str,
    conversation_history: list,
    timeout: float = 30.0,
    failure_callback: Optional[FailureCallback] = None,
    main_runtime: Optional[dict] = None,
) -> Optional[str]:
    """Generate a better title from later conversation context."""
    excerpt = _conversation_excerpt(conversation_history)
    if not excerpt:
        return None

    messages = [
        {"role": "system", "content": _REFINE_TITLE_PROMPT},
        {
            "role": "user",
            "content": f"Existing title: {existing_title or '(none)'}\n\nRecent conversation:\n{excerpt}",
        },
    ]

    try:
        response = call_llm(
            task="title_generation",
            messages=messages,
            max_tokens=500,
            temperature=0.3,
            timeout=timeout,
            main_runtime=main_runtime,
        )
        return _clean_title(response.choices[0].message.content or "")
    except Exception as e:
        logger.warning("Adaptive title refinement failed: %s", e)
        logger.debug("Adaptive title refinement traceback", exc_info=True)
        if failure_callback is not None:
            try:
                failure_callback("title refinement", e)
            except Exception:
                logger.debug("Title refinement failure_callback raised", exc_info=True)
        return None


def auto_title_session(
    session_db,
    session_id: str,
    user_message: str,
    assistant_response: str,
    failure_callback: Optional[FailureCallback] = None,
    main_runtime: Optional[dict] = None,
    title_callback: Optional[TitleCallback] = None,
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

    title = generate_title(
        user_message, assistant_response, failure_callback=failure_callback, main_runtime=main_runtime
    )
    if not title:
        return

    try:
        session_db.set_session_title(session_id, title)
        _merge_title_metadata(
            session_db,
            session_id,
            {
                "title_source": "auto_initial",
                "title_locked": False,
                "title_updated_at": time.time(),
                "title_turn_count": 1,
            },
        )
        logger.debug("Auto-generated session title: %s", title)
        if title_callback is not None:
            try:
                title_callback(title)
            except Exception:
                logger.debug("Auto-title callback failed", exc_info=True)
    except Exception as e:
        logger.debug("Failed to set auto-generated title: %s", e)


def _refine_title_session_worker(
    session_db,
    session_id: str,
    current_title: str,
    conversation_history: list,
    user_msg_count: int,
    metadata: Dict[str, Any],
    failure_callback: Optional[FailureCallback] = None,
    main_runtime: Optional[dict] = None,
    title_callback: Optional[TitleCallback] = None,
) -> None:
    title = generate_refined_title(
        current_title,
        conversation_history,
        failure_callback=failure_callback,
        main_runtime=main_runtime,
    )
    if not title or title == current_title:
        return

    try:
        previous_title = current_title
        session_db.set_session_title(session_id, title)
        updated_metadata = dict(metadata)
        updated_metadata.update(
            {
                "title_source": "auto_refined",
                "title_locked": False,
                "title_updated_at": time.time(),
                "title_turn_count": user_msg_count,
                "previous_title": previous_title,
            }
        )
        _merge_title_metadata(session_db, session_id, updated_metadata)
        logger.debug("Refined session title: %s", title)
        if title_callback is not None:
            try:
                title_callback(title)
            except Exception:
                logger.debug("Adaptive title callback failed", exc_info=True)
    except Exception as e:
        logger.debug("Failed to set refined title: %s", e)


def maybe_refine_title(
    session_db,
    session_id: str,
    conversation_history: list,
    failure_callback: Optional[FailureCallback] = None,
    main_runtime: Optional[dict] = None,
    title_callback: Optional[TitleCallback] = None,
    title_config: Optional[Dict[str, Any]] = None,
    run_in_background: bool = True,
) -> None:
    """Maybe re-evaluate an auto-generated title after the topic stabilizes.

    The first implementation is intentionally conservative: it refines only
    titles with auto provenance, never unknown/manual titles by default, and
    only once after the configured user-turn threshold.
    """
    if not session_db or not session_id:
        return

    cfg = _effective_title_config(title_config)
    if not cfg.get("enabled", True) or not cfg.get("adaptive_retitle", True):
        return

    user_msg_count = sum(1 for m in (conversation_history or []) if m.get("role") == "user")
    threshold = int(cfg.get("retitle_after_user_turns") or 4)
    if user_msg_count < threshold:
        return

    try:
        current_title = session_db.get_session_title(session_id)
    except Exception:
        return
    if not current_title:
        return

    metadata = _get_title_metadata(session_db, session_id)
    if metadata.get("title_locked"):
        return

    source = metadata.get("title_source")
    if cfg.get("retitle_auto_titles_only", True) and source not in _AUTO_TITLE_SOURCES:
        return

    if source == "auto_refined" and int(metadata.get("title_turn_count") or 0) >= threshold:
        return

    args = (
        session_db,
        session_id,
        current_title,
        conversation_history,
        user_msg_count,
        metadata,
    )
    kwargs = {
        "failure_callback": failure_callback,
        "main_runtime": main_runtime,
        "title_callback": title_callback,
    }
    if not run_in_background:
        _refine_title_session_worker(*args, **kwargs)
        return

    thread = threading.Thread(
        target=_refine_title_session_worker,
        args=args,
        kwargs=kwargs,
        daemon=True,
        name="adaptive-title",
    )
    thread.start()


def maybe_auto_title(
    session_db,
    session_id: str,
    user_message: str,
    assistant_response: str,
    conversation_history: list,
    failure_callback: Optional[FailureCallback] = None,
    main_runtime: Optional[dict] = None,
    title_callback: Optional[TitleCallback] = None,
) -> None:
    """Fire-and-forget title generation after the first exchange.

    Only generates a title when:
    - This appears to be the first user→assistant exchange
    - No title is already set
    """
    if not session_db or not session_id or not user_message or not assistant_response:
        return

    cfg = _effective_title_config()
    if not cfg.get("enabled", True):
        return

    # Count user messages in history to detect first exchange.
    # conversation_history includes the exchange that just happened,
    # so for a first exchange we expect exactly 1 user message
    # (or 2 counting system). Be generous: generate on first 2 exchanges.
    user_msg_count = sum(1 for m in (conversation_history or []) if m.get("role") == "user")
    if user_msg_count > 2:
        maybe_refine_title(
            session_db,
            session_id,
            conversation_history,
            failure_callback=failure_callback,
            main_runtime=main_runtime,
            title_callback=title_callback,
            title_config=cfg,
        )
        return
    if not cfg.get("initial_auto_title", True):
        return

    thread = threading.Thread(
        target=auto_title_session,
        args=(session_db, session_id, user_message, assistant_response),
        kwargs={
            "failure_callback": failure_callback,
            "main_runtime": main_runtime,
            "title_callback": title_callback,
        },
        daemon=True,
        name="auto-title",
    )
    thread.start()
