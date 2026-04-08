"""Built-in hook: capture compact learning events for gateway self-improvement."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from hermes_cli.config import get_hermes_home


def _compact_context(event_type: str, context: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "event_type": event_type,
        "platform": context.get("platform", ""),
        "session_key": context.get("session_key", ""),
    }

    if event_type.startswith("command:"):
        out["command"] = context.get("command") or event_type.split(":", 1)[1]
        args = context.get("args", "")
        if isinstance(args, str) and args:
            out["args_preview"] = args[:120]

    if event_type == "agent:end":
        resp = context.get("response", "")
        if isinstance(resp, str):
            out["response_preview"] = resp[:160]

    if event_type in ("session:end", "session:reset"):
        out["user_id"] = context.get("user_id", "")

    return out


async def handle(event_type: str, context: dict[str, Any]) -> None:
    if event_type != "agent:end" and event_type != "session:end" and not event_type.startswith("command:"):
        return

    home: Path = get_hermes_home()
    path = home / "gateway_learning_events.jsonl"
    event = {
        "ts": int(time.time()),
        **_compact_context(event_type, context or {}),
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
