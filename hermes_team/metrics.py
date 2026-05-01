from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from .approval_store import ApprovalStore
from .messages import TeamEventStore
from .orchestrator import TeamRunStore
from .registry_store import RegistryStore


@dataclass
class TeamMetrics:
    total_runs: int
    runs_by_status: dict[str, int] = field(default_factory=dict)
    total_events: int = 0
    events_by_name: dict[str, int] = field(default_factory=dict)
    approvals_by_status: dict[str, int] = field(default_factory=dict)
    registry_tasks: int = 0
    total_duration_ms: int = 0
    average_duration_ms: float = 0.0
    duration_by_role_ms: dict[str, dict[str, float]] = field(default_factory=dict)
    total_estimated_cost_usd: float = 0.0
    estimated_cost_by_role_usd: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'total_runs': self.total_runs,
            'runs_by_status': self.runs_by_status,
            'total_events': self.total_events,
            'events_by_name': self.events_by_name,
            'approvals_by_status': self.approvals_by_status,
            'registry_tasks': self.registry_tasks,
            'total_duration_ms': self.total_duration_ms,
            'average_duration_ms': self.average_duration_ms,
            'duration_by_role_ms': self.duration_by_role_ms,
            'total_estimated_cost_usd': self.total_estimated_cost_usd,
            'estimated_cost_by_role_usd': self.estimated_cost_by_role_usd,
        }


class TeamMetricsStore:
    def __init__(self, state_dir: Any | None = None) -> None:
        self.run_store = TeamRunStore(state_dir)
        self.event_store = TeamEventStore(state_dir)
        self.approval_store = ApprovalStore(state_dir)
        self.registry_store = RegistryStore(state_dir)

    def snapshot(self) -> TeamMetrics:
        runs = list((self.run_store.load().get('runs') or {}).values())
        events = self.event_store.list()
        approvals = self.approval_store.list_approvals()
        registry = self.registry_store.load()
        duration_values: list[int] = []
        role_durations: dict[str, list[int]] = {}
        cost_by_role: Counter[str] = Counter()
        total_cost = 0.0
        for run in runs:
            for step in run.get('steps') or []:
                role = str(step.get('role') or 'unknown')
                raw = step.get('raw') if isinstance(step.get('raw'), dict) else {}
                duration = raw.get('duration_ms')
                if isinstance(duration, (int, float)):
                    duration_ms = int(duration)
                    duration_values.append(duration_ms)
                    role_durations.setdefault(role, []).append(duration_ms)
                usage = raw.get('usage') if isinstance(raw.get('usage'), dict) else {}
                cost = usage.get('cost_usd') or usage.get('estimated_cost_usd') or raw.get('cost_usd') or raw.get('estimated_cost_usd')
                if isinstance(cost, (int, float)):
                    total_cost += float(cost)
                    cost_by_role[role] += float(cost)
        duration_by_role = {
            role: {
                'count': len(values),
                'total': float(sum(values)),
                'average': float(sum(values) / len(values)) if values else 0.0,
            }
            for role, values in role_durations.items()
        }
        return TeamMetrics(
            total_runs=len(runs),
            runs_by_status=dict(Counter(str(run.get('status') or 'unknown') for run in runs)),
            total_events=len(events),
            events_by_name=dict(Counter(str(event.get('event') or 'unknown') for event in events)),
            approvals_by_status=dict(Counter(str(approval.get('status') or 'unknown') for approval in approvals)),
            registry_tasks=len(registry.get('tasks') or {}),
            total_duration_ms=sum(duration_values),
            average_duration_ms=(sum(duration_values) / len(duration_values) if duration_values else 0.0),
            duration_by_role_ms=duration_by_role,
            total_estimated_cost_usd=round(total_cost, 8),
            estimated_cost_by_role_usd={role: round(float(cost), 8) for role, cost in cost_by_role.items()},
        )
