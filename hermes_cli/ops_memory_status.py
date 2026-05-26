"""Read-only Hermes memory status for the Jenny Ops dashboard.

This module only reads profile-local config and memory files. It does not write
memory, compact memory, change config, or touch other profiles.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from hermes_cli.config import get_hermes_home, load_config

MEMORY_FILES = [
    ("memory", "MEMORY.md", "memory_char_limit"),
    ("user", "USER.md", "user_char_limit"),
]


def _split_entries(text: str) -> List[str]:
    return [entry.strip() for entry in text.split("\n§\n") if entry.strip()]


def _limit_for(config_memory: Dict[str, Any], key: str, fallback: int) -> int:
    raw = config_memory.get(key, fallback)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = fallback
    return max(value, 1)


def _tone(percent_used: float, exists: bool, enabled: bool) -> str:
    if not enabled:
        return "disabled"
    if not exists:
        return "missing"
    if percent_used >= 0.9:
        return "critical"
    if percent_used >= 0.75:
        return "warning"
    return "ok"


def _read_memory_file(base: Path, config_memory: Dict[str, Any], target: str, filename: str, limit_key: str) -> Dict[str, Any]:
    path = base / "memories" / filename
    exists = path.exists()
    text = path.read_text(encoding="utf-8", errors="replace") if exists else ""
    entries = _split_entries(text)
    duplicate_count = max(0, len(entries) - len(set(entries)))
    limit = _limit_for(config_memory, limit_key, 1)
    chars = len(text)
    percent_used = min(chars / limit, 999.0)
    enabled_key = "memory_enabled" if target == "memory" else "user_profile_enabled"
    enabled = bool(config_memory.get(enabled_key, True))
    return {
        "target": target,
        "filename": filename,
        "path": str(path),
        "exists": exists,
        "enabled": enabled,
        "chars": chars,
        "limit": limit,
        "percent_used": round(percent_used * 100, 1),
        "entries": len(entries),
        "duplicate_entries": duplicate_count,
        "status": _tone(percent_used, exists, enabled),
    }


def read_ops_memory_status(home: Optional[Path] = None) -> Dict[str, Any]:
    """Return a profile-local, read-only memory capacity/status summary."""

    base = home or get_hermes_home()
    config = load_config() or {}
    raw_memory = config.get("memory") if isinstance(config, dict) else None
    config_memory: Dict[str, Any] = dict(raw_memory) if isinstance(raw_memory, dict) else {}
    rows = [
        _read_memory_file(base, config_memory, target, filename, limit_key)
        for target, filename, limit_key in MEMORY_FILES
    ]
    worst_order = {"critical": 4, "warning": 3, "missing": 2, "disabled": 1, "ok": 0}
    worst = max((row["status"] for row in rows), key=lambda status: worst_order.get(status, 0), default="ok")
    total_chars = sum(int(row["chars"]) for row in rows)
    total_limit = sum(int(row["limit"]) for row in rows)
    return {
        "ok": True,
        "mode": "local_read_only",
        "profile_home": str(base),
        "provider": str(config_memory.get("provider") or "builtin"),
        "memory_enabled": bool(config_memory.get("memory_enabled", True)),
        "user_profile_enabled": bool(config_memory.get("user_profile_enabled", True)),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "status": worst,
        "total_chars": total_chars,
        "total_limit": max(total_limit, 1),
        "total_percent_used": round((total_chars / max(total_limit, 1)) * 100, 1),
        "files": rows,
        "warning": None,
    }
