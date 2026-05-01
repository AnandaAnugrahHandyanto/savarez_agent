from __future__ import annotations

import json
import pytest

from hermes_team import task_hook, JsonStateStore
from hermes_team.registry_api import configure_registry_store, load_registry
from hermes_team.task_store import TaskStore


@pytest.fixture
def hermes_team_env(tmp_path, monkeypatch):
    monkeypatch.setenv('HERMES_HOME', str(tmp_path))
    state_dir = tmp_path / 'state' / 'team'
    state_dir.mkdir(parents=True, exist_ok=True)
    configure_registry_store(state_dir)
    task_hook._TASK_STORE = TaskStore(state_dir)
    task_hook._APPROVAL_STORE = task_hook.ApprovalStore(state_dir)
    return state_dir


def test_task_hook_cron_upsert_dry_run_uses_hermes_native(capsys, hermes_team_env):
    task = task_hook.create_task('cron dry run', 'desc')

    task_hook.dispatch([
        'cron_upsert',
        task['id'],
        'audit-job',
        '0 9 * * *',
        '--message', 'hello',
        '--channel', 'feishu',
        '--to', 'user:test',
        '--dry-run',
    ])

    output = capsys.readouterr().out
    assert 'cron_upsert dry-run' in output
    assert 'openclaw' not in output.lower()
    registry = load_registry()
    assert registry.get('tasks', {}).get(task['id']) is None



def test_task_hook_cron_upsert_gray_preview(capsys, hermes_team_env):
    task = task_hook.create_task('cron gray run', 'desc')

    task_hook.dispatch([
        'cron_upsert_gray',
        task['id'],
        'gray-job',
        '0 10 * * *',
        '--system-event', 'ping',
    ])

    output = capsys.readouterr().out
    assert 'cron_upsert gray' in output
    assert 'preview:' in output
    assert 'openclaw' not in output.lower()



def test_task_hook_cron_upsert_creates_job_and_registry(capsys, hermes_team_env, monkeypatch):
    task = task_hook.create_task('cron live run', 'desc')

    created = {
        'id': 'job-123',
        'schedule_display': '0 11 * * *',
        'deliver': 'feishu:user:test',
    }

    monkeypatch.setattr('hermes_team.task_cron.create_job', lambda **kwargs: created)
    monkeypatch.setattr('hermes_team.task_cron.update_job', lambda *args, **kwargs: None)

    task_hook.dispatch([
        'cron_upsert',
        task['id'],
        'live-job',
        '0 11 * * *',
        '--message', 'go',
        '--channel', 'feishu',
        '--to', 'user:test',
    ])

    output = capsys.readouterr().out
    assert 'cron_upsert created' in output
    assert 'job=job-123' in output
    registry = load_registry()
    task_link = registry.get('tasks', {}).get(task['id']) or {}
    assert task_link.get('jobIds') == ['job-123']
    assert task_link.get('lastStatus') == 'scheduled'



def test_task_hook_cron_upsert_updates_existing_job(capsys, hermes_team_env, monkeypatch):
    task = task_hook.create_task('cron update run', 'desc')
    task_hook.bind_mapping(task['id'], job_id='job-existing', note='seed', source='test')

    updated = {
        'id': 'job-existing',
        'schedule_display': '0 12 * * *',
        'deliver': 'feishu:user:test',
    }

    monkeypatch.setattr('hermes_team.task_cron.create_job', lambda **kwargs: (_ for _ in ()).throw(AssertionError('should not create')))
    monkeypatch.setattr('hermes_team.task_cron.update_job', lambda job_id, payload: updated if job_id == 'job-existing' else None)

    task_hook.dispatch([
        'cron_upsert',
        task['id'],
        'live-job',
        '0 12 * * *',
        '--message', 'updated',
        '--channel', 'feishu',
        '--to', 'user:test',
    ])

    output = capsys.readouterr().out
    assert 'cron_upsert updated' in output
    assert 'job=job-existing' in output
    registry = load_registry()
    task_link = registry.get('tasks', {}).get(task['id']) or {}
    assert task_link.get('jobIds') == ['job-existing']
    assert task_link.get('lastStatus') == 'scheduled'
    assert len(task_link.get('notes') or []) >= 2


def test_create_task_avoids_duplicate_ids_within_same_second(hermes_team_env, monkeypatch):
    class FrozenDateTime:
        @staticmethod
        def now(_tz):
            from datetime import datetime
            return datetime(2026, 4, 11, 16, 11, 43, tzinfo=task_hook.TZ)

    monkeypatch.setattr(task_hook, 'datetime', FrozenDateTime)

    first = task_hook.create_task('first', 'desc')
    second = task_hook.create_task('second', 'desc')
    third = task_hook.create_task('third', 'desc')

    assert first['id'] == 'TSK-20260411-161143'
    assert second['id'] == 'TSK-20260411-161143-01'
    assert third['id'] == 'TSK-20260411-161143-02'


def test_shared_json_store_clones_defaults_between_reads(tmp_path):
    store = JsonStateStore(tmp_path)
    path = tmp_path / 'missing.json'

    first = store._load_json(path, [])
    first.append('mutated')
    second = store._load_json(path, [])

    assert second == []
