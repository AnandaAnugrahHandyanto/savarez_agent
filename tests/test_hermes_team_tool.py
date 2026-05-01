from __future__ import annotations

import json

from hermes_team.approval_store import ApprovalStore
from hermes_team.runner import TeamRunnerResult
from tools.hermes_team_tool import (
    team_approval_audit_tool,
    team_approvals_tool,
    team_approve_tool,
    team_events_tool,
    team_metrics_tool,
    team_replans_tool,
    team_sandbox_audit_tool,
    team_watch_tool,
    team_reject_tool,
    team_roles_tool,
    team_run_task_tool,
    team_status_tool,
)
from tools.registry import registry


def test_team_tool_registration_discovers_core_team_tools():
    expected = {'team_run_task', 'team_status', 'team_events', 'team_roles', 'team_approvals', 'team_approve', 'team_reject', 'team_metrics', 'team_watch', 'team_sandbox_audit', 'team_replans', 'team_approval_audit', 'team_templates'}
    assert expected <= set(registry.get_all_tool_names())
    assert registry.get_toolset_for_tool('team_run_task') == 'team'


def test_team_roles_tool_lists_default_roles():
    payload = json.loads(team_roles_tool({}))
    names = {role['name'] for role in payload['roles']}
    assert {'cio', 'planner', 'executor', 'reviewer', 'risk_officer'} <= names


def test_team_run_status_and_events_tools_use_persistent_state(tmp_path, monkeypatch):
    monkeypatch.setenv('HERMES_HOME', str(tmp_path))

    def fake_run_role(self, role, goal, context='', task_id=None, run_id=None):
        return TeamRunnerResult(
            status='completed',
            summary=f'{role.name} ok',
            session_id=f'sess-{role.name}',
            raw={'usage': {'estimated_cost_usd': 0.01}},
        )

    monkeypatch.setattr('hermes_team.runner.TeamRunner.run_role', fake_run_role)

    # Use an explicit task_id so the state remains deterministic and avoids relying on live task creation.
    result_payload = json.loads(team_run_task_tool({
        'goal': 'verify tool entrypoint',
        'task_id': 'TSK-TOOL-1',
        'roles': ['executor'],
        'context': 'test context',
        'require_review': True,
    }))

    assert result_payload['ok'] is True
    result = result_payload['result']
    assert result['task_id'] == 'TSK-TOOL-1'
    assert [step['role'] for step in result['steps']] == ['executor', 'reviewer']

    status_payload = json.loads(team_status_tool({'run_id': result['run_id']}))
    assert status_payload['ok'] is True
    assert status_payload['run']['status'] == 'completed'

    events_payload = json.loads(team_events_tool({'task_id': 'TSK-TOOL-1'}))
    event_names = [event['event'] for event in events_payload['events']]
    assert 'team.run_started' in event_names
    assert 'team.completed' in event_names

    metrics_payload = json.loads(team_metrics_tool({}))
    assert metrics_payload['ok'] is True
    assert metrics_payload['metrics']['snapshot']['total_runs'] == 1
    assert metrics_payload['metrics']['snapshot']['registry_tasks'] >= 1
    assert metrics_payload['metrics']['snapshot']['total_duration_ms'] >= 0
    assert metrics_payload['metrics']['snapshot']['total_estimated_cost_usd'] == 0.02
    assert metrics_payload['metrics']['snapshot']['estimated_cost_by_role_usd']['executor'] == 0.01

    watch_payload = json.loads(team_watch_tool({'run_id': result['run_id']}))
    assert watch_payload['ok'] is True
    assert watch_payload['watch']['status'] == 'completed'

    sandbox_payload = json.loads(team_sandbox_audit_tool({'run_id': result['run_id']}))
    assert sandbox_payload['ok'] is True
    assert sandbox_payload['count'] >= 2
    assert all('policy' in record for record in sandbox_payload['records'])

    replans_payload = json.loads(team_replans_tool({'run_id': result['run_id']}))
    assert replans_payload['ok'] is True
    assert replans_payload['count'] == 0


def test_team_approval_tools_can_list_approve_and_reject(tmp_path, monkeypatch):
    monkeypatch.setenv('HERMES_HOME', str(tmp_path))
    store = ApprovalStore()
    store.upsert({
        'approval_id': 'apr-tool-1',
        'status': 'pending',
        'scope': {'task_id': 'TSK-APR', 'run_id': 'run-apr', 'role': 'executor'},
        'reason': 'test pending approval',
    })
    store.upsert({
        'approval_id': 'apr-tool-2',
        'status': 'pending',
        'scope': {'task_id': 'TSK-APR', 'run_id': 'run-apr', 'role': 'reviewer'},
        'reason': 'test reject approval',
    })

    listed = json.loads(team_approvals_tool({'status': 'pending'}))
    assert listed['count'] == 2

    approved = json.loads(team_approve_tool({'approval_id': 'apr-tool-1', 'reason': '主人批准'}))
    assert approved['ok'] is True
    assert approved['approval']['status'] == 'approved'

    rejected = json.loads(team_reject_tool({'approval_id': 'apr-tool-2', 'reason': 'scope too broad'}))
    assert rejected['ok'] is True
    assert rejected['approval']['status'] == 'rejected'

    events = json.loads(team_events_tool({'task_id': 'TSK-APR'}))['events']
    assert [event['event'] for event in events] == ['team.approval_approved', 'team.approval_rejected']

    audit = json.loads(team_approval_audit_tool({}))
    assert audit['ok'] is True
    assert audit['audit']['by_status']['approved'] == 1
    assert audit['audit']['by_status']['rejected'] == 1
