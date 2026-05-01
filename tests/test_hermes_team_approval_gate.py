from __future__ import annotations

from hermes_team.approval_store import ApprovalStore
from hermes_team.dispatcher import DispatchRequest, TeamDispatcher
from hermes_team.messages import TeamEventStore
from hermes_team.registry_store import RegistryStore
from hermes_team.runner import TeamRunner, TeamRunnerResult


def test_dispatcher_blocks_dangerous_external_action_and_records_pending_approval(tmp_path):
    called = {'runner': False}

    def fake_executor(role, goal, context, task_id, run_id):
        called['runner'] = True
        return TeamRunnerResult(status='completed', summary='should not run')

    dispatcher = TeamDispatcher(
        runner=TeamRunner(executor=fake_executor),
        registry_store=RegistryStore(tmp_path),
        event_store=TeamEventStore(tmp_path),
    )

    result = dispatcher.dispatch(DispatchRequest(
        task_id='TSK-APPROVAL',
        run_id='run-approval',
        role='executor',
        goal='send webhook to external production system',
        toolsets=['terminal', 'file'],
    ))

    assert result.status == 'approval_pending'
    assert result.raw['required'] is True
    assert called['runner'] is False
    approvals = ApprovalStore(tmp_path).list_approvals()
    assert approvals[0]['status'] == 'pending'
    assert approvals[0]['scope']['task_id'] == 'TSK-APPROVAL'
    events = TeamEventStore(tmp_path).list(task_id='TSK-APPROVAL')
    assert [event['event'] for event in events] == ['team.approval_required']


def test_dispatcher_allows_when_matching_approval_exists(tmp_path):
    ApprovalStore(tmp_path).upsert({
        'approval_id': 'apr-existing',
        'status': 'approved',
        'scope': {'task_id': 'TSK-APPROVED', 'run_id': 'run-approved', 'role': 'executor'},
    })

    dispatcher = TeamDispatcher(
        runner=TeamRunner(executor=lambda role, goal, context, task_id, run_id: TeamRunnerResult(status='completed', summary='approved run')),
        registry_store=RegistryStore(tmp_path),
        event_store=TeamEventStore(tmp_path),
    )

    result = dispatcher.dispatch(DispatchRequest(
        task_id='TSK-APPROVED',
        run_id='run-approved',
        role='executor',
        goal='deploy to production',
    ))

    assert result.status == 'completed'
    assert result.summary == 'approved run'
