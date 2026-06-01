"""Heartbeat context-pack construction."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from .models import HeartbeatContextPack, SourceObservation
from .sources import collect_curated_memory, collect_kanban


def _workspace() -> Path:
    from hermes_cli.config import read_raw_config

    raw = read_raw_config() or {}
    terminal = raw.get("terminal")
    if isinstance(terminal, dict) and terminal.get("cwd"):
        return Path(str(terminal["cwd"])).expanduser()
    return Path.cwd()


def _instructions(config: Dict[str, Any], max_chars: int = 6000) -> str:
    path = _workspace() / str(config.get("instructions_file") or "HEARTBEAT.md")
    try:
        return path.read_text(encoding="utf-8")[:max_chars]
    except (FileNotFoundError, OSError, UnicodeError):
        return ""


def build_context_pack(
    heartbeat_id: str,
    config: Dict[str, Any],
    *,
    recent_notifications: List[Dict[str, Any]],
) -> HeartbeatContextPack:
    observations: List[SourceObservation] = []
    sources = config["sources"]
    if sources["kanban"].get("enabled", True):
        observations.append(collect_kanban(sources["kanban"]))
    if sources["curated_memory"].get("enabled", True):
        observations.append(collect_curated_memory(sources["curated_memory"]))
    return HeartbeatContextPack(
        heartbeat_id=heartbeat_id,
        generated_at=datetime.now(timezone.utc).isoformat(),
        timezone=str(config.get("timezone") or "local"),
        instructions=_instructions(config),
        observations=observations,
        recent_notifications=recent_notifications,
        policy_summary={
            "cooldown_minutes": config["delivery"]["cooldown_minutes"],
            "max_notifications_per_day": config["delivery"]["max_notifications_per_day"],
        },
    )
