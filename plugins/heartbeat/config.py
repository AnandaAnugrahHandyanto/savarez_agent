"""Configuration parsing for Hermes Heartbeat."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict


DEFAULT_CONFIG: Dict[str, Any] = {
    "enabled": False,
    "interval_minutes": 30,
    "jitter_minutes": 5,
    "timezone": "",
    "active_hours": {"enabled": False, "start": "08:00", "end": "22:00"},
    "budget": {"max_runtime_seconds": 90, "max_review_tokens": 1200},
    "delivery": {
        "targets": [],
        "cooldown_minutes": 60,
        "max_notifications_per_day": 6,
        "mirror_transcript": True,
    },
    "inbox": {
        "ttl_hours": 72,
        "max_active_findings": 20,
        "inject_max_findings": 3,
        "inject_max_chars": 2400,
    },
    "external_memory": {"publish_observations": True},
    "sources": {
        "kanban": {"enabled": True, "max_tasks": 30},
        "curated_memory": {"enabled": True, "max_chars": 6000},
    },
    "instructions_file": "HEARTBEAT.md",
}


def _merge(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    out = deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def _positive_int(cfg: Dict[str, Any], key: str, minimum: int = 1) -> int:
    value = cfg.get(key)
    if isinstance(value, bool):
        raise ValueError(f"heartbeat.{key} must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"heartbeat.{key} must be an integer") from exc
    if parsed < minimum:
        raise ValueError(f"heartbeat.{key} must be >= {minimum}")
    cfg[key] = parsed
    return parsed


def _validate_time(value: Any, key: str) -> str:
    text = str(value or "")
    parts = text.split(":")
    if len(parts) != 2:
        raise ValueError(f"heartbeat.active_hours.{key} must be HH:MM")
    try:
        hour, minute = (int(part) for part in parts)
    except ValueError as exc:
        raise ValueError(f"heartbeat.active_hours.{key} must be HH:MM") from exc
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError(f"heartbeat.active_hours.{key} must be HH:MM")
    return f"{hour:02d}:{minute:02d}"


def load_heartbeat_config() -> Dict[str, Any]:
    from hermes_cli.config import read_raw_config

    raw = read_raw_config() or {}
    block = raw.get("heartbeat")
    if block is None:
        block = {}
    if not isinstance(block, dict):
        raise ValueError("heartbeat config must be a mapping")
    cfg = _merge(DEFAULT_CONFIG, block)
    for section in (
        "active_hours",
        "budget",
        "delivery",
        "inbox",
        "external_memory",
        "sources",
    ):
        if not isinstance(cfg.get(section), dict):
            raise ValueError(f"heartbeat.{section} must be a mapping")
    for source in ("kanban", "curated_memory"):
        if not isinstance(cfg["sources"].get(source), dict):
            raise ValueError(f"heartbeat.sources.{source} must be a mapping")

    _positive_int(cfg, "interval_minutes")
    _positive_int(cfg, "jitter_minutes", minimum=0)
    _positive_int(cfg["budget"], "max_runtime_seconds")
    _positive_int(cfg["budget"], "max_review_tokens")
    _positive_int(cfg["delivery"], "cooldown_minutes", minimum=0)
    _positive_int(cfg["delivery"], "max_notifications_per_day", minimum=0)
    _positive_int(cfg["inbox"], "ttl_hours")
    _positive_int(cfg["inbox"], "max_active_findings")
    _positive_int(cfg["inbox"], "inject_max_findings")
    _positive_int(cfg["inbox"], "inject_max_chars")
    _positive_int(cfg["sources"]["kanban"], "max_tasks")
    _positive_int(cfg["sources"]["curated_memory"], "max_chars")
    cfg["active_hours"]["start"] = _validate_time(cfg["active_hours"].get("start"), "start")
    cfg["active_hours"]["end"] = _validate_time(cfg["active_hours"].get("end"), "end")
    if not isinstance(cfg["delivery"].get("targets"), list):
        raise ValueError("heartbeat.delivery.targets must be a list")
    return cfg
