from __future__ import annotations

from dataclasses import asdict, dataclass, field
import time
from typing import Any
from uuid import uuid4

from .approval_gate import ApprovalGate
from .messages import TeamEvent, TeamEventStore
from .policies import PolicyEngine
from .registry_store import RegistryStore
from .roles import RoleRegistry
from .runner import TeamRunner
from .sandbox import TeamSandboxAuditStore, TeamSandboxPolicyEngine


@dataclass
class DispatchRequest:
    task_id: str
    role: str
    goal: str
    context: str = ''
    toolsets: list[str] | None = None
    run_id: str | None = None
    require_review: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DispatchResult:
    task_id: str
    run_id: str
    role: str
    status: str
    summary: str = ''
    error: str | None = None
    session_id: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TeamDispatcher:
    def __init__(
        self,
        role_registry: RoleRegistry | None = None,
        runner: TeamRunner | None = None,
        registry_store: RegistryStore | None = None,
        event_store: TeamEventStore | None = None,
        policy_engine: PolicyEngine | None = None,
        approval_gate: ApprovalGate | None = None,
        sandbox_engine: TeamSandboxPolicyEngine | None = None,
        sandbox_audit: TeamSandboxAuditStore | None = None,
    ) -> None:
        self.role_registry = role_registry or RoleRegistry.default()
        self.runner = runner or TeamRunner()
        self.registry_store = registry_store or RegistryStore()
        self.event_store = event_store or TeamEventStore()
        self.policy_engine = policy_engine or PolicyEngine()
        self.approval_gate = approval_gate or ApprovalGate(state_dir=registry_store.state_dir if registry_store else None)
        self.sandbox_engine = sandbox_engine or TeamSandboxPolicyEngine()
        self.sandbox_audit = sandbox_audit or TeamSandboxAuditStore(self.registry_store.state_dir)

    def dispatch(self, request: DispatchRequest) -> DispatchResult:
        run_id = request.run_id or f"run-{uuid4().hex[:12]}"
        role = self.role_registry.get(request.role)
        ok, reason = self.policy_engine.check_dispatch(role, request.toolsets)
        if not ok:
            result = DispatchResult(request.task_id, run_id, request.role, 'blocked', error=reason)
            self._record(request.task_id, run_id, request.role, 'team.dispatch_blocked', {'reason': reason})
            self.registry_store.bind_mapping(request.task_id, run_id=run_id, note=reason or '', source='hermes_team.dispatcher', status='blocked')
            return result

        approval = self.approval_gate.evaluate(
            task_id=request.task_id,
            run_id=run_id,
            role=request.role,
            goal=request.goal,
            context=request.context,
            toolsets=request.toolsets,
            metadata=request.metadata,
        )
        if not approval.allowed:
            result = DispatchResult(request.task_id, run_id, request.role, 'approval_pending', error=approval.reason, raw=approval.to_dict())
            self._record(request.task_id, run_id, request.role, 'team.approval_required', approval.to_dict())
            self.registry_store.bind_mapping(request.task_id, run_id=run_id, note=approval.reason or '', source='hermes_team.dispatcher', status='approval_pending')
            return result

        sandbox = self.sandbox_engine.derive(role=request.role, toolsets=request.toolsets or role.toolsets, metadata=request.metadata)
        self.sandbox_audit.append({
            'task_id': request.task_id,
            'run_id': run_id,
            'role': request.role,
            'policy': sandbox.to_dict(),
        })
        self._record(request.task_id, run_id, request.role, 'team.sandbox_applied', sandbox.to_dict())

        self._record(request.task_id, run_id, request.role, 'team.agent_started', {'goal': request.goal, 'sandbox': sandbox.to_dict()})
        started = time.perf_counter()
        try:
            runner_result = self.runner.run_role(role, request.goal, request.context, request.task_id, run_id)
            duration_ms = int((time.perf_counter() - started) * 1000)
            status = 'completed' if runner_result.status in {'completed', 'success', 'done'} else runner_result.status
            result = DispatchResult(
                task_id=request.task_id,
                run_id=run_id,
                role=request.role,
                status=status,
                summary=runner_result.summary,
                error=runner_result.error,
                session_id=runner_result.session_id,
                raw={**runner_result.raw, 'duration_ms': duration_ms, 'sandbox': sandbox.to_dict()},
            )
        except Exception as exc:  # keep team state recoverable
            duration_ms = int((time.perf_counter() - started) * 1000)
            result = DispatchResult(request.task_id, run_id, request.role, 'failed', error=str(exc), raw={'duration_ms': duration_ms, 'sandbox': sandbox.to_dict()})

        event_name = 'team.agent_completed' if result.status == 'completed' else 'team.agent_failed'
        self._record(request.task_id, run_id, request.role, event_name, result.to_dict())
        self.registry_store.bind_mapping(
            request.task_id,
            run_id=run_id,
            session_id=result.session_id,
            note=result.summary or result.error or '',
            source=f'hermes_team.{request.role}',
            status=result.status,
        )
        return result

    def dispatch_many(self, requests: list[DispatchRequest], max_concurrency: int | None = None) -> list[DispatchResult]:
        # MVP keeps deterministic sequential ordering; policy exposes concurrency for later parallel runner.
        return [self.dispatch(request) for request in requests]

    def _record(self, task_id: str, run_id: str, role: str, event: str, payload: dict[str, Any]) -> None:
        self.event_store.append(TeamEvent(event=event, task_id=task_id, run_id=run_id, role=role, payload=payload))
