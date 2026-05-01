from __future__ import annotations

import json
from pathlib import Path

import pytest

from hermes_team.approval_store import ApprovalStore

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.execution_control import approval_read_compat


@pytest.fixture()
def approval_env(tmp_path, monkeypatch):
    state_dir = tmp_path / 'state' / 'team'
    monkeypatch.setenv('HERMES_HOME', str(tmp_path))
    store = ApprovalStore(state_dir)
    monkeypatch.setattr(approval_read_compat, '_HERMES_APPROVAL_STORE', store)
    monkeypatch.setattr(approval_read_compat, '_list_legacy_approvals', lambda: [{'approval_id': 'legacy-1', 'task_id': 'TSK-LEGACY', 'status': 'pending'}])
    monkeypatch.setattr(approval_read_compat, 'list_execution_control_approvals', lambda: [])
    return store, state_dir


def test_compat_approvals_prefers_hermes_store(approval_env):
    store, _ = approval_env
    store.save([
        {
            'approval_id': 'hermes-1',
            'task_id': 'TSK-HERMES',
            'status': 'approved',
            'created_at': '2026-04-11T12:00:00+08:00',
            'scope': {'task_id': 'TSK-HERMES'},
        }
    ])

    approvals = approval_read_compat.list_compat_approvals()
    assert approvals[0]['approval_id'] == 'hermes-1'
    assert any(item['approval_id'] == 'legacy-1' for item in approvals)


def test_compat_find_task_approval_reads_hermes_store(approval_env):
    store, _ = approval_env
    store.save([
        {
            'approval_id': 'hermes-2',
            'task_id': 'TSK-H2',
            'status': 'approved',
            'created_at': '2026-04-11T12:30:00+08:00',
            'scope': {'task_id': 'TSK-H2'},
        }
    ])

    latest = approval_read_compat.find_compat_task_approval('TSK-H2')
    assert latest is not None
    assert latest['approval_id'] == 'hermes-2'


def test_compat_store_resolves_from_hermes_home(monkeypatch, tmp_path):
    monkeypatch.setenv('HERMES_HOME', str(tmp_path))
    approval_read_compat._HERMES_APPROVAL_STORE = None

    store = approval_read_compat._get_hermes_approval_store()

    assert store.path == tmp_path / 'state' / 'team' / 'approvals.json'
