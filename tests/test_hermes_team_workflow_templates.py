from __future__ import annotations

import json

from hermes_team.workflow_templates import WorkflowTemplateRegistry, apply_workflow_template
from tools.hermes_team_tool import team_run_task_tool, team_templates_tool


def test_workflow_template_registry_lists_builtin_templates():
    templates = WorkflowTemplateRegistry.default().list_templates()
    names = {template.name for template in templates}
    assert {'implementation_review', 'research_plan_execute', 'parallel_audit'} <= names


def test_apply_workflow_template_builds_parallel_audit_dag():
    spec = apply_workflow_template('parallel_audit', goal='Audit Hermes team runtime', context='repo path')
    assert spec.mode == 'dag'
    assert spec.parallel is True
    assert spec.max_concurrency >= 2
    assert spec.graph is not None
    ids = {node['id'] for node in spec.graph}
    assert {'security', 'tests', 'docs', 'synthesis'} <= ids
    synthesis = next(node for node in spec.graph if node['id'] == 'synthesis')
    assert set(synthesis['depends_on']) == {'security', 'tests', 'docs'}
    assert 'repo path' in spec.context


def test_team_templates_tool_lists_and_describes_templates():
    listed = json.loads(team_templates_tool({}))
    assert listed['ok'] is True
    assert any(item['name'] == 'parallel_audit' for item in listed['templates'])

    described = json.loads(team_templates_tool({'name': 'implementation_review'}))
    assert described['ok'] is True
    assert described['template']['name'] == 'implementation_review'
    assert described['template']['mode'] == 'sequential'


def test_team_run_task_tool_accepts_template(monkeypatch, tmp_path):
    monkeypatch.setenv('HERMES_HOME', str(tmp_path))

    captured = {}

    def fake_run(self, spec):
        captured['spec'] = spec
        from hermes_team.orchestrator import TeamRunResult
        return TeamRunResult(task_id='TSK-TPL', run_id='run-template', status='completed', final_summary='ok', steps=[])

    monkeypatch.setattr('hermes_team.orchestrator.TeamOrchestrator.run', fake_run)

    payload = json.loads(team_run_task_tool({
        'goal': 'ship feature',
        'template': 'implementation_review',
        'context': 'repo=/tmp/repo',
        'metadata': {'priority': 'high'},
    }))

    assert payload['ok'] is True
    assert payload['result']['run_id'] == 'run-template'
    spec = captured['spec']
    assert spec.roles == ['planner', 'executor', 'reviewer']
    assert spec.context == 'repo=/tmp/repo'
    assert spec.metadata['template'] == 'implementation_review'
    assert spec.metadata['priority'] == 'high'
