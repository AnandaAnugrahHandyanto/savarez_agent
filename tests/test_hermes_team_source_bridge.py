from __future__ import annotations

import json

import pytest

from hermes_team.registry_api import configure_registry_store, load_registry
from hermes_team.source_bridge import (
    _registry_needs_bootstrap,
    backfill_team_state_from_legacy,
    bootstrap_team_state_from_legacy,
    legacy_bootstrap_enabled,
)


def test_registry_needs_bootstrap_accepts_new_and_legacy_empty_shapes():
    assert _registry_needs_bootstrap({'tasks': {}}) is True
    assert _registry_needs_bootstrap({'mappings': []}) is True
    assert _registry_needs_bootstrap({}) is True


def test_registry_needs_bootstrap_rejects_populated_new_and_legacy_shapes():
    assert _registry_needs_bootstrap({'tasks': {'TSK-1': {'jobIds': ['job-1']}}}) is False
    assert _registry_needs_bootstrap({'mappings': [{'taskId': 'TSK-1'}]}) is False


def test_legacy_bootstrap_disabled_by_default(monkeypatch, tmp_path):
    monkeypatch.delenv('HERMES_ENABLE_OPENCLAW_TEAM_BOOTSTRAP', raising=False)

    with pytest.raises(RuntimeError, match='disabled by default'):
        bootstrap_team_state_from_legacy(tmp_path)

    assert legacy_bootstrap_enabled() is False


def test_configured_registry_persists_new_shape(tmp_path):
    state_dir = tmp_path / 'state' / 'team'
    configure_registry_store(state_dir)

    registry = load_registry()
    assert registry == {'tasks': {}}

    on_disk = json.loads((state_dir / 'task_run_session_registry.json').read_text(encoding='utf-8')) if (state_dir / 'task_run_session_registry.json').exists() else {'tasks': {}}
    assert on_disk == {'tasks': {}}


def test_bootstrap_ignores_malformed_legacy_json(monkeypatch, tmp_path):
    monkeypatch.setenv('HERMES_ENABLE_OPENCLAW_TEAM_BOOTSTRAP', '1')
    monkeypatch.setenv('HERMES_HOME', str(tmp_path / 'hermes-home'))

    legacy_edict = tmp_path / 'data' / 'edict'
    legacy_edict.mkdir(parents=True)
    (legacy_edict / 'tasks.json').write_text('{not-json', encoding='utf-8')
    (legacy_edict / 'archive.json').write_text('[{"id": "ARCH-1"}]', encoding='utf-8')
    (legacy_edict / 'task_run_session_registry.json').write_text('{"mappings": []}', encoding='utf-8')

    result = bootstrap_team_state_from_legacy(tmp_path)

    assert result['taskCounts'] == {'active': 0, 'archived': 1}


def test_backfill_team_state_from_legacy_merges_missing_items(monkeypatch, tmp_path):
    hermes_home = tmp_path / 'hermes-home'
    monkeypatch.setenv('HERMES_HOME', str(hermes_home))
    state_dir = hermes_home / 'state' / 'team'
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / 'tasks.json').write_text(json.dumps([{'id': 'HERMES-1', 'state': 'pending'}]), encoding='utf-8')
    (state_dir / 'archive.json').write_text(json.dumps([]), encoding='utf-8')
    (state_dir / 'task_run_session_registry.json').write_text(json.dumps({'tasks': {'HERMES-1': {'jobIds': ['job-h']}}}), encoding='utf-8')
    (state_dir / 'approvals.json').write_text(json.dumps([{'approval_id': 'APR-H', 'task_id': 'HERMES-1', 'status': 'approved', 'scope': {'task_id': 'HERMES-1'}}]), encoding='utf-8')

    legacy_root = tmp_path / 'legacy-root'
    legacy_edict = legacy_root / 'data' / 'edict'
    legacy_edict.mkdir(parents=True, exist_ok=True)
    (legacy_edict / 'tasks.json').write_text(json.dumps([{'id': 'LEGACY-1', 'state': 'pending'}]), encoding='utf-8')
    (legacy_edict / 'archive.json').write_text(json.dumps([{'id': 'LEGACY-ARCH', 'state': 'done'}]), encoding='utf-8')
    (legacy_edict / 'task_run_session_registry.json').write_text(json.dumps({'tasks': {'LEGACY-1': {'jobIds': ['job-1']}}}), encoding='utf-8')
    approvals_dir = legacy_root / 'data' / 'approvals'
    approvals_dir.mkdir(parents=True, exist_ok=True)
    (approvals_dir / 'approvals.json').write_text(json.dumps([{'approval_id': 'APR-L', 'task_id': 'LEGACY-1', 'status': 'approved', 'scope': {'task_id': 'LEGACY-1'}}]), encoding='utf-8')

    result = backfill_team_state_from_legacy(legacy_root)

    assert result['tasksAdded'] == 1
    assert result['archiveAdded'] == 1
    assert result['registryTasksAdded'] == 1
    assert result['approvalsAdded'] == 1
    merged_tasks = json.loads((state_dir / 'tasks.json').read_text(encoding='utf-8'))
    merged_archive = json.loads((state_dir / 'archive.json').read_text(encoding='utf-8'))
    merged_registry = json.loads((state_dir / 'task_run_session_registry.json').read_text(encoding='utf-8'))
    merged_approvals = json.loads((state_dir / 'approvals.json').read_text(encoding='utf-8'))
    assert {item['id'] for item in merged_tasks} == {'HERMES-1', 'LEGACY-1'}
    assert {item['id'] for item in merged_archive} == {'LEGACY-ARCH'}
    assert set((merged_registry.get('tasks') or {}).keys()) == {'HERMES-1', 'LEGACY-1'}
    assert {item['approval_id'] for item in merged_approvals} == {'APR-H', 'APR-L'}
