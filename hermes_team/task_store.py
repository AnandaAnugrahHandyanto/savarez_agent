from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .json_store import JsonStateStore

TZ = timezone(timedelta(hours=8))
STATE_LABELS = {
    'pending': '待接收',
    'cio_triage': 'CIO分拣',
    'intel_gather': '情报/数据采集',
    'risk_review': '风控审核',
    'assigned': '已派发',
    'executing': '执行中',
    'review': '复核',
    'done': '已完成',
    'blocked': '阻塞',
    'cancelled': '取消',
}
VALID_TRANSITIONS = {
    'pending': ['cio_triage', 'cancelled'],
    'cio_triage': ['intel_gather', 'assigned', 'cancelled'],
    'intel_gather': ['risk_review', 'cancelled'],
    'risk_review': ['assigned', 'intel_gather', 'cancelled'],
    'assigned': ['executing', 'blocked', 'cancelled'],
    'executing': ['review', 'blocked', 'cancelled'],
    'review': ['done', 'risk_review', 'executing', 'cancelled'],
    'blocked': ['executing', 'assigned', 'review', 'cancelled'],
    'done': [],
    'cancelled': [],
}


class TaskStore(JsonStateStore):
    """Hermes-native task store.

    New writes go to HERMES_HOME/state/team/{tasks,archive}.json.
    Optional historical hydration is handled by an explicit read-only migration bridge.
    This store never writes outside the Hermes state directory.
    """

    def __init__(self, state_dir: Path | None = None) -> None:
        super().__init__(state_dir)
        self.tasks_path = self.state_dir / 'tasks.json'
        self.archive_path = self.state_dir / 'archive.json'

    def list_tasks(self) -> list[dict[str, Any]]:
        data = self._load_json(self.tasks_path, [])
        return data if isinstance(data, list) else []

    def list_archive(self) -> list[dict[str, Any]]:
        data = self._load_json(self.archive_path, [])
        return data if isinstance(data, list) else []

    def bootstrap_if_empty(self, active: list[dict[str, Any]], archived: list[dict[str, Any]]) -> dict[str, int]:
        current_active = self.list_tasks()
        current_archive = self.list_archive()
        if current_active or current_archive:
            return {'active': len(current_active), 'archived': len(current_archive)}
        self._save_json(self.tasks_path, active)
        self._save_json(self.archive_path, archived)
        return {'active': len(active), 'archived': len(archived)}

    @staticmethod
    def now_iso() -> str:
        return datetime.now(TZ).isoformat()
