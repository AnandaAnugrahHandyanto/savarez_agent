from __future__ import annotations

from hermes_team.registry_api import update_mapping_status

__all__ = ['update_mapping_status']


def mark_shadow_status(
    task_id: str,
    status: str,
    *,
    note: str = '',
    source: str = 'execution_control.shadow_spawn',
) -> dict:
    """Hermes-native shadow-spawn compatibility hook.

    Keeps the minimal legacy contract while writing status updates into the Hermes team registry.
    """
    return update_mapping_status(task_id=task_id, status=status, note=note, source=source)
