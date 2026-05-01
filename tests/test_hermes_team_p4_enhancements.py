from __future__ import annotations

from hermes_team.dispatcher import TeamDispatcher
from hermes_team.orchestrator import TeamOrchestrator, TeamRunSpec
from hermes_team.registry_store import RegistryStore
from hermes_team.runner import TeamRunner, TeamRunnerResult
from hermes_team.sandbox import TeamSandboxAuditStore
from hermes_team.watcher import TeamWatcher


def test_dispatch_records_sandbox_policy_and_watcher_snapshot(tmp_path):
    def fake_executor(role, goal, context='', task_id=None, run_id=None):
        return TeamRunnerResult(status='completed', summary=f'{role.name} done')

    orchestrator = TeamOrchestrator(dispatcher=None, task_store=None)
    orchestrator.task_store.state_dir = tmp_path
    orchestrator.event_store.state_dir = tmp_path
    orchestrator.run_store.state_dir = tmp_path
    orchestrator.dispatcher = TeamDispatcher(
        runner=TeamRunner(fake_executor),
        registry_store=RegistryStore(tmp_path),
        event_store=orchestrator.event_store,
        sandbox_audit=TeamSandboxAuditStore(tmp_path),
    )

    result = orchestrator.run(TeamRunSpec(goal='sandbox smoke', task_id='TSK-SANDBOX', roles=['executor'], require_review=False))

    assert result.status == 'completed'
    audit = TeamSandboxAuditStore(tmp_path).list(run_id=result.run_id)
    assert len(audit) == 1
    assert audit[0]['policy']['enabled'] is True

    snapshot = TeamWatcher(tmp_path).snapshot(run_id=result.run_id)
    assert snapshot.status == 'completed'
    assert snapshot.events_count >= 3


def test_auto_replan_recovers_non_approval_failure(tmp_path):
    calls = []

    def flaky_executor(role, goal, context='', task_id=None, run_id=None):
        calls.append((role.name, goal))
        if len(calls) == 1:
            return TeamRunnerResult(status='failed', error='deterministic failure')
        return TeamRunnerResult(status='completed', summary=f'{role.name} recovered')

    runner = TeamRunner(flaky_executor)
    orchestrator = TeamOrchestrator.default()
    orchestrator.task_store.state_dir = tmp_path
    orchestrator.event_store.state_dir = tmp_path
    orchestrator.run_store.state_dir = tmp_path
    orchestrator.dispatcher = TeamDispatcher(
        runner=runner,
        registry_store=RegistryStore(tmp_path),
        event_store=orchestrator.event_store,
        sandbox_audit=TeamSandboxAuditStore(tmp_path),
    )

    result = orchestrator.run(TeamRunSpec(goal='recover objective', task_id='TSK-REPLAN', roles=['executor'], require_review=False, auto_replan=True))

    assert result.status == 'completed'
    assert any(step['role'] == 'replanner' for step in result.steps)
    events = [event['event'] for event in orchestrator.event_store.list(run_id=result.run_id)]
    assert 'team.replan_proposed' in events
