from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent.runtime_context_layer import build_runtime_context
from agent.timeline_sync import coerce_epoch_seconds


def _env_disabled(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"0", "false", "no", "off", "disabled"}


def _get_config_value(config: dict[str, Any], key: str, default: Any) -> Any:
    section = config.get("agent") if isinstance(config, dict) else None
    if isinstance(section, dict) and key in section:
        return section.get(key)
    return default


def _load_settings() -> dict[str, Any]:
    settings = {
        "enabled": True,
        "recent_window_minutes": 30,
        "max_events": 8,
        "include_other_platforms": True,
    }
    try:
        from hermes_cli.config import load_config

        config = load_config()
        settings["enabled"] = bool(_get_config_value(config, "timeline_sync_enabled", settings["enabled"]))
        settings["recent_window_minutes"] = int(
            _get_config_value(config, "timeline_sync_recent_window_minutes", settings["recent_window_minutes"])
        )
        settings["max_events"] = int(_get_config_value(config, "timeline_sync_max_events", settings["max_events"]))
        settings["include_other_platforms"] = bool(
            _get_config_value(config, "timeline_sync_include_other_platforms", settings["include_other_platforms"])
        )
    except Exception:
        pass

    env_enabled = os.getenv("HERMES_TIMELINE_SYNC_ENABLED")
    if _env_disabled(env_enabled):
        settings["enabled"] = False
    return settings


def _now_override() -> datetime | None:
    raw = os.getenv("HERMES_TIMELINE_SYNC_NOW")
    epoch = coerce_epoch_seconds(raw)
    if epoch is None:
        return None
    return datetime.fromtimestamp(epoch, tz=timezone.utc)


def on_pre_llm_call(
    *,
    session_id: str = "",
    user_message: str = "",
    conversation_history: list[dict[str, Any]] | None = None,
    platform: str = "",
    model: str = "",
    **kwargs: Any,
) -> dict[str, str] | None:
    settings = _load_settings()
    if not settings.get("enabled", True):
        return None

    db_override = os.getenv("HERMES_TIMELINE_SYNC_DB", "").strip()
    db_path = Path(db_override).expanduser() if db_override else None
    if db_path is None:
        try:
            from hermes_constants import get_hermes_home

            default_db = get_hermes_home() / "state.db"
        except Exception:
            default_db = Path.home() / ".hermes" / "state.db"
        if not default_db.exists():
            return None
    context = build_runtime_context(
        db_path=db_path,
        now=_now_override(),
        session_id=session_id or "",
        platform=platform or "",
        user_message=user_message or "",
        conversation_history=conversation_history or [],
        recent_window_minutes=max(0, int(settings.get("recent_window_minutes", 30))),
        max_events=max(0, int(settings.get("max_events", 8))),
        include_other_platforms=bool(settings.get("include_other_platforms", True)),
    )
    if not context.strip():
        return None
    return {"context": context}


def register(ctx) -> None:
    ctx.register_hook("pre_llm_call", on_pre_llm_call)
