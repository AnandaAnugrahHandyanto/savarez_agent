from __future__ import annotations

import json
from typing import Any

from hermes_team.approval_audit import ApprovalAuditReporter
from hermes_team.approval_manager import TeamApprovalManager
from hermes_team.metrics_reporter import TeamMetricsReporter
from hermes_team.replanner import ReplanStore
from hermes_team.sandbox import TeamSandboxAuditStore
from hermes_team.watcher import TeamWatcher
from hermes_team.messages import TeamEventStore
from hermes_team.orchestrator import TeamOrchestrator, TeamRunSpec, TeamRunStore
from hermes_team.roles import RoleRegistry
from hermes_team.workflow_templates import WorkflowTemplateRegistry, apply_workflow_template
from tools.registry import registry


def _json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def _parse_roles(value: Any) -> list[str]:
    if value is None:
        return ['executor', 'reviewer']
    if isinstance(value, str):
        return [part.strip() for part in value.split(',') if part.strip()]
    if isinstance(value, list):
        return [str(part).strip() for part in value if str(part).strip()]
    return ['executor', 'reviewer']


def team_run_task_tool(args: dict[str, Any], **_: Any) -> str:
    goal = str(args.get('goal') or '').strip()
    if not goal:
        return _json({'ok': False, 'error': 'goal is required'})

    template = str(args.get('template') or '').strip()
    metadata = dict(args.get('metadata') or {})
    if template:
        try:
            spec = apply_workflow_template(
                template,
                goal=goal,
                task_id=(str(args.get('task_id')).strip() if args.get('task_id') else None),
                context=str(args.get('context') or ''),
                metadata=metadata,
            )
        except Exception as exc:
            return _json({'ok': False, 'error': str(exc)})
        if args.get('graph') is not None:
            spec.graph = list(args.get('graph')) if isinstance(args.get('graph'), list) else spec.graph
            spec.mode = str(args.get('mode') or 'dag')
        if args.get('roles') is not None:
            spec.roles = _parse_roles(args.get('roles'))
        if args.get('parallel') is not None:
            spec.parallel = bool(args.get('parallel'))
        if args.get('max_concurrency'):
            spec.max_concurrency = int(args.get('max_concurrency'))
        if args.get('require_review') is not None:
            spec.require_review = bool(args.get('require_review'))
        if args.get('auto_replan') is not None:
            spec.auto_replan = bool(args.get('auto_replan'))
    else:
        spec = TeamRunSpec(
            goal=goal,
            task_id=(str(args.get('task_id')).strip() if args.get('task_id') else None),
            mode=str(args.get('mode') or 'sequential'),
            roles=_parse_roles(args.get('roles')),
            graph=(list(args.get('graph')) if isinstance(args.get('graph'), list) else None),
            context=str(args.get('context') or ''),
            require_review=bool(args.get('require_review', True)),
            parallel=bool(args.get('parallel', False)),
            max_concurrency=(int(args.get('max_concurrency')) if args.get('max_concurrency') else None),
            metadata=metadata,
            auto_replan=bool(args.get('auto_replan', False)),
        )
    result = TeamOrchestrator.default().run(spec)
    return _json({'ok': result.status == 'completed', 'result': result.to_dict()})


def team_status_tool(args: dict[str, Any], **_: Any) -> str:
    run_id = args.get('run_id')
    task_id = args.get('task_id')
    runs = TeamRunStore().load().get('runs', {})
    if run_id:
        run = runs.get(str(run_id))
        return _json({'ok': bool(run), 'run': run, 'error': None if run else f'run not found: {run_id}'})
    if task_id:
        matched = [run for run in runs.values() if run.get('task_id') == str(task_id)]
        return _json({'ok': True, 'runs': matched, 'count': len(matched)})
    latest = sorted(runs.values(), key=lambda item: item.get('updated_at') or '', reverse=True)
    limit = int(args.get('limit') or 10)
    return _json({'ok': True, 'runs': latest[:limit], 'count': len(latest)})


def team_events_tool(args: dict[str, Any], **_: Any) -> str:
    task_id = str(args.get('task_id')).strip() if args.get('task_id') else None
    run_id = str(args.get('run_id')).strip() if args.get('run_id') else None
    limit = int(args.get('limit') or 50)
    events = TeamEventStore().list(task_id=task_id, run_id=run_id)
    return _json({'ok': True, 'events': events[-limit:], 'count': len(events)})


def team_roles_tool(args: dict[str, Any] | None = None, **_: Any) -> str:
    roles = [role.__dict__ for role in RoleRegistry.default().list()]
    return _json({'ok': True, 'roles': roles})


def team_approvals_tool(args: dict[str, Any], **_: Any) -> str:
    status = str(args.get('status')).strip() if args.get('status') else None
    approvals = TeamApprovalManager().list(status=status)
    return _json({'ok': True, 'approvals': approvals, 'count': len(approvals)})


def team_approve_tool(args: dict[str, Any], **_: Any) -> str:
    approval_id = str(args.get('approval_id') or '').strip()
    if not approval_id:
        return _json({'ok': False, 'error': 'approval_id is required'})
    try:
        approval = TeamApprovalManager().decide(
            approval_id,
            decision='approved',
            by=str(args.get('by') or 'hermes_team.tool'),
            reason=str(args.get('reason') or ''),
        )
    except Exception as exc:
        return _json({'ok': False, 'error': str(exc)})
    return _json({'ok': True, 'approval': approval})


def team_reject_tool(args: dict[str, Any], **_: Any) -> str:
    approval_id = str(args.get('approval_id') or '').strip()
    if not approval_id:
        return _json({'ok': False, 'error': 'approval_id is required'})
    try:
        approval = TeamApprovalManager().decide(
            approval_id,
            decision='rejected',
            by=str(args.get('by') or 'hermes_team.tool'),
            reason=str(args.get('reason') or ''),
        )
    except Exception as exc:
        return _json({'ok': False, 'error': str(exc)})
    return _json({'ok': True, 'approval': approval})


def team_metrics_tool(args: dict[str, Any] | None = None, **_: Any) -> str:
    return _json({'ok': True, 'metrics': TeamMetricsReporter().report().to_dict()})


def team_watch_tool(args: dict[str, Any], **_: Any) -> str:
    watcher = TeamWatcher()
    snapshot = watcher.snapshot(
        run_id=(str(args.get('run_id')).strip() if args.get('run_id') else None),
        task_id=(str(args.get('task_id')).strip() if args.get('task_id') else None),
        limit=int(args.get('limit') or 20),
        stale_after_seconds=int(args.get('stale_after_seconds') or 900),
    )
    if str(args.get('format') or 'json') == 'text':
        return watcher.render_text(snapshot)
    return _json({'ok': snapshot.status != 'not_found', 'watch': snapshot.to_dict()})


def team_sandbox_audit_tool(args: dict[str, Any], **_: Any) -> str:
    records = TeamSandboxAuditStore().list(
        task_id=(str(args.get('task_id')).strip() if args.get('task_id') else None),
        run_id=(str(args.get('run_id')).strip() if args.get('run_id') else None),
        limit=(int(args.get('limit')) if args.get('limit') else None),
    )
    return _json({'ok': True, 'records': records, 'count': len(records)})


def team_replans_tool(args: dict[str, Any], **_: Any) -> str:
    rows = ReplanStore().list(
        task_id=(str(args.get('task_id')).strip() if args.get('task_id') else None),
        run_id=(str(args.get('run_id')).strip() if args.get('run_id') else None),
    )
    return _json({'ok': True, 'replans': rows, 'count': len(rows)})


def team_approval_audit_tool(args: dict[str, Any] | None = None, **_: Any) -> str:
    return _json({'ok': True, 'audit': ApprovalAuditReporter().report().to_dict()})


def team_templates_tool(args: dict[str, Any] | None = None, **_: Any) -> str:
    args = args or {}
    registry_ = WorkflowTemplateRegistry.default()
    name = str(args.get('name') or '').strip()
    if name:
        try:
            return _json({'ok': True, 'template': registry_.get(name).to_dict()})
        except Exception as exc:
            return _json({'ok': False, 'error': str(exc)})
    return _json({'ok': True, 'templates': [template.to_dict() for template in registry_.list_templates()]})


TEAM_RUN_TASK_SCHEMA = {
    'name': 'team_run_task',
    'description': 'Run a Hermes-native multi-agent team workflow for a goal. Creates/persists task/run/events state.',
    'parameters': {
        'type': 'object',
        'properties': {
            'goal': {'type': 'string', 'description': 'Objective for the team to execute.'},
            'context': {'type': 'string', 'description': 'Relevant context, constraints, paths, verification commands.'},
            'task_id': {'type': 'string', 'description': 'Existing Hermes team task id. Omit to create one.'},
            'template': {'type': 'string', 'description': 'Optional workflow template name from team_templates, e.g. implementation_review or parallel_audit.'},
            'roles': {'type': 'array', 'items': {'type': 'string'}, 'description': 'Ordered role workflow, e.g. ["planner", "executor", "reviewer"].'},
            'mode': {'type': 'string', 'enum': ['sequential', 'dag'], 'default': 'sequential'},
            'graph': {
                'type': 'array',
                'description': 'Optional DAG nodes for mode=dag. Each node has id, role, goal, depends_on, context, toolsets.',
                'items': {
                    'type': 'object',
                    'properties': {
                        'id': {'type': 'string'},
                        'role': {'type': 'string'},
                        'goal': {'type': 'string'},
                        'depends_on': {'type': 'array', 'items': {'type': 'string'}},
                        'context': {'type': 'string'},
                        'toolsets': {'type': 'array', 'items': {'type': 'string'}},
                        'metadata': {'type': 'object'},
                    },
                    'required': ['id', 'role', 'goal'],
                },
            },
            'parallel': {'type': 'boolean', 'default': False, 'description': 'For DAG mode, run nodes at the same dependency level concurrently.'},
            'max_concurrency': {'type': 'integer', 'default': 4},
            'require_review': {'type': 'boolean', 'default': True},
            'metadata': {'type': 'object', 'description': 'Optional metadata such as priority.'},
            'auto_replan': {'type': 'boolean', 'default': False, 'description': 'If true, propose and execute one bounded recovery DAG for non-approval failures.'},
        },
        'required': ['goal'],
    },
}

TEAM_STATUS_SCHEMA = {
    'name': 'team_status',
    'description': 'Inspect Hermes team run status by run_id, task_id, or latest runs.',
    'parameters': {'type': 'object', 'properties': {'run_id': {'type': 'string'}, 'task_id': {'type': 'string'}, 'limit': {'type': 'integer', 'default': 10}}, 'required': []},
}

TEAM_EVENTS_SCHEMA = {
    'name': 'team_events',
    'description': 'List Hermes team events filtered by run_id or task_id.',
    'parameters': {'type': 'object', 'properties': {'run_id': {'type': 'string'}, 'task_id': {'type': 'string'}, 'limit': {'type': 'integer', 'default': 50}}, 'required': []},
}

TEAM_ROLES_SCHEMA = {'name': 'team_roles', 'description': 'List Hermes-native team roles and their allowed toolsets.', 'parameters': {'type': 'object', 'properties': {}, 'required': []}}
TEAM_APPROVALS_SCHEMA = {'name': 'team_approvals', 'description': 'List Hermes team approvals, optionally filtered by status.', 'parameters': {'type': 'object', 'properties': {'status': {'type': 'string'}}, 'required': []}}
TEAM_APPROVE_SCHEMA = {'name': 'team_approve', 'description': 'Approve a pending Hermes team dispatch. Human confirmation must already be present in chat/context.', 'parameters': {'type': 'object', 'properties': {'approval_id': {'type': 'string'}, 'reason': {'type': 'string'}, 'by': {'type': 'string'}}, 'required': ['approval_id']}}
TEAM_REJECT_SCHEMA = {'name': 'team_reject', 'description': 'Reject a pending Hermes team dispatch.', 'parameters': {'type': 'object', 'properties': {'approval_id': {'type': 'string'}, 'reason': {'type': 'string'}, 'by': {'type': 'string'}}, 'required': ['approval_id']}}
TEAM_METRICS_SCHEMA = {'name': 'team_metrics', 'description': 'Summarize Hermes team runs, events, approvals, and registry task counts.', 'parameters': {'type': 'object', 'properties': {}, 'required': []}}
TEAM_WATCH_SCHEMA = {'name': 'team_watch', 'description': 'Render a live-style watch snapshot for a Hermes team run/task, including latest events and stale detection.', 'parameters': {'type': 'object', 'properties': {'run_id': {'type': 'string'}, 'task_id': {'type': 'string'}, 'limit': {'type': 'integer', 'default': 20}, 'stale_after_seconds': {'type': 'integer', 'default': 900}, 'format': {'type': 'string', 'enum': ['json', 'text'], 'default': 'json'}}, 'required': []}}
TEAM_SANDBOX_AUDIT_SCHEMA = {'name': 'team_sandbox_audit', 'description': 'List sandbox policies applied to Hermes team role dispatches.', 'parameters': {'type': 'object', 'properties': {'run_id': {'type': 'string'}, 'task_id': {'type': 'string'}, 'limit': {'type': 'integer'}}, 'required': []}}
TEAM_REPLANS_SCHEMA = {'name': 'team_replans', 'description': 'List bounded dynamic replan proposals/results for Hermes team runs.', 'parameters': {'type': 'object', 'properties': {'run_id': {'type': 'string'}, 'task_id': {'type': 'string'}}, 'required': []}}
TEAM_APPROVAL_AUDIT_SCHEMA = {'name': 'team_approval_audit', 'description': 'Audit Hermes team approvals for pending decisions and incomplete scope risk.', 'parameters': {'type': 'object', 'properties': {}, 'required': []}}
TEAM_TEMPLATES_SCHEMA = {'name': 'team_templates', 'description': 'List or inspect built-in Hermes team workflow templates.', 'parameters': {'type': 'object', 'properties': {'name': {'type': 'string'}}, 'required': []}}


def check_team_requirements() -> bool:
    return True


registry.register('team_run_task', 'team', TEAM_RUN_TASK_SCHEMA, team_run_task_tool, check_fn=check_team_requirements, emoji='👥')
registry.register('team_status', 'team', TEAM_STATUS_SCHEMA, team_status_tool, check_fn=check_team_requirements, emoji='👥')
registry.register('team_events', 'team', TEAM_EVENTS_SCHEMA, team_events_tool, check_fn=check_team_requirements, emoji='👥')
registry.register('team_roles', 'team', TEAM_ROLES_SCHEMA, team_roles_tool, check_fn=check_team_requirements, emoji='👥')
registry.register('team_approvals', 'team', TEAM_APPROVALS_SCHEMA, team_approvals_tool, check_fn=check_team_requirements, emoji='👥')
registry.register('team_approve', 'team', TEAM_APPROVE_SCHEMA, team_approve_tool, check_fn=check_team_requirements, emoji='👥')
registry.register('team_reject', 'team', TEAM_REJECT_SCHEMA, team_reject_tool, check_fn=check_team_requirements, emoji='👥')
registry.register('team_metrics', 'team', TEAM_METRICS_SCHEMA, team_metrics_tool, check_fn=check_team_requirements, emoji='👥')
registry.register('team_watch', 'team', TEAM_WATCH_SCHEMA, team_watch_tool, check_fn=check_team_requirements, emoji='👥')
registry.register('team_sandbox_audit', 'team', TEAM_SANDBOX_AUDIT_SCHEMA, team_sandbox_audit_tool, check_fn=check_team_requirements, emoji='👥')
registry.register('team_replans', 'team', TEAM_REPLANS_SCHEMA, team_replans_tool, check_fn=check_team_requirements, emoji='👥')
registry.register('team_approval_audit', 'team', TEAM_APPROVAL_AUDIT_SCHEMA, team_approval_audit_tool, check_fn=check_team_requirements, emoji='👥')
registry.register('team_templates', 'team', TEAM_TEMPLATES_SCHEMA, team_templates_tool, check_fn=check_team_requirements, emoji='👥')
