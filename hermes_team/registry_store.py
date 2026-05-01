from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .json_store import JsonStateStore

TZ = timezone(timedelta(hours=8))


def _now_iso() -> str:
    return datetime.now(TZ).isoformat()


class RegistryStore(JsonStateStore):
    """Hermes-native task/session registry.

    Persists the canonical team run/session registry under HERMES_HOME/state/team.
    """

    def __init__(self, state_dir: Path | None = None) -> None:
        super().__init__(state_dir)
        self.path = self.state_dir / 'task_run_session_registry.json'

    def load(self) -> dict[str, Any]:
        data = self._load_json(self.path, {'tasks': {}})
        if not isinstance(data, dict):
            return {'tasks': {}}
        data.setdefault('tasks', {})
        return data

    def save(self, payload: dict[str, Any]) -> None:
        self._save_json(self.path, payload)

    def _ensure_task_entry(self, data: dict[str, Any], task_id: str) -> dict[str, Any]:
        tasks = data.setdefault('tasks', {})
        return tasks.setdefault(task_id, {
            'jobIds': [],
            'runIds': [],
            'sessionIds': [],
            'sessionKeys': [],
            'notes': [],
            'lastStatus': 'linked',
            'updatedAt': _now_iso(),
        })

    @staticmethod
    def _append_unique(entry: dict[str, Any], key: str, value: str | None) -> None:
        if not value:
            return
        values = entry.setdefault(key, [])
        if value not in values:
            values.append(value)

    def bind_mapping(
        self,
        task_id: str,
        job_id: str | None = None,
        session_id: str | None = None,
        session_key: str | None = None,
        run_id: str | None = None,
        note: str = '',
        source: str = '',
        status: str | None = None,
    ) -> dict[str, Any]:
        data = self.load()
        entry = self._ensure_task_entry(data, task_id)
        self._append_unique(entry, 'jobIds', job_id)
        self._append_unique(entry, 'runIds', run_id)
        self._append_unique(entry, 'sessionIds', session_id)
        self._append_unique(entry, 'sessionKeys', session_key)
        if note or source:
            entry.setdefault('notes', []).append({
                'at': _now_iso(),
                'note': note,
                'source': source,
            })
        if status:
            entry['lastStatus'] = status
        entry['updatedAt'] = _now_iso()
        self.save(data)
        return data

    def update_mapping_status(self, task_id: str, status: str, note: str = '', source: str = '') -> dict[str, Any]:
        data = self.load()
        entry = self._ensure_task_entry(data, task_id)
        entry['lastStatus'] = status
        if note or source:
            entry.setdefault('notes', []).append({
                'at': _now_iso(),
                'note': note,
                'source': source,
            })
        entry['updatedAt'] = _now_iso()
        self.save(data)
        return data

    def sync_execution_payload(
        self,
        task_id: str,
        payload: dict[str, Any],
        note: str = '',
        source: str = '',
        status: str | None = None,
    ) -> dict[str, Any]:
        return self.bind_mapping(
            task_id=task_id,
            job_id=payload.get('jobId'),
            session_id=payload.get('sessionId'),
            session_key=payload.get('sessionKey'),
            run_id=payload.get('runId'),
            note=note,
            source=source,
            status=status,
        )
