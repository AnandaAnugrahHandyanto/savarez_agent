from __future__ import annotations

from typing import Any, Dict, List, Optional

from hermes_team.approval_store import ApprovalStore
from hermes_team.paths import ensure_team_state_dir

_HERMES_APPROVAL_STORE: ApprovalStore | None = None


def _get_hermes_approval_store() -> ApprovalStore:
    global _HERMES_APPROVAL_STORE
    state_dir = ensure_team_state_dir()
    if _HERMES_APPROVAL_STORE is None or _HERMES_APPROVAL_STORE.path.parent != state_dir:
        _HERMES_APPROVAL_STORE = ApprovalStore(state_dir)
    return _HERMES_APPROVAL_STORE


def list_execution_control_approvals() -> List[Dict[str, Any]]:
    """Legacy compatibility hook.

    Hermes no longer depends on the old execution_control package, but tests and
    migrated callers still import this module. Keep the hook overridable so tests
    can inject legacy data without requiring the old package.
    """
    return []


def _list_legacy_approvals() -> List[Dict[str, Any]]:
    try:
        return list_execution_control_approvals() or []
    except Exception:
        return []


def list_compat_approvals() -> List[Dict[str, Any]]:
    hermes_items = _get_hermes_approval_store().list_approvals() or []
    legacy_items = _list_legacy_approvals()
    combined = list(hermes_items) + [item for item in legacy_items if item not in hermes_items]
    return sorted(
        combined,
        key=lambda item: str(item.get("created_at") or ""),
        reverse=True,
    )


def find_compat_task_approval(task_id: str) -> Optional[Dict[str, Any]]:
    if not task_id:
        return None
    for item in list_compat_approvals():
        if item.get("task_id") == task_id:
            return item
        scope = item.get("scope") or {}
        if isinstance(scope, dict) and scope.get("task_id") == task_id:
            return item
    return None
