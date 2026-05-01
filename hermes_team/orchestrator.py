from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .dispatcher import DispatchRequest, DispatchResult, TeamDispatcher
from .approval_gate import ApprovalGate
from .json_store import JsonStateStore
from .messages import TeamEvent, TeamEventStore
from .replanner import TeamReplanner
from .roles import RoleRegistry
from .task_store import TaskStore

TZ = timezone(timedelta(hours=8))


@dataclass
class TeamRunSpec:
    goal: str
    task_id: str | None = None
    mode: str = 'sequential'
    roles: list[str] = field(default_factory=lambda: ['executor', 'reviewer'])
    graph: list[dict[str, Any]] | None = None
    context: str = ''
    require_review: bool = True
    parallel: bool = False
    max_concurrency: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    auto_replan: bool = False


@dataclass
class TeamRunResult:
    task_id: str
    run_id: str
    status: str
    final_summary: str
    steps: list[dict[str, Any]]
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TeamRunStore(JsonStateStore):
    def __init__(self, state_dir: Path | None = None) -> None:
        super().__init__(state_dir)
        self.path = self.state_dir / 'runs.json'

    def save_run(self, result: TeamRunResult) -> dict[str, Any]:
        data = self._load_json(self.path, {'runs': {}})
        if not isinstance(data, dict):
            data = {'runs': {}}
        data.setdefault('runs', {})[result.run_id] = result.to_dict() | {'updated_at': datetime.now(TZ).isoformat()}
        self._save_json(self.path, data)
        return data['runs'][result.run_id]

    def load(self) -> dict[str, Any]:
        data = self._load_json(self.path, {'runs': {}})
        return data if isinstance(data, dict) else {'runs': {}}


class TeamOrchestrator:
    def __init__(
        self,
        dispatcher: TeamDispatcher | None = None,
        task_store: TaskStore | None = None,
        event_store: TeamEventStore | None = None,
        run_store: TeamRunStore | None = None,
        role_registry: RoleRegistry | None = None,
    ) -> None:
        self.task_store = task_store or TaskStore()
        self.event_store = event_store or TeamEventStore(self.task_store.state_dir)
        self.run_store = run_store or TeamRunStore(self.task_store.state_dir)
        self.role_registry = role_registry or RoleRegistry.default()
        self.dispatcher = dispatcher or TeamDispatcher(role_registry=self.role_registry, event_store=self.event_store)

    @classmethod
    def default(cls) -> 'TeamOrchestrator':
        return cls()

    def run(self, spec: TeamRunSpec) -> TeamRunResult:
        self._sync_store_paths()
        task_id = spec.task_id or self._create_task(spec)
        run_id = f"run-{uuid4().hex[:12]}"
        self.event_store.append(TeamEvent('team.run_started', task_id=task_id, run_id=run_id, payload={'goal': spec.goal, 'roles': spec.roles}))
        self._transition_best_effort(task_id, 'cio_triage', 'hermes_team.orchestrator', 'team run started')
        self._transition_best_effort(task_id, 'assigned', 'hermes_team.orchestrator', 'team roles assigned')

        if spec.mode == 'dag' or spec.graph:
            result = self._run_graph(spec, task_id, run_id)
            return self._maybe_replan(spec, result)

        requests = self.plan(spec, task_id, run_id)
        steps: list[dict[str, Any]] = []
        errors: list[str] = []
        for request in requests:
            if request.role != 'reviewer':
                self._transition_best_effort(task_id, 'executing', request.role, f'{request.role} started')
            result = self.dispatcher.dispatch(request)
            steps.append(result.to_dict())
            if result.status != 'completed':
                errors.append(result.error or f'{result.role} {result.status}')
                self._transition_best_effort(task_id, 'blocked', result.role, result.error or 'team step failed')
                final = self._finalize(task_id, run_id, 'failed', steps, errors)
                return self._maybe_replan(spec, final)
            if request.role != 'reviewer':
                self._transition_best_effort(task_id, 'review', request.role, f'{request.role} completed')

        result = self._finalize(task_id, run_id, 'completed', steps, errors)
        self._transition_best_effort(task_id, 'done', 'hermes_team.orchestrator', 'team run completed')
        return result

    def plan(self, spec: TeamRunSpec, task_id: str, run_id: str) -> list[DispatchRequest]:
        roles = list(spec.roles or ['executor', 'reviewer'])
        if spec.require_review and 'reviewer' not in roles:
            roles.append('reviewer')
        requests: list[DispatchRequest] = []
        for role in roles:
            role_goal = spec.goal if role != 'reviewer' else f"Review the team output for this objective and return PASS or concrete gaps: {spec.goal}"
            requests.append(DispatchRequest(task_id=task_id, run_id=run_id, role=role, goal=role_goal, context=spec.context, require_review=spec.require_review))
        return requests

    def synthesize(self, steps: list[dict[str, Any]]) -> str:
        summaries = [f"{step.get('role')}: {step.get('summary') or step.get('error') or step.get('status')}" for step in steps]
        return '\n'.join(summaries)

    def _run_graph(self, spec: TeamRunSpec, task_id: str, run_id: str) -> TeamRunResult:
        from .task_graph import TeamGraphNode, TeamGraphRunner, TeamTaskGraph

        nodes = [
            TeamGraphNode(
                id=str(node.get('id') or f"node-{idx}"),
                role=str(node.get('role') or 'executor'),
                goal=str(node.get('goal') or spec.goal),
                context=str(node.get('context') or ''),
                depends_on=[str(dep) for dep in node.get('depends_on', [])],
                toolsets=node.get('toolsets'),
                metadata=dict(node.get('metadata') or {}),
            )
            for idx, node in enumerate(spec.graph or [])
        ]
        if not nodes:
            nodes = [TeamGraphNode(id='executor', role='executor', goal=spec.goal)]
        graph_result = TeamGraphRunner(self.dispatcher).run(
            TeamTaskGraph(nodes),
            task_id=task_id,
            run_id=run_id,
            inherited_context=spec.context,
            parallel=spec.parallel,
            max_concurrency=spec.max_concurrency,
        )
        steps = [result.to_dict() for result in graph_result.results]
        final = self._finalize(task_id, run_id, graph_result.status, steps, graph_result.errors)
        self._transition_best_effort(
            task_id,
            'done' if graph_result.status == 'completed' else 'blocked',
            'hermes_team.orchestrator',
            f'team graph {graph_result.status}',
        )
        return final

    def _maybe_replan(self, spec: TeamRunSpec, result: TeamRunResult) -> TeamRunResult:
        if not spec.auto_replan:
            return result
        replanner = TeamReplanner(self.task_store.state_dir)
        decision = replanner.evaluate(result, spec)
        replanner.record(task_id=result.task_id, run_id=result.run_id, decision=decision)
        if not decision.needed or decision.spec is None:
            return result
        replanned = self.run(decision.spec)
        combined_steps = list(result.steps) + [{'role': 'replanner', 'status': 'completed', 'summary': decision.reason, 'raw': {'replan_run_id': replanned.run_id}}] + list(replanned.steps)
        combined_errors = list(result.errors) + list(replanned.errors)
        status = 'completed' if replanned.status == 'completed' else result.status
        return self._finalize(result.task_id, result.run_id, status, combined_steps, combined_errors)

    def _sync_store_paths(self) -> None:
        state_dir = self.task_store.state_dir
        self.event_store.state_dir = state_dir
        self.event_store.path = state_dir / 'events.json'
        self.run_store.state_dir = state_dir
        self.run_store.path = state_dir / 'runs.json'
        self.dispatcher.event_store = self.event_store
        self.dispatcher.registry_store.state_dir = state_dir
        self.dispatcher.registry_store.path = state_dir / 'task_run_session_registry.json'
        self.dispatcher.approval_gate = ApprovalGate(state_dir=state_dir)
        self.dispatcher.sandbox_audit.state_dir = state_dir
        self.dispatcher.sandbox_audit.path = state_dir / 'sandbox_audit.json'

    def _create_task(self, spec: TeamRunSpec) -> str:
        from . import task_hook

        task = task_hook.create_task(spec.goal[:80] or 'team run', spec.context or spec.goal, priority=str(spec.metadata.get('priority', 'normal')))
        return str(task['id'])

    def _finalize(self, task_id: str, run_id: str, status: str, steps: list[dict[str, Any]], errors: list[str]) -> TeamRunResult:
        final_summary = self.synthesize(steps)
        result = TeamRunResult(task_id=task_id, run_id=run_id, status=status, final_summary=final_summary, steps=steps, errors=errors)
        self.run_store.save_run(result)
        self.event_store.append(TeamEvent('team.completed' if status == 'completed' else 'team.failed', task_id=task_id, run_id=run_id, payload=result.to_dict()))
        return result

    @staticmethod
    def _transition_best_effort(task_id: str, new_state: str, by: str, reason: str) -> None:
        try:
            from . import task_hook

            task_hook.transition(task_id, new_state, by=by, reason=reason)
        except Exception:
            return
