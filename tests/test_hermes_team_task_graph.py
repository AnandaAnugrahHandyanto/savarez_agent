from __future__ import annotations

import time

from hermes_team.dispatcher import TeamDispatcher
from hermes_team.messages import TeamEventStore
from hermes_team.registry_store import RegistryStore
from hermes_team.runner import TeamRunner, TeamRunnerResult
from hermes_team.task_graph import TeamGraphNode, TeamGraphRunner, TeamTaskGraph


def test_task_graph_topological_order_and_cycle_detection():
    import pytest

    graph = TeamTaskGraph([
        TeamGraphNode(id='research', role='researcher', goal='research'),
        TeamGraphNode(id='plan', role='planner', goal='plan', depends_on=['research']),
        TeamGraphNode(id='execute', role='executor', goal='execute', depends_on=['plan']),
    ])

    assert [node.id for node in graph.topological_order()] == ['research', 'plan', 'execute']

    with pytest.raises(ValueError, match='cycle'):
        TeamTaskGraph([
            TeamGraphNode(id='a', role='executor', goal='a', depends_on=['b']),
            TeamGraphNode(id='b', role='executor', goal='b', depends_on=['a']),
        ])


def test_task_graph_execution_levels_group_independent_nodes():
    graph = TeamTaskGraph([
        TeamGraphNode(id='a', role='executor', goal='a'),
        TeamGraphNode(id='b', role='executor', goal='b'),
        TeamGraphNode(id='c', role='reviewer', goal='c', depends_on=['a', 'b']),
    ])

    assert [[node.id for node in level] for level in graph.execution_levels()] == [['a', 'b'], ['c']]


def test_graph_runner_blocks_dependents_when_dependency_fails(tmp_path):
    def fake_executor(role, goal, context, task_id, run_id):
        if goal == 'fail':
            return TeamRunnerResult(status='failed', error='boom')
        return TeamRunnerResult(status='completed', summary=f'{role.name}:{goal}')

    dispatcher = TeamDispatcher(
        runner=TeamRunner(executor=fake_executor),
        registry_store=RegistryStore(tmp_path),
        event_store=TeamEventStore(tmp_path),
    )
    graph = TeamTaskGraph([
        TeamGraphNode(id='a', role='executor', goal='fail'),
        TeamGraphNode(id='b', role='reviewer', goal='review', depends_on=['a']),
    ])

    result = TeamGraphRunner(dispatcher).run(graph, task_id='TSK-GRAPH', run_id='run-graph')

    assert result.status == 'failed'
    assert [item.role for item in result.results] == ['executor']
    assert 'b' in result.blocked_nodes
    assert any('blocked by failed dependencies' in error for error in result.errors)


def test_graph_runner_parallelizes_independent_dependency_levels(tmp_path):
    started: list[str] = []

    def fake_executor(role, goal, context, task_id, run_id):
        started.append(goal)
        if goal in {'a', 'b'}:
            time.sleep(0.05)
        return TeamRunnerResult(status='completed', summary=f'{role.name}:{goal}')

    dispatcher = TeamDispatcher(
        runner=TeamRunner(executor=fake_executor),
        registry_store=RegistryStore(tmp_path),
        event_store=TeamEventStore(tmp_path),
    )
    graph = TeamTaskGraph([
        TeamGraphNode(id='a', role='executor', goal='a'),
        TeamGraphNode(id='b', role='executor', goal='b'),
        TeamGraphNode(id='c', role='reviewer', goal='c', depends_on=['a', 'b']),
    ])

    result = TeamGraphRunner(dispatcher).run(graph, task_id='TSK-PARALLEL', run_id='run-parallel', parallel=True, max_concurrency=2)

    assert result.status == 'completed'
    assert result.parallel is True
    assert result.execution_order == [['a', 'b'], ['c']]
    assert [item.summary for item in result.results] == ['executor:a', 'executor:b', 'reviewer:c']
    assert set(started[:2]) == {'a', 'b'}
    assert started[-1] == 'c'
