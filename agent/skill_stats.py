"""Skill load statistics tracking.

Records every successful skill_view() call to ~/.hermes/.skills_stats.json
so that `hermes skills stats` and skills_check.py --watch report real usage
data instead of always-zero counters.
"""

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_STATS_LOCK = threading.Lock()
_STATS_PATH: Optional[Path] = None


def _get_stats_path() -> Path:
    global _STATS_PATH
    if _STATS_PATH is None:
        from hermes_constants import get_hermes_home

        _STATS_PATH = get_hermes_home() / ".skills_stats.json"
    return _STATS_PATH


def _record_skill_load(skill_name: str) -> None:
    """
    Record a skill load event to the stats file.

    Called after every successful skill_view() call to track which skills
    are actually being used vs. which are dead weight.
    """
    stats_file = _get_stats_path()

    with _STATS_LOCK:
        try:
            if stats_file.exists():
                stats = json.loads(stats_file.read_text(encoding="utf-8"))
            else:
                stats = {"skills": {}, "schema_version": 1}
        except (json.JSONDecodeError, OSError):
            stats = {"skills": {}, "schema_version": 1}

        now = datetime.now(timezone.utc).isoformat()

        if skill_name not in stats["skills"]:
            stats["skills"][skill_name] = {
                "load_count": 0,
                "last_used": None,
                "first_used": None,
            }

        stats["skills"][skill_name]["load_count"] += 1
        stats["skills"][skill_name]["last_used"] = now
        if stats["skills"][skill_name]["first_used"] is None:
            stats["skills"][skill_name]["first_used"] = now

        stats_file.write_text(
            json.dumps(stats, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


def _maybe_record_skill_load(skill_name: str) -> None:
    """
    Best-effort skill load recording.

    Silently ignores any exception so that stats tracking can never break
    the skill_view() tool itself.
    """
    try:
        _record_skill_load(skill_name)
    except Exception:
        pass
