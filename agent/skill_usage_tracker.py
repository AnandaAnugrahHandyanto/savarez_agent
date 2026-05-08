"""Best-effort persistence for skill usage and known CLI history."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from hermes_constants import get_hermes_home
from utils import atomic_json_write

logger = logging.getLogger(__name__)

_MAX_TIMESTAMPS_PER_CATEGORY = 30
_DEFAULT_USAGE_WINDOW_SECONDS = 30 * 86400
_DEFAULT_CLI_WINDOW_DAYS = 30


def _usage_path() -> Path:
    return get_hermes_home() / ".skill_usage.json"


def _known_clis_path() -> Path:
    return get_hermes_home() / ".skill_known_clis.json"


def _read_json(path: Path) -> dict:
    try:
        if not path.exists():
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        logger.debug("Could not read %s: %s", path, exc)
        return {}


def _write_json(path: Path, payload: dict) -> None:
    try:
        atomic_json_write(path, payload)
    except Exception as exc:
        logger.debug("Could not write %s: %s", path, exc)


def record_category_use(category: str) -> None:
    if not category:
        return
    data = _read_json(_usage_path())
    history = data.get(category) or []
    if not isinstance(history, list):
        history = []
    history.append(time.time())
    data[category] = history[-_MAX_TIMESTAMPS_PER_CATEGORY:]
    _write_json(_usage_path(), data)


def top_categories(within_seconds: int = _DEFAULT_USAGE_WINDOW_SECONDS) -> list[str]:
    data = _read_json(_usage_path())
    cutoff = time.time() - within_seconds
    scored: list[tuple[int, str]] = []
    for category, timestamps in data.items():
        if not isinstance(timestamps, list):
            continue
        recent = sum(
            1
            for timestamp in timestamps
            if isinstance(timestamp, (int, float)) and timestamp >= cutoff
        )
        if recent:
            scored.append((recent, str(category)))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [category for _score, category in scored]


def record_cli_seen(cli: str) -> None:
    if not cli:
        return
    data = _read_json(_known_clis_path())
    data[cli] = time.time()
    _write_json(_known_clis_path(), data)


def is_known_cli(cli: str, *, window_days: int = _DEFAULT_CLI_WINDOW_DAYS) -> bool:
    if not cli:
        return False
    data = _read_json(_known_clis_path())
    timestamp = data.get(cli)
    if not isinstance(timestamp, (int, float)):
        return False
    return (time.time() - timestamp) <= (window_days * 86400)


def usage_rank_epoch() -> str:
    path = _usage_path()
    try:
        mtime = path.stat().st_mtime if path.exists() else 0
    except OSError:
        mtime = 0
    day = int(mtime // 86400) if mtime else 0
    return str(day)

