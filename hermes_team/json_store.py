from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .paths import ensure_team_state_dir


class JsonStateStore:
    """Shared JSON persistence helpers for Hermes team state stores.

    [P4] Centralize repeated JSON read/write logic so task/approval/registry stores stay behaviorally aligned.
    """

    def __init__(self, state_dir: Path | None = None) -> None:
        self.state_dir = state_dir or ensure_team_state_dir()

    @staticmethod
    def _clone_default(default: Any) -> Any:
        return deepcopy(default)

    def _load_json(self, path: Path, default: Any) -> Any:
        if not path.exists():
            return self._clone_default(default)
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            return self._clone_default(default)
        return data

    def _save_json(self, path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
