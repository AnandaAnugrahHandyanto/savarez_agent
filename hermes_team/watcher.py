from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .json_store import JsonStateStore
from .messages import TeamEventStore
from .orchestrator import TeamRunStore

TZ = timezone(timedelta(hours=8))


def _now_iso() -> str:
    return datetime.now(TZ).isoformat()


@dataclass
class TeamWatchSnapshot:
    run_id: str | None
    task_id: str | None
    status: str
    updated_at: str
    events_count: int
    latest_events: list[dict[str, Any]] = field(default_factory=list)
    steps: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    stale: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            'run_id': self.run_id,
            'task_id': self.task_id,
            'status': self.status,
            'updated_at': self.updated_at,
            'events_count': self.events_count,
            'latest_events': self.latest_events,
            'steps': self.steps,
            'errors': self.errors,
            'stale': self.stale,
        }


class TeamWatchStore(JsonStateStore):
    def __init__(self, state_dir: Path | None = None) -> None:
        super().__init__(state_dir)
        self.path = self.state_dir / 'watch.json'

    def save_snapshot(self, snapshot: TeamWatchSnapshot) -> dict[str, Any]:
        data = self._load_json(self.path, {'snapshots': {}})
        if not isinstance(data, dict):
            data = {'snapshots': {}}
        key = snapshot.run_id or snapshot.task_id or 'latest'
        data.setdefault('snapshots', {})[key] = snapshot.to_dict()
        data['updated_at'] = _now_iso()
        self._save_json(self.path, data)
        return data['snapshots'][key]

    def load(self) -> dict[str, Any]:
        data = self._load_json(self.path, {'snapshots': {}})
        return data if isinstance(data, dict) else {'snapshots': {}}


class TeamWatcher:
    def __init__(self, state_dir: Path | None = None) -> None:
        self.run_store = TeamRunStore(state_dir)
        self.event_store = TeamEventStore(state_dir)
        self.watch_store = TeamWatchStore(state_dir)

    def snapshot(self, *, run_id: str | None = None, task_id: str | None = None, limit: int = 20, stale_after_seconds: int = 900) -> TeamWatchSnapshot:
        runs = list((self.run_store.load().get('runs') or {}).values())
        if run_id:
            run = next((item for item in runs if item.get('run_id') == run_id), None)
        elif task_id:
            candidates = [item for item in runs if item.get('task_id') == task_id]
            run = sorted(candidates, key=lambda item: item.get('updated_at') or '', reverse=True)[0] if candidates else None
        else:
            run = sorted(runs, key=lambda item: item.get('updated_at') or '', reverse=True)[0] if runs else None

        resolved_run_id = str(run.get('run_id')) if run else run_id
        resolved_task_id = str(run.get('task_id')) if run else task_id
        events = self.event_store.list(task_id=resolved_task_id, run_id=resolved_run_id)
        latest = events[-int(limit):]
        updated_at = str((run or {}).get('updated_at') or (latest[-1].get('timestamp') if latest else _now_iso()))
        stale = False
        try:
            then = datetime.fromisoformat(updated_at)
            stale = (datetime.now(TZ) - then) > timedelta(seconds=int(stale_after_seconds))
        except Exception:
            stale = False
        snapshot = TeamWatchSnapshot(
            run_id=resolved_run_id,
            task_id=resolved_task_id,
            status=str((run or {}).get('status') or 'not_found'),
            updated_at=updated_at,
            events_count=len(events),
            latest_events=latest,
            steps=list((run or {}).get('steps') or []),
            errors=list((run or {}).get('errors') or []),
            stale=stale,
        )
        self.watch_store.save_snapshot(snapshot)
        return snapshot

    def render_text(self, snapshot: TeamWatchSnapshot) -> str:
        lines = [
            f"run_id: {snapshot.run_id or '-'}",
            f"task_id: {snapshot.task_id or '-'}",
            f"status: {snapshot.status}",
            f"updated_at: {snapshot.updated_at}",
            f"events: {snapshot.events_count}",
            f"stale: {snapshot.stale}",
            'steps:',
        ]
        for step in snapshot.steps:
            lines.append(f"  - {step.get('role')}: {step.get('status')} {step.get('summary') or step.get('error') or ''}".rstrip())
        if snapshot.errors:
            lines.append('errors:')
            lines.extend(f"  - {err}" for err in snapshot.errors)
        if snapshot.latest_events:
            lines.append('latest_events:')
            for event in snapshot.latest_events[-5:]:
                lines.append(f"  - {event.get('timestamp')} {event.get('event')} role={event.get('role') or '-'}")
        return '\n'.join(lines)
