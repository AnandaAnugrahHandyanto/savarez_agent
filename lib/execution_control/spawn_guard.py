from __future__ import annotations

from typing import Any

from hermes_team.registry_api import sync_execution_payload, update_mapping_status

__all__ = ['sync_execution_payload', 'update_mapping_status']


def record_spawn_execution(
    task_id: str,
    payload: dict[str, Any],
    *,
    note: str = '',
    source: str = 'execution_control.spawn_guard',
    status: str | None = None,
) -> dict[str, Any]:
    """Hermes-native execution-control compatibility hook.

    Historical callers wrote spawn execution metadata through the legacy task registry.
    Hermes keeps the same shape but persists the canonical mapping via hermes_team.registry_api.
    """
    return sync_execution_payload(task_id=task_id, payload=payload, note=note, source=source, status=status)
