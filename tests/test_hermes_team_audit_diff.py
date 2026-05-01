from __future__ import annotations

import json

from hermes_team import task_hook
from hermes_team.approval_store import ApprovalStore
from hermes_team.registry_api import configure_registry_store, load_registry, update_mapping_status
from hermes_team.source_bridge import audit_team_state_vs_legacy
from hermes_team.task_store import TaskStore


def _prepare_env(tmp_path, monkeypatch):
    hermes_home = tmp_path / 'hermes-home'
    state_dir = hermes_home / 'state' / 'team'
    state_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv('HERMES_HOME', str(hermes_home))
    configure_registry_store(state_dir)
    task_hook._TASK_STORE = TaskStore(state_dir)
    task_hook._APPROVAL_STORE = ApprovalStore(state_dir)
    return state_dir


def test_audit_team_state_vs_legacy_reports_parity(tmp_path, monkeypatch):
    state_dir = _prepare_env(tmp_path, monkeypatch)

    legacy_edict = tmp_path / 'data' / 'edict'
    legacy_edict.mkdir(parents=True)
    legacy_tasks = [{'id': 'TSK-1', 'title': 'legacy task'}]
    legacy_archive = [{'id': 'TSK-2', 'title': 'legacy done'}]
    legacy_registry = {'tasks': {'TSK-1': {'jobIds': ['job-1']}, 'TSK-2': {'jobIds': []}}}
    legacy_approvals = [{'approval_id': 'APR-1', 'task_id': 'TSK-1', 'scope': {'task_id': 'TSK-1'}}]
    (legacy_edict / 'tasks.json').write_text(json.dumps(legacy_tasks), encoding='utf-8')
    (legacy_edict / 'archive.json').write_text(json.dumps(legacy_archive), encoding='utf-8')
    (legacy_edict / 'task_run_session_registry.json').write_text(json.dumps(legacy_registry), encoding='utf-8')
    (legacy_edict / 'approvals.json').write_text(json.dumps(legacy_approvals), encoding='utf-8')

    TaskStore(state_dir)._save_json(state_dir / 'tasks.json', legacy_tasks)
    TaskStore(state_dir)._save_json(state_dir / 'archive.json', legacy_archive)
    ApprovalStore(state_dir).save(legacy_approvals)
    update_mapping_status('TSK-1', 'scheduled', note='seed', source='test')
    update_mapping_status('TSK-2', 'done', note='seed', source='test')

    report = audit_team_state_vs_legacy(tmp_path)

    assert report['summary']['taskParity'] is True
    assert report['summary']['registryParity'] is True
    assert report['summary']['approvalParity'] is True
    assert report['diff']['missingTaskIdsInHermes'] == []
    assert report['diff']['extraTaskIdsInHermes'] == []


def test_audit_team_state_vs_legacy_reports_missing_items(tmp_path, monkeypatch):
    state_dir = _prepare_env(tmp_path, monkeypatch)

    legacy_edict = tmp_path / 'data' / 'edict'
    legacy_edict.mkdir(parents=True)
    (legacy_edict / 'tasks.json').write_text(json.dumps([{'id': 'TSK-ONLY-LEGACY'}]), encoding='utf-8')
    (legacy_edict / 'archive.json').write_text(json.dumps([]), encoding='utf-8')
    (legacy_edict / 'task_run_session_registry.json').write_text(json.dumps({'tasks': {'TSK-ONLY-LEGACY': {'jobIds': ['job-x']}}}), encoding='utf-8')
    (legacy_edict / 'approvals.json').write_text(json.dumps([{'approval_id': 'APR-X', 'task_id': 'TSK-ONLY-LEGACY'}]), encoding='utf-8')

    TaskStore(state_dir)._save_json(state_dir / 'tasks.json', [{'id': 'TSK-ONLY-HERMES'}])
    TaskStore(state_dir)._save_json(state_dir / 'archive.json', [])
    ApprovalStore(state_dir).save([{'approval_id': 'APR-Y', 'task_id': 'TSK-ONLY-HERMES'}])
    update_mapping_status('TSK-ONLY-HERMES', 'pending', note='seed', source='test')

    report = audit_team_state_vs_legacy(tmp_path)

    assert report['summary']['taskParity'] is False
    assert report['summary']['registryParity'] is False
    assert report['summary']['approvalParity'] is False
    assert report['diff']['missingTaskIdsInHermes'] == ['TSK-ONLY-LEGACY']
    assert report['diff']['extraTaskIdsInHermes'] == ['TSK-ONLY-HERMES']
    assert report['diff']['missingRegistryTaskIdsInHermes'] == ['TSK-ONLY-LEGACY']
    assert report['diff']['extraRegistryTaskIdsInHermes'] == ['TSK-ONLY-HERMES']
    assert report['diff']['missingApprovalTaskIdsInHermes'] == ['TSK-ONLY-LEGACY']
    assert report['diff']['extraApprovalTaskIdsInHermes'] == ['TSK-ONLY-HERMES']


def test_task_hook_audit_legacy_diff_prints_json_report(tmp_path, monkeypatch, capsys):
    state_dir = _prepare_env(tmp_path, monkeypatch)

    legacy_edict = tmp_path / 'data' / 'edict'
    legacy_edict.mkdir(parents=True)
    (legacy_edict / 'tasks.json').write_text(json.dumps([{'id': 'TSK-1'}]), encoding='utf-8')
    (legacy_edict / 'archive.json').write_text(json.dumps([]), encoding='utf-8')
    (legacy_edict / 'task_run_session_registry.json').write_text(json.dumps({'tasks': {'TSK-1': {'jobIds': []}}}), encoding='utf-8')
    (legacy_edict / 'approvals.json').write_text(json.dumps([]), encoding='utf-8')

    TaskStore(state_dir)._save_json(state_dir / 'tasks.json', [{'id': 'TSK-1'}])
    TaskStore(state_dir)._save_json(state_dir / 'archive.json', [])
    update_mapping_status('TSK-1', 'pending', note='seed', source='test')

    task_hook.dispatch(['audit_legacy_diff', str(tmp_path)])
    output = capsys.readouterr().out

    assert 'legacy vs hermes team state audit' in output
    assert '"mode": "read-only-audit"' in output
    assert '"taskparity": true' in output.lower()
    assert load_registry()['tasks']['TSK-1']['lastStatus'] == 'pending'
