"""Read-only social platform status data for the Jenny Ops dashboard.

This module intentionally reads a local JSON status snapshot only. It does not
call YouTube, Meta, TikTok, or any other external platform API, and it does not
write files, schedule jobs, change privacy, upload, delete, or mutate tokens.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from hermes_constants import get_hermes_home

DEFAULT_SOCIAL_PLATFORMS: List[Dict[str, Any]] = [
    {
        "platform": "YouTube",
        "published": None,
        "scheduled": None,
        "issues_private": "Queue reset / private check needed",
        "readiness": "Canonical upload engine, but live counts require a read-only sync.",
        "source": "Default dashboard status; no local sync file found.",
        "status": "needs_sync",
    },
    {
        "platform": "Facebook",
        "published": None,
        "scheduled": None,
        "issues_private": "Legacy old-style queue blocked",
        "readiness": "Native Reels path exists; use only approved current-quality packages.",
        "source": "Default dashboard status; no local sync file found.",
        "status": "needs_sync",
    },
    {
        "platform": "Instagram",
        "published": None,
        "scheduled": "0 known scheduler",
        "issues_private": "Immediate publish only / API readiness check",
        "readiness": "Do not call scheduling ready until a real scheduler and token check exist.",
        "source": "Default dashboard status; no local sync file found.",
        "status": "needs_sync",
    },
    {
        "platform": "TikTok",
        "published": 0,
        "scheduled": 0,
        "issues_private": "Onboarding/API not ready",
        "readiness": "Format support is not posting readiness; OAuth/app review remains gated.",
        "source": "Default dashboard status; no local sync file found.",
        "status": "blocked",
    },
]


def social_status_path() -> Path:
    """Return the profile-local social platform status snapshot path."""

    return get_hermes_home() / "state" / "ops-center" / "social-platform-status.json"


def _display_count(value: Any) -> str:
    if value is None:
        return "Needs sync"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        return str(int(value)) if float(value).is_integer() else str(value)
    text = str(value).strip()
    return text or "Needs sync"


def _normalize_platform(raw: Dict[str, Any], default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    base = dict(default or {})
    base.update(raw or {})
    platform = str(base.get("platform") or "Unknown").strip() or "Unknown"
    return {
        "platform": platform,
        "published": _display_count(base.get("published")),
        "scheduled": _display_count(base.get("scheduled")),
        "issues_private": str(base.get("issues_private") or base.get("issuesPrivate") or "Needs sync").strip() or "Needs sync",
        "readiness": str(base.get("readiness") or "Read-only status only; no platform action performed.").strip(),
        "source": str(base.get("source") or "Local status snapshot").strip(),
        "status": str(base.get("status") or "needs_sync").strip(),
        "last_checked_at": base.get("last_checked_at"),
    }


def _merge_defaults(items: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_name = {str(item.get("platform", "")).lower(): item for item in items if item.get("platform")}
    merged: List[Dict[str, Any]] = []
    for default in DEFAULT_SOCIAL_PLATFORMS:
        key = str(default["platform"]).lower()
        merged.append(_normalize_platform(by_name.pop(key, {}), default))
    for extra in by_name.values():
        merged.append(_normalize_platform(extra))
    return merged


def read_social_platform_status(path: Optional[Path] = None) -> Dict[str, Any]:
    """Read and normalize the local social platform status snapshot.

    Missing files return conservative defaults. Invalid JSON also returns defaults
    with a warning instead of failing the dashboard, because this is an
    observability panel and must not become an execution path.
    """

    status_file = path or social_status_path()
    base: Dict[str, Any] = {
        "ok": True,
        "mode": "local_read_only",
        "path": str(status_file),
        "updated_at": None,
        "warning": None,
        "platforms": _merge_defaults([]),
    }

    if not status_file.exists():
        return base

    try:
        data = json.loads(status_file.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - exact JSON error varies
        base["warning"] = f"Could not read local status snapshot: {exc}"
        return base

    platforms = data.get("platforms", data if isinstance(data, list) else [])
    if not isinstance(platforms, list):
        base["warning"] = "Local status snapshot has no list-valued platforms field."
        return base

    base["updated_at"] = data.get("updated_at") if isinstance(data, dict) else None
    base["source"] = data.get("source") if isinstance(data, dict) else None
    base["platforms"] = _merge_defaults([item for item in platforms if isinstance(item, dict)])
    return base
