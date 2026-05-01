from __future__ import annotations

from pathlib import Path
from typing import Any

from .paths import ensure_team_state_dir
from .registry_store import RegistryStore

_DEFAULT_STORE = RegistryStore(ensure_team_state_dir())


def configure_registry_store(state_dir: Path | None = None) -> RegistryStore:
    global _DEFAULT_STORE
    _DEFAULT_STORE = RegistryStore(state_dir or ensure_team_state_dir())
    return _DEFAULT_STORE


def get_registry_store() -> RegistryStore:
    return _DEFAULT_STORE


def load_registry() -> dict[str, Any]:
    return _DEFAULT_STORE.load()


def bind_mapping(
    task_id: str,
    job_id: str | None = None,
    session_id: str | None = None,
    session_key: str | None = None,
    run_id: str | None = None,
    note: str = '',
    source: str = '',
    status: str | None = None,
) -> dict[str, Any]:
    return _DEFAULT_STORE.bind_mapping(
        task_id=task_id,
        job_id=job_id,
        session_id=session_id,
        session_key=session_key,
        run_id=run_id,
        note=note,
        source=source,
        status=status,
    )


def update_mapping_status(task_id: str, status: str, note: str = '', source: str = '') -> dict[str, Any]:
    return _DEFAULT_STORE.update_mapping_status(task_id=task_id, status=status, note=note, source=source)


def sync_execution_payload(
    task_id: str,
    payload: dict[str, Any],
    note: str = '',
    source: str = '',
    status: str | None = None,
) -> dict[str, Any]:
    return _DEFAULT_STORE.sync_execution_payload(
        task_id=task_id,
        payload=payload,
        note=note,
        source=source,
        status=status,
    )
