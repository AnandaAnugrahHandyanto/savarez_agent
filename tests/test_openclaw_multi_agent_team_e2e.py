from __future__ import annotations

import json

import pytest

from hermes_team import task_hook
from hermes_team.approval_store import ApprovalStore
from hermes_team.registry_api import configure_registry_store, load_registry
from hermes_team.task_store import TaskStore


@pytest.fixture()
def hermes_team_chain_env(tmp_path, monkeypatch):
    monkeypatch.setenv('HERMES_HOME', str(tmp_path))
    state_dir = tmp_path / 'state' / 'team'
    state_dir.mkdir(parents=True, exist_ok=True)
    configure_registry_store(state_dir)
    task_hook._TASK_STORE = TaskStore(state_dir)
    task_hook._APPROVAL_STORE = ApprovalStore(state_dir)
    return state_dir


def test_task_approval_cron_registry_chain_visible_in_list(capsys, hermes_team_chain_env, monkeypatch):
    task = task_hook.create_task('team chain', 'desc')
    task_id = task['id']

    approvals = [
        {
            'approval_id': 'APR-CHAIN-1',
            'task_id': task_id,
            'status': 'approved',
            'created_at': '2026-04-11T12:30:00+08:00',
            'scope': {'task_id': task_id},
        }
    ]
    (hermes_team_chain_env / 'approvals.json').write_text(
        json.dumps(approvals, ensure_ascii=False, indent=2), encoding='utf-8'
    )

    created = {
        'id': 'job-chain-1',
        'schedule_display': '0 13 * * *',
        'deliver': 'feishu:user:test',
    }
    monkeypatch.setattr('hermes_team.task_cron.create_job', lambda **kwargs: created)
    monkeypatch.setattr('hermes_team.task_cron.update_job', lambda *args, **kwargs: None)

    task_hook.dispatch([
        'cron_upsert',
        task_id,
        'chain-job',
        '0 13 * * *',
        '--message', 'hello chain',
        '--channel', 'feishu',
        '--to', 'user:test',
    ])
    capsys.readouterr()

    task_hook.dispatch(['list'])
    output = capsys.readouterr().out
    assert task_id in output
    assert 'approval: approved (APR-CHAIN-1)' in output
    assert 'registry: scheduled' in output
    assert 'link: job=job-chain-1' in output

    registry = load_registry()
    task_link = registry['tasks'][task_id]
    assert task_link['jobIds'] == ['job-chain-1']
    assert task_link['lastStatus'] == 'scheduled'
