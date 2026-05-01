from __future__ import annotations

from hermes_team.dispatcher import DispatchRequest, TeamDispatcher
from hermes_team.messages import TeamEventStore
from hermes_team.orchestrator import TeamOrchestrator, TeamRunSpec
from hermes_team.registry_store import RegistryStore
from hermes_team.roles import DEFAULT_ROLES, RoleRegistry, TeamRole
from hermes_team.runner import TeamRunner, TeamRunnerResult


def test_default_roles_include_core_team_roles():
    registry = RoleRegistry.default()

    assert {'cio', 'researcher', 'planner', 'executor', 'reviewer', 'risk_officer'} <= set(registry.names())
    assert registry.get('executor').toolsets == ['terminal', 'file']
    assert registry.get('cio').can_delegate is True


def test_dispatcher_runs_role_and_persists_registry_and_events(tmp_path):
    def fake_executor(role, goal, context, task_id, run_id):
        return TeamRunnerResult(status='completed', summary=f'{role.name}:{goal}', session_id='sess-1')

    dispatcher = TeamDispatcher(
        runner=TeamRunner(executor=fake_executor),
        registry_store=RegistryStore(tmp_path),
        event_store=TeamEventStore(tmp_path),
    )

    result = dispatcher.dispatch(DispatchRequest(task_id='TSK-1', run_id='run-1', role='executor', goal='do work'))

    assert result.status == 'completed'
    assert result.summary == 'executor:do work'
    registry = RegistryStore(tmp_path).load()
    assert registry['tasks']['TSK-1']['runIds'] == ['run-1']
    assert registry['tasks']['TSK-1']['sessionIds'] == ['sess-1']
    assert registry['tasks']['TSK-1']['lastStatus'] == 'completed'
    events = TeamEventStore(tmp_path).list(task_id='TSK-1')
    assert [event['event'] for event in events] == ['team.sandbox_applied', 'team.agent_started', 'team.agent_completed']


def test_dispatcher_blocks_disallowed_toolsets(tmp_path):
    role = TeamRole(name='limited', description='limited', system_prompt='limited', toolsets=['file'])
    registry = RoleRegistry({'limited': role})
    dispatcher = TeamDispatcher(role_registry=registry, registry_store=RegistryStore(tmp_path), event_store=TeamEventStore(tmp_path))

    result = dispatcher.dispatch(DispatchRequest(task_id='TSK-2', run_id='run-2', role='limited', goal='x', toolsets=['terminal']))

    assert result.status == 'blocked'
    assert 'toolset not allowed' in (result.error or '')
    assert RegistryStore(tmp_path).load()['tasks']['TSK-2']['lastStatus'] == 'blocked'


def test_orchestrator_sequential_flow_with_fake_runner(tmp_path, monkeypatch):
    monkeypatch.setenv('HERMES_HOME', str(tmp_path.parent))

    def fake_executor(role, goal, context, task_id, run_id):
        return {'status': 'completed', 'summary': f'{role.name} ok', 'session_id': f'sess-{role.name}'}

    event_store = TeamEventStore(tmp_path)
    dispatcher = TeamDispatcher(
        runner=TeamRunner(executor=fake_executor),
        registry_store=RegistryStore(tmp_path),
        event_store=event_store,
    )
    orchestrator = TeamOrchestrator(dispatcher=dispatcher, event_store=event_store)

    result = orchestrator.run(TeamRunSpec(task_id='TSK-3', goal='build feature', roles=['executor'], context='ctx'))

    assert result.status == 'completed'
    assert [step['role'] for step in result.steps] == ['executor', 'reviewer']
    runs = orchestrator.run_store.load()['runs']
    assert result.run_id in runs
    events = event_store.list(task_id='TSK-3')
    assert events[0]['event'] == 'team.run_started'
    assert events[-1]['event'] == 'team.completed'
