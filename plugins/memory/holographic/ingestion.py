"""Durable deferred understanding ingestion for the holographic provider."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Any

from .enrichment import enrich_fact

logger = logging.getLogger(__name__)

_PREF_PATTERNS = [
    re.compile(r"\bI\s+(?:prefer|like|love|use|want|need)\s+(.+)", re.IGNORECASE),
    re.compile(r"\bmy\s+(?:favorite|preferred|default)\s+\w+\s+is\s+(.+)", re.IGNORECASE),
    re.compile(r"\bI\s+(?:always|never|usually)\s+(.+)", re.IGNORECASE),
]
_DECISION_PATTERNS = [
    re.compile(r"\bwe\s+(?:decided|agreed|chose)\s+(?:to\s+)?(.+)", re.IGNORECASE),
    re.compile(r"\bthe\s+project\s+(?:uses|needs|requires)\s+(.+)", re.IGNORECASE),
]

_MAX_FACT_LENGTH = 480
_MAX_TURN_CONTENT = 1200
_MAX_MESSAGE_CONTENT = 900


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"0", "false", "no", "off", ""}


def _as_int(value: Any, default: int, *, minimum: int = 1, maximum: int | None = None) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    parsed = max(minimum, parsed)
    if maximum is not None:
        parsed = min(maximum, parsed)
    return parsed


def ingest_settings(config: dict | None) -> dict:
    config = config or {}
    return {
        "deferred_ingest": _as_bool(config.get("deferred_ingest"), True),
        "turn_understanding": _as_bool(config.get("turn_understanding"), True),
        "ingest_batch_size": _as_int(config.get("ingest_batch_size"), 2, minimum=1, maximum=16),
        "ingest_max_pending": _as_int(config.get("ingest_max_pending"), 200, minimum=10, maximum=5000),
        "ingest_retry_delay_seconds": _as_int(config.get("ingest_retry_delay_seconds"), 60, minimum=5, maximum=1800),
        "session_ingest_message_limit": _as_int(config.get("session_ingest_message_limit"), 80, minimum=10, maximum=400),
    }


def queue_turn_ingest(store, config: dict | None, *, session_id: str, user_content: str, assistant_content: str) -> dict:
    settings = ingest_settings(config)
    if not settings["deferred_ingest"] or not settings["turn_understanding"]:
        return {"enqueued": False, "reason": "disabled"}

    payload = {
        "session_id": session_id or "",
        "user_content": (user_content or "").strip()[:_MAX_TURN_CONTENT],
        "assistant_content": (assistant_content or "").strip()[:_MAX_TURN_CONTENT],
    }
    if not payload["user_content"]:
        return {"enqueued": False, "reason": "empty"}

    dedupe_key = _dedupe_key("turn", payload)
    return store.enqueue_ingest(
        "turn",
        payload,
        dedupe_key=dedupe_key,
        source_channel="turn_understanding",
        session_id=session_id or "",
        max_pending=settings["ingest_max_pending"],
    )


def queue_session_ingest(store, config: dict | None, *, session_id: str, messages: list[dict]) -> dict:
    settings = ingest_settings(config)
    if not settings["deferred_ingest"]:
        return {"enqueued": False, "reason": "disabled"}

    sanitized = _sanitize_messages(messages, limit=settings["session_ingest_message_limit"])
    if not sanitized:
        return {"enqueued": False, "reason": "empty"}

    payload = {
        "session_id": session_id or "",
        "messages": sanitized,
    }
    dedupe_key = _dedupe_key("session", payload)
    return store.enqueue_ingest(
        "session",
        payload,
        dedupe_key=dedupe_key,
        source_channel="session_auto_extract",
        session_id=session_id or "",
        max_pending=settings["ingest_max_pending"],
    )


def drain_understanding_ingest(
    store,
    config: dict | None,
    *,
    limit: int | None = None,
    reason: str = "runtime",
) -> dict:
    settings = ingest_settings(config)
    if not settings["deferred_ingest"]:
        return {"claimed": 0, "processed": 0, "failed": 0, "facts_written": 0, "reason": "disabled"}

    batch_limit = limit if limit is not None else settings["ingest_batch_size"]
    claimed = store.claim_ingest_batch(limit=batch_limit)
    if not claimed:
        return {"claimed": 0, "processed": 0, "failed": 0, "facts_written": 0, "reason": reason}

    processed = 0
    failed = 0
    facts_written = 0
    for item in claimed:
        ingest_id = int(item["ingest_id"])
        try:
            written = _process_ingest_item(store, item)
            store.complete_ingest(ingest_id, facts_written=written)
            processed += 1
            facts_written += written
        except Exception as exc:
            failed += 1
            store.fail_ingest(
                ingest_id,
                str(exc),
                retry_delay_seconds=settings["ingest_retry_delay_seconds"],
            )
            logger.warning("Holographic ingest failed during %s: %s", reason, exc)

    return {
        "claimed": len(claimed),
        "processed": processed,
        "failed": failed,
        "facts_written": facts_written,
        "reason": reason,
    }


def _process_ingest_item(store, item: dict) -> int:
    payload = json.loads(item["payload_json"])
    ingest_type = item.get("ingest_type", "")

    if ingest_type == "turn":
        candidates = _extract_candidates_from_text(
            payload.get("user_content", ""),
            source_prefix="turn_understanding",
        )
    elif ingest_type == "session":
        candidates = []
        for message in payload.get("messages", []):
            if message.get("role") != "user":
                continue
            candidates.extend(
                _extract_candidates_from_text(
                    message.get("content", ""),
                    source_prefix="session_auto_extract",
                )
            )
    else:
        raise ValueError(f"unknown ingest type: {ingest_type}")

    written = 0
    for candidate in candidates:
        store.add_fact(
            candidate["content"],
            category=candidate["category"],
            source_channel=candidate["source_channel"],
            source_confidence=candidate["source_confidence"],
            intent_type=candidate["intent_type"],
            salience_score=candidate["salience_score"],
        )
        written += 1
    return written


def _extract_candidates_from_text(text: str, *, source_prefix: str) -> list[dict]:
    normalized = (text or "").strip()
    if len(normalized) < 10:
        return []

    enrichment = enrich_fact(normalized, source_channel=source_prefix)
    direct_pref = any(pattern.search(normalized) for pattern in _PREF_PATTERNS)
    direct_decision = any(pattern.search(normalized) for pattern in _DECISION_PATTERNS)
    has_structure = any(
        enrichment.to_dict().get(key)
        for key in ("entities", "projects", "topics", "dates", "times", "locations")
    )

    if direct_pref:
        category = "user_pref"
    elif direct_decision or enrichment.intent_type in {"decision", "goal", "task", "issue"} or enrichment.projects:
        category = "project"
    elif enrichment.intent_type in {"event"} and has_structure:
        category = "general"
    else:
        category = "general"

    should_capture = direct_pref or direct_decision
    if not should_capture:
        if enrichment.intent_type in {"goal", "task", "issue", "event"} and has_structure:
            should_capture = True
        elif enrichment.salience_score >= 0.72 and has_structure:
            should_capture = True

    if not should_capture:
        return []

    source_confidence = 0.66 if source_prefix.startswith("turn_") else 0.62
    if category == "user_pref":
        source_suffix = "user_pref"
    elif category == "project":
        source_suffix = "project"
    else:
        source_suffix = "general"

    return [{
        "content": normalized[:_MAX_FACT_LENGTH],
        "category": category,
        "source_channel": f"{source_prefix}:{source_suffix}",
        "source_confidence": source_confidence,
        "intent_type": enrichment.intent_type,
        "salience_score": enrichment.salience_score,
    }]


def _sanitize_messages(messages: list[dict], *, limit: int) -> list[dict]:
    sanitized: list[dict] = []
    for message in messages[-limit:]:
        role = str(message.get("role", "") or "")
        content = message.get("content", "")
        if role not in {"user", "assistant"} or not isinstance(content, str):
            continue
        compact = content.strip()
        if not compact:
            continue
        sanitized.append({
            "role": role,
            "content": compact[:_MAX_MESSAGE_CONTENT],
        })
    return sanitized


def _dedupe_key(ingest_type: str, payload: dict) -> str:
    digest = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    session_id = str(payload.get("session_id", "") or "")
    return f"{ingest_type}:{session_id}:{digest}"
