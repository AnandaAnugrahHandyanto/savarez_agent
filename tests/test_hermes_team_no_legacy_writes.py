from __future__ import annotations

import json

from hermes_team import task_hook
from hermes_team.registry_api import configure_registry_store, load_registry, update_mapping_status


def _prepare_isolated_team_env(tmp_path, monkeypatch):
    hermes_home = tmp_path / 'hermes-home'
    state_dir = hermes_home / 'state' / 'team'
    state_dir.mkdir(parents=True)

    legacy_root = tmp_path / 'openclaw-runtime'
    legacy_edict = legacy_root / 'data' / 'edict'
    legacy_edict.mkdir(parents=True)
    (legacy_edict / 'tasks.json').write_text(json.dumps([{'id': 'LEGACY-1'}]), encoding='utf-8')
    (legacy_edict / 'archive.json').write_text(json.dumps([{'id': 'LEGACY-A'}]), encoding='utf-8')
    (legacy_edict / 'task_run_session_registry.json').write_text(json.dumps({'mappings': [{'taskId': 'LEGACY-1'}]}), encoding='utf-8')

    monkeypatch.setenv('HERMES_HOME', str(hermes_home))
    configure_registry_store(state_dir)
    monkeypatch.setattr(task_hook, '_TASK_STORE', task_hook.TaskStore(state_dir))
    monkeypatch.setattr(task_hook, '_APPROVAL_STORE', task_hook.ApprovalStore(state_dir))
    return state_dir, legacy_edict


def test_task_hook_writes_only_to_hermes_state(tmp_path, monkeypatch):
    state_dir, legacy_edict = _prepare_isolated_team_env(tmp_path, monkeypatch)

    task = task_hook.create_task('native write only', 'desc')

    current_tasks = json.loads((state_dir / 'tasks.json').read_text(encoding='utf-8'))
    assert any(item['id'] == task['id'] for item in current_tasks)

    legacy_tasks = json.loads((legacy_edict / 'tasks.json').read_text(encoding='utf-8'))
    assert legacy_tasks == [{'id': 'LEGACY-1'}]

    registry = load_registry()
    assert registry == {'tasks': {}}
    legacy_registry = json.loads((legacy_edict / 'task_run_session_registry.json').read_text(encoding='utf-8'))
    assert legacy_registry == {'mappings': [{'taskId': 'LEGACY-1'}]}


def test_registry_update_does_not_touch_legacy_registry(tmp_path, monkeypatch):
    state_dir, legacy_edict = _prepare_isolated_team_env(tmp_path, monkeypatch)

    update_mapping_status('TSK-NATIVE-1', 'scheduled', note='native update', source='pytest')

    native_registry = json.loads((state_dir / 'task_run_session_registry.json').read_text(encoding='utf-8'))
    assert native_registry['tasks']['TSK-NATIVE-1']['lastStatus'] == 'scheduled'

    legacy_registry = json.loads((legacy_edict / 'task_run_session_registry.json').read_text(encoding='utf-8'))
    assert legacy_registry == {'mappings': [{'taskId': 'LEGACY-1'}]}


def test_cron_upsert_does_not_touch_legacy_registry(tmp_path, monkeypatch, capsys):
    state_dir, legacy_edict = _prepare_isolated_team_env(tmp_path, monkeypatch)

    task = task_hook.create_task('cron isolated', 'desc')
    created = {
        'id': 'job-native-1',
        'schedule_display': '*/5 * * * *',
        'deliver': 'feishu',
    }
    monkeypatch.setattr('hermes_team.task_cron.create_job', lambda **kwargs: created)
    monkeypatch.setattr('hermes_team.task_cron.update_job', lambda *args, **kwargs: None)

    task_hook.dispatch([
        'cron_upsert',
        task['id'],
        'native-job',
        '*/5 * * * *',
        '--message',
        'hello',
    ])

    output = capsys.readouterr().out
    assert 'cron_upsert created' in output

    native_registry = load_registry()
    assert native_registry['tasks'][task['id']]['jobIds'] == ['job-native-1']

    legacy_registry = json.loads((legacy_edict / 'task_run_session_registry.json').read_text(encoding='utf-8'))
    assert legacy_registry == {'mappings': [{'taskId': 'LEGACY-1'}]}

    legacy_tasks = json.loads((legacy_edict / 'tasks.json').read_text(encoding='utf-8'))
    assert legacy_tasks == [{'id': 'LEGACY-1'}]
