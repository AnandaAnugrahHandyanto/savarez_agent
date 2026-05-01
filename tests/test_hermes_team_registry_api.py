from __future__ import annotations

import json
from pathlib import Path

import pytest

from hermes_team.registry_api import bind_mapping, configure_registry_store, load_registry, sync_execution_payload, update_mapping_status


@pytest.fixture()
def configured_registry(tmp_path):
    state_dir = tmp_path / 'state' / 'team'
    configure_registry_store(state_dir)
    return state_dir


def test_registry_api_bind_and_status(configured_registry):
    registry = bind_mapping(
        task_id='TSK-API-1',
        job_id='job-1',
        session_id='sess-1',
        session_key='key-1',
        run_id='run-1',
        note='bound',
        source='pytest',
        status='pending',
    )
    task = registry['tasks']['TSK-API-1']
    assert task['jobIds'] == ['job-1']
    assert task['runIds'] == ['run-1']
    assert task['sessionIds'] == ['sess-1']
    assert task['sessionKeys'] == ['key-1']
    assert task['lastStatus'] == 'pending'

    registry = update_mapping_status('TSK-API-1', 'ready', note='status', source='pytest')
    assert registry['tasks']['TSK-API-1']['lastStatus'] == 'ready'


def test_registry_api_sync_execution_payload(configured_registry):
    sync_execution_payload(
        'TSK-API-2',
        {
            'jobId': 'job-2',
            'sessionId': 'sess-2',
            'sessionKey': 'key-2',
            'runId': 'run-2',
        },
        note='sync',
        source='pytest',
        status='approved',
    )
    data = load_registry()
    task = data['tasks']['TSK-API-2']
    assert task['jobIds'] == ['job-2']
    assert task['runIds'] == ['run-2']
    assert task['sessionIds'] == ['sess-2']
    assert task['sessionKeys'] == ['key-2']
    assert task['lastStatus'] == 'approved'

    on_disk = json.loads((configured_registry / 'task_run_session_registry.json').read_text(encoding='utf-8'))
    assert on_disk['tasks']['TSK-API-2']['lastStatus'] == 'approved'
