from __future__ import annotations

import json
import sys
from pathlib import Path

from hermes_team.registry_api import configure_registry_store, load_registry

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.execution_control import shadow_spawn, spawn_guard


def test_spawn_guard_records_execution_payload_in_hermes_registry(tmp_path, monkeypatch):
    monkeypatch.setenv('HERMES_HOME', str(tmp_path))
    state_dir = tmp_path / 'state' / 'team'
    state_dir.mkdir(parents=True, exist_ok=True)
    configure_registry_store(state_dir)

    registry = spawn_guard.record_spawn_execution(
        'TSK-SPAWN',
        {
            'jobId': 'job-1',
            'runId': 'run-1',
            'sessionId': 'sess-1',
            'sessionKey': 'key-1',
        },
        note='spawned from pytest',
        source='pytest.spawn_guard',
        status='executing',
    )

    entry = registry['tasks']['TSK-SPAWN']
    assert entry['jobIds'] == ['job-1']
    assert entry['runIds'] == ['run-1']
    assert entry['lastStatus'] == 'executing'
    on_disk = json.loads((state_dir / 'task_run_session_registry.json').read_text(encoding='utf-8'))
    assert on_disk['tasks']['TSK-SPAWN']['sessionIds'] == ['sess-1']


def test_shadow_spawn_updates_mapping_status_in_hermes_registry(tmp_path, monkeypatch):
    monkeypatch.setenv('HERMES_HOME', str(tmp_path))
    state_dir = tmp_path / 'state' / 'team'
    state_dir.mkdir(parents=True, exist_ok=True)
    configure_registry_store(state_dir)
    spawn_guard.record_spawn_execution('TSK-SHADOW', {'jobId': 'job-shadow'}, status='queued')

    shadow_spawn.mark_shadow_status('TSK-SHADOW', 'shadow-running', note='shadow started', source='pytest.shadow')

    registry = load_registry()
    assert registry['tasks']['TSK-SHADOW']['lastStatus'] == 'shadow-running'
    notes = registry['tasks']['TSK-SHADOW']['notes']
    assert notes[-1]['source'] == 'pytest.shadow'
    assert notes[-1]['note'] == 'shadow started'
