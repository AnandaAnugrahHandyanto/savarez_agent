from __future__ import annotations

from pathlib import Path
from typing import Any

from .json_store import JsonStateStore


class ApprovalStore(JsonStateStore):
    """Hermes-native approval store.

    Persists canonical approval state under HERMES_HOME/state/team.
    """

    def __init__(self, state_dir: Path | None = None) -> None:
        super().__init__(state_dir)
        self.path = self.state_dir / 'approvals.json'

    def list_approvals(self) -> list[dict[str, Any]]:
        data = self._load_json(self.path, [])
        return data if isinstance(data, list) else []

    def save(self, approvals: list[dict[str, Any]]) -> None:
        self._save_json(self.path, approvals)

    def upsert(self, approval: dict[str, Any], key: str = 'approval_id') -> list[dict[str, Any]]:
        approvals = self.list_approvals()
        approval_key = approval.get(key)
        if approval_key:
            for index, item in enumerate(approvals):
                if item.get(key) == approval_key:
                    approvals[index] = {**item, **approval}
                    self.save(approvals)
                    return approvals
        approvals.append(approval)
        self.save(approvals)
        return approvals
