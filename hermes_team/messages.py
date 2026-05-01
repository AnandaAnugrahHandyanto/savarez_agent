from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .json_store import JsonStateStore

TZ = timezone(timedelta(hours=8))


@dataclass
class TeamEvent:
    event: str
    task_id: str
    run_id: str
    role: str | None = None
    agent_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(TZ).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TeamEventStore(JsonStateStore):
    def __init__(self, state_dir: Path | None = None) -> None:
        super().__init__(state_dir)
        self.path = self.state_dir / 'events.json'

    def append(self, event: TeamEvent) -> dict[str, Any]:
        data = self._load_json(self.path, {'events': []})
        if not isinstance(data, dict):
            data = {'events': []}
        data.setdefault('events', []).append(event.to_dict())
        self._save_json(self.path, data)
        return event.to_dict()

    def list(self, task_id: str | None = None, run_id: str | None = None) -> list[dict[str, Any]]:
        data = self._load_json(self.path, {'events': []})
        events = data.get('events', []) if isinstance(data, dict) else []
        if task_id is not None:
            events = [event for event in events if event.get('task_id') == task_id]
        if run_id is not None:
            events = [event for event in events if event.get('run_id') == run_id]
        return events


def append_event(event: TeamEvent, state_dir: Path | None = None) -> dict[str, Any]:
    return TeamEventStore(state_dir).append(event)


def list_events(task_id: str | None = None, run_id: str | None = None, state_dir: Path | None = None) -> list[dict[str, Any]]:
    return TeamEventStore(state_dir).list(task_id=task_id, run_id=run_id)
