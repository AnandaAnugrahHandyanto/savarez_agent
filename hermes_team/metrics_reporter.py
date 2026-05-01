from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from statistics import mean
from typing import Any

from .metrics import TeamMetricsStore
from .orchestrator import TeamRunStore


@dataclass
class TeamMetricsReport:
    snapshot: dict[str, Any]
    runs_by_role_status: dict[str, dict[str, int]] = field(default_factory=dict)
    average_steps_per_run: float = 0.0
    failure_reasons: dict[str, int] = field(default_factory=dict)
    approval_pressure: int = 0
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            'snapshot': self.snapshot,
            'runs_by_role_status': self.runs_by_role_status,
            'average_steps_per_run': self.average_steps_per_run,
            'failure_reasons': self.failure_reasons,
            'approval_pressure': self.approval_pressure,
            'recommendations': self.recommendations,
        }


class TeamMetricsReporter:
    def __init__(self, state_dir: Any | None = None) -> None:
        self.metrics = TeamMetricsStore(state_dir)
        self.runs = TeamRunStore(state_dir)

    def report(self) -> TeamMetricsReport:
        snapshot = self.metrics.snapshot().to_dict()
        run_rows = list((self.runs.load().get('runs') or {}).values())
        role_status: dict[str, Counter[str]] = defaultdict(Counter)
        failure_reasons: Counter[str] = Counter()
        step_counts: list[int] = []
        for run in run_rows:
            steps = list(run.get('steps') or [])
            step_counts.append(len(steps))
            for step in steps:
                role_status[str(step.get('role') or 'unknown')][str(step.get('status') or 'unknown')] += 1
                if step.get('status') != 'completed':
                    failure_reasons[str(step.get('error') or step.get('status') or 'unknown')] += 1
            for err in run.get('errors') or []:
                failure_reasons[str(err)] += 1
        recommendations: list[str] = []
        approvals_pending = int(snapshot.get('approvals_by_status', {}).get('pending', 0))
        if approvals_pending:
            recommendations.append(f'{approvals_pending} pending approvals need explicit human decision')
        failed_runs = int(snapshot.get('runs_by_status', {}).get('failed', 0))
        if failed_runs:
            recommendations.append('inspect failed runs with team_watch and trigger bounded replan only for non-approval failures')
        if not run_rows:
            recommendations.append('no team runs recorded yet')
        return TeamMetricsReport(
            snapshot=snapshot,
            runs_by_role_status={role: dict(counter) for role, counter in role_status.items()},
            average_steps_per_run=mean(step_counts) if step_counts else 0.0,
            failure_reasons=dict(failure_reasons),
            approval_pressure=approvals_pending,
            recommendations=recommendations,
        )
