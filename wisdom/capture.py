"""Capture operations for Hermes Wisdom Kernel."""

from __future__ import annotations

from typing import Any

from wisdom.classify import classify_capture, detect_explicit_trigger
from wisdom.config import load_wisdom_config
from wisdom.db import WisdomDB
from wisdom.models import CaptureOutcome, WisdomConfig
from wisdom.redaction import detect_secret_like_text, ensure_salt, stable_hash


def effective_enabled(db: WisdomDB, config: WisdomConfig) -> bool:
    setting = db.get_setting("enabled")
    if setting is None:
        return config.enabled
    return setting.lower() in {"1", "true", "yes", "on"}


def effective_capture_mode(db: WisdomDB, config: WisdomConfig) -> str:
    setting = db.get_setting("capture_mode")
    mode = (setting or config.capture_mode or "explicit").lower()
    return "explicit" if mode not in {"off", "explicit"} else mode


def capture_text(
    text: str,
    *,
    channel: str = "gateway",
    source_kind: str = "text",
    session_key: object | None = None,
    message_ref: object | None = None,
    metadata: dict[str, Any] | None = None,
    config: WisdomConfig | None = None,
    db: WisdomDB | None = None,
    cleaned_text: str | None = None,
    require_enabled: bool = True,
) -> CaptureOutcome:
    config = config or load_wisdom_config()
    db = db or WisdomDB(config.db_path)
    db.init()

    if require_enabled and not effective_enabled(db, config):
        return CaptureOutcome("disabled", message="Wisdom is off.")
    if detect_secret_like_text(text):
        return CaptureOutcome("blocked_secret", message="Capture blocked because the text looks like it contains a secret.")

    trigger = detect_explicit_trigger(text)
    cleaned = cleaned_text if cleaned_text is not None else (trigger.cleaned_text if trigger else text.strip())
    classification = classify_capture(text, cleaned, trigger)
    salt = ensure_salt()
    raw_metadata = _safe_metadata(metadata or {})
    if trigger:
        raw_metadata["trigger"] = trigger.prefix

    record = db.create_capture(
        original_text=text,
        cleaned_text=cleaned,
        classification=classification,
        channel=channel,
        source_kind=source_kind,
        session_key_hash=stable_hash(session_key, salt=salt, prefix="sess_"),
        message_ref_hash=stable_hash(message_ref, salt=salt, prefix="msg_"),
        raw_metadata=raw_metadata,
        capture_metadata={"capture_version": 1},
    )
    return CaptureOutcome("captured", capture=record)


def _safe_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    allowed: dict[str, Any] = {}
    for key, value in metadata.items():
        key_text = str(key)
        if key_text.lower() in {"chat_id", "user_id", "message_id", "thread_id", "phone", "platform_id"}:
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            allowed[key_text] = value
    return allowed
