"""Profile-scoped structured event logging for Heartbeat runs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from hermes_constants import get_hermes_home


def heartbeat_log_path() -> Path:
    return get_hermes_home() / "logs" / "heartbeat.jsonl"


def log_event(event: str, **fields: Any) -> None:
    path = heartbeat_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    record: Dict[str, Any] = {
        "event": event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    record.update(fields)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, default=str) + "\n")
