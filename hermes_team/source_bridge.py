from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .approval_store import ApprovalStore
from .paths import ensure_team_state_dir
from .registry_store import RegistryStore
from .task_store import TaskStore


def _merge_rows_by_key(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
    *,
    key: str,
) -> tuple[list[dict[str, Any]], int]:
    merged = list(existing)
    seen = {str(item.get(key) or '') for item in existing if item.get(key)}
    added = 0
    for item in incoming:
        item_key = str(item.get(key) or '')
        if not item_key or item_key in seen:
            continue
        merged.append(item)
        seen.add(item_key)
        added += 1
    return merged, added


def _approval_task_ids(rows: list[dict[str, Any]]) -> set[str]:
    ids: set[str] = set()
    for row in rows:
        scope = row.get('scope') or {}
        task_id = scope.get('task_id') or row.get('task_id')
        if task_id:
            ids.add(str(task_id))
    return ids


LEGACY_REGISTRY_EMPTY = {'mappings': []}
_BOOTSTRAP_ENV_FLAG = 'HERMES_ENABLE_OPENCLAW_TEAM_BOOTSTRAP'


def _registry_needs_bootstrap(data: dict[str, Any]) -> bool:
    if not isinstance(data, dict):
        return True
    tasks = data.get('tasks')
    if isinstance(tasks, dict):
        return len(tasks) == 0
    mappings = data.get('mappings')
    if isinstance(mappings, list):
        return len(mappings) == 0
    return True


def legacy_bootstrap_enabled() -> bool:
    return os.getenv(_BOOTSTRAP_ENV_FLAG, '').strip().lower() in {'1', 'true', 'yes', 'on'}


class LegacyOpenClawBridge:
    """Read-only adapter for historical team task/approval/registry data.

    This bridge exists only for explicit migration/bootstrap and audit comparison.
    Hermes-native code should not write to these locations.
    """

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root
        self.edict_dir = workspace_root / 'data' / 'edict'

    def _load_json(self, path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            return default

    def read_tasks(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        active = self._load_json(self.edict_dir / 'tasks.json', [])
        archived = self._load_json(self.edict_dir / 'archive.json', [])
        return (
            active if isinstance(active, list) else [],
            archived if isinstance(archived, list) else [],
        )

    def read_registry(self) -> dict[str, Any]:
        data = self._load_json(self.edict_dir / 'task_run_session_registry.json', LEGACY_REGISTRY_EMPTY)
        return data if isinstance(data, dict) else dict(LEGACY_REGISTRY_EMPTY)

    def read_approvals(self) -> list[dict[str, Any]]:
        candidates = [
            self.workspace_root / 'data' / 'approvals' / 'approvals.json',
            self.workspace_root / 'data' / 'execution_control' / 'approvals.json',
            self.workspace_root / 'data' / 'edict' / 'approvals.json',
        ]
        for path in candidates:
            data = self._load_json(path, None)
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                for key in ('approvals', 'items', 'data'):
                    value = data.get(key)
                    if isinstance(value, list):
                        return value
        return []


def bootstrap_team_state_from_legacy(workspace_root: Path) -> dict[str, Any]:
    """[P5] Keep legacy bootstrap resilient to malformed legacy JSON without widening exception handling."""
    if not legacy_bootstrap_enabled():
        raise RuntimeError(
            'Historical team bootstrap is disabled by default. '
            f'Set {_BOOTSTRAP_ENV_FLAG}=1 only for explicit migration/audit runs.'
        )

    bridge = LegacyOpenClawBridge(workspace_root)
    task_store = TaskStore(ensure_team_state_dir())
    registry_store = RegistryStore(ensure_team_state_dir())
    approval_store = ApprovalStore(ensure_team_state_dir())

    active, archived = bridge.read_tasks()
    task_counts = task_store.bootstrap_if_empty(active, archived)

    current_registry = registry_store.load()
    if _registry_needs_bootstrap(current_registry):
        registry_store.save(bridge.read_registry())
    if approval_store.list_approvals() == []:
        approval_store.save(bridge.read_approvals())

    return {
        'taskCounts': task_counts,
        'registryTasks': len((registry_store.load().get('tasks') or {})),
        'registryMappings': len((registry_store.load().get('mappings') or [])),
        'approvals': len(approval_store.list_approvals()),
        'mode': 'explicit-migration-bootstrap',
        'bootstrapEnabled': True,
    }


def backfill_team_state_from_legacy(workspace_root: Path) -> dict[str, Any]:
    """Merge missing legacy team state into Hermes without overwriting Hermes-owned rows."""
    bridge = LegacyOpenClawBridge(workspace_root)
    state_dir = ensure_team_state_dir()
    task_store = TaskStore(state_dir)
    registry_store = RegistryStore(state_dir)
    approval_store = ApprovalStore(state_dir)

    legacy_active, legacy_archived = bridge.read_tasks()
    legacy_registry = bridge.read_registry()
    legacy_approvals = bridge.read_approvals()

    hermes_active = task_store.list_tasks()
    hermes_archived = task_store.list_archive()
    merged_active, tasks_added = _merge_rows_by_key(hermes_active, legacy_active, key='id')
    merged_archive, archive_added = _merge_rows_by_key(hermes_archived, legacy_archived, key='id')
    if tasks_added:
        task_store._save_json(task_store.tasks_path, merged_active)
    if archive_added:
        task_store._save_json(task_store.archive_path, merged_archive)

    registry = registry_store.load()
    registry_tasks = registry.get('tasks') or {}
    if not isinstance(registry_tasks, dict):
        registry_tasks = {}
    legacy_registry_tasks = legacy_registry.get('tasks') or {}
    if not isinstance(legacy_registry_tasks, dict):
        legacy_registry_tasks = {}
    registry_added = 0
    for task_id, payload in legacy_registry_tasks.items():
        if task_id in registry_tasks:
            continue
        registry_tasks[task_id] = payload
        registry_added += 1
    if registry_added:
        registry['tasks'] = registry_tasks
        registry_store.save(registry)

    merged_approvals, approvals_added = _merge_rows_by_key(
        approval_store.list_approvals(),
        legacy_approvals,
        key='approval_id',
    )
    if approvals_added:
        approval_store.save(merged_approvals)

    return {
        'mode': 'merge-missing-from-legacy',
        'tasksAdded': tasks_added,
        'archiveAdded': archive_added,
        'registryTasksAdded': registry_added,
        'approvalsAdded': approvals_added,
    }


def audit_team_state_vs_legacy(workspace_root: Path) -> dict[str, Any]:
    """Read-only comparison between legacy OpenClaw team state and Hermes-native team state."""
    bridge = LegacyOpenClawBridge(workspace_root)
    task_store = TaskStore(ensure_team_state_dir())
    registry_store = RegistryStore(ensure_team_state_dir())
    approval_store = ApprovalStore(ensure_team_state_dir())

    legacy_active, legacy_archived = bridge.read_tasks()
    legacy_registry = bridge.read_registry()
    legacy_approvals = bridge.read_approvals()

    hermes_active = task_store.list_tasks()
    hermes_archived = task_store.list_archive()
    hermes_registry = registry_store.load()
    hermes_approvals = approval_store.list_approvals()

    legacy_task_ids = {str(item.get('id') or '') for item in [*legacy_active, *legacy_archived] if item.get('id')}
    hermes_task_ids = {str(item.get('id') or '') for item in [*hermes_active, *hermes_archived] if item.get('id')}

    legacy_registry_tasks = legacy_registry.get('tasks') or {}
    if not isinstance(legacy_registry_tasks, dict):
        legacy_registry_tasks = {}
    legacy_registry_mappings = legacy_registry.get('mappings') or []
    if not isinstance(legacy_registry_mappings, list):
        legacy_registry_mappings = []

    hermes_registry_tasks = hermes_registry.get('tasks') or {}
    if not isinstance(hermes_registry_tasks, dict):
        hermes_registry_tasks = {}

    legacy_approval_task_ids = _approval_task_ids(legacy_approvals)
    hermes_approval_task_ids = _approval_task_ids(hermes_approvals)

    legacy_registry_task_ids = sorted(legacy_registry_tasks.keys())
    hermes_registry_task_ids = sorted(hermes_registry_tasks.keys())
    missing_in_hermes = sorted(legacy_task_ids - hermes_task_ids)
    extra_in_hermes = sorted(hermes_task_ids - legacy_task_ids)

    return {
        'mode': 'read-only-audit',
        'legacy': {
            'activeTasks': len(legacy_active),
            'archivedTasks': len(legacy_archived),
            'taskIds': sorted(legacy_task_ids),
            'registryTasks': len(legacy_registry_tasks),
            'registryMappings': len(legacy_registry_mappings),
            'registryTaskIds': legacy_registry_task_ids,
            'approvals': len(legacy_approvals),
            'approvalTaskIds': sorted(legacy_approval_task_ids),
        },
        'hermes': {
            'activeTasks': len(hermes_active),
            'archivedTasks': len(hermes_archived),
            'taskIds': sorted(hermes_task_ids),
            'registryTasks': len(hermes_registry_tasks),
            'registryMappings': len((hermes_registry.get('mappings') or [])) if isinstance(hermes_registry.get('mappings'), list) else 0,
            'registryTaskIds': hermes_registry_task_ids,
            'approvals': len(hermes_approvals),
            'approvalTaskIds': sorted(hermes_approval_task_ids),
        },
        'diff': {
            'missingTaskIdsInHermes': missing_in_hermes,
            'extraTaskIdsInHermes': extra_in_hermes,
            'missingRegistryTaskIdsInHermes': sorted(set(legacy_registry_task_ids) - set(hermes_registry_task_ids)),
            'extraRegistryTaskIdsInHermes': sorted(set(hermes_registry_task_ids) - set(legacy_registry_task_ids)),
            'missingApprovalTaskIdsInHermes': sorted(legacy_approval_task_ids - hermes_approval_task_ids),
            'extraApprovalTaskIdsInHermes': sorted(hermes_approval_task_ids - legacy_approval_task_ids),
        },
        'summary': {
            'taskParity': missing_in_hermes == [] and extra_in_hermes == [],
            'registryParity': sorted(set(legacy_registry_task_ids)) == sorted(set(hermes_registry_task_ids)),
            'approvalParity': sorted(legacy_approval_task_ids) == sorted(hermes_approval_task_ids),
        },
    }
