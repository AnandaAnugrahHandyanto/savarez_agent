"""Voice benchmark telemetry for Hermes gateway voice turns."""

from __future__ import annotations

import json
import os
import time
import uuid
from collections import OrderedDict
from pathlib import Path
from typing import Any


DEFAULT_LIMIT = 5
MAX_EVENTS = 500


def new_turn_id() -> str:
    return f"voice-{int(time.time())}-{uuid.uuid4().hex[:8]}"


def bench_path() -> Path:
    raw = os.environ.get("HERMES_VOICE_BENCH_PATH")
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".hermes" / "voice_bench.jsonl"


def append_event(event: dict[str, Any]) -> None:
    payload = {
        "ts": time.time(),
        **event,
    }
    path = bench_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    except OSError:
        return


def recent_events(*, platform: str | None = None, chat_id: str | None = None, max_events: int = MAX_EVENTS) -> list[dict[str, Any]]:
    path = bench_path()
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-max_events:]
    except OSError:
        return []
    events: list[dict[str, Any]] = []
    for line in lines:
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(item, dict):
            continue
        if platform and str(item.get("platform") or "") != platform:
            continue
        if chat_id and str(item.get("chat_id") or "") != str(chat_id):
            continue
        events.append(item)
    return events


def grouped_turns(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    turns: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for item in events:
        turn_id = str(item.get("turn_id") or "").strip()
        if not turn_id:
            continue
        turn = turns.setdefault(
            turn_id,
            {
                "turn_id": turn_id,
                "ts": item.get("ts"),
                "platform": item.get("platform"),
                "chat_id": item.get("chat_id"),
                "message_id": item.get("message_id"),
                "stages": {},
            },
        )
        turn["ts"] = item.get("ts") or turn.get("ts")
        turn["platform"] = item.get("platform") or turn.get("platform")
        turn["chat_id"] = item.get("chat_id") or turn.get("chat_id")
        turn["message_id"] = item.get("message_id") or turn.get("message_id")
        stage = str(item.get("stage") or "").strip()
        if stage:
            turn["stages"][stage] = item
    return list(turns.values())


def _ms(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{value:.0f}ms"
    return "?"


def format_recent(platform: str | None = None, chat_id: str | None = None, *, limit: int = DEFAULT_LIMIT) -> str:
    events = recent_events(platform=platform, chat_id=chat_id)
    turns = grouped_turns(events)[-max(1, min(limit, 20)):]
    if not turns:
        return "Voice bench: no measured voice turns yet."

    lines = ["Voice bench recent turns:"]
    for turn in reversed(turns):
        stages = turn.get("stages") or {}
        stt = stages.get("stt") or {}
        agent = stages.get("agent") or {}
        tts = stages.get("tts") or {}
        delivery = stages.get("delivery") or {}
        stage_values = [
            stage.get("elapsed_ms")
            for stage in (stt, agent, tts, delivery)
            if isinstance(stage.get("elapsed_ms"), (int, float))
        ]
        total_ms = sum(stage_values) if stage_values else None
        status = "ok" if not any((s.get("error") for s in stages.values() if isinstance(s, dict))) else "warn"
        lines.append(
            f"- {status} total={_ms(total_ms)} "
            f"stt={_ms(stt.get('elapsed_ms'))} "
            f"agent={_ms(agent.get('elapsed_ms'))} "
            f"tts={_ms(tts.get('elapsed_ms'))} "
            f"send={_ms(delivery.get('elapsed_ms'))}"
        )
        transcript = str(stt.get("transcript") or "").strip()
        if transcript:
            lines.append(f"  heard: {transcript[:120]}")
        response = str(agent.get("response") or "").strip()
        if response:
            lines.append(f"  reply: {response[:120]}")
    return "\n".join(lines)
