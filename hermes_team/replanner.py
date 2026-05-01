from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .json_store import JsonStateStore
from .messages import TeamEvent, TeamEventStore

if TYPE_CHECKING:
    from .orchestrator import TeamRunSpec

TZ = timezone(timedelta(hours=8))


def _now_iso() -> str:
    return datetime.now(TZ).isoformat()


@dataclass
class ReplanDecision:
    needed: bool
    reason: str = ''
    spec: Any | None = None
    proposed_graph: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            'needed': self.needed,
            'reason': self.reason,
            'spec': None if self.spec is None else {
                'goal': self.spec.goal,
                'task_id': self.spec.task_id,
                'mode': self.spec.mode,
                'roles': self.spec.roles,
                'graph': self.spec.graph,
                'context': self.spec.context,
                'require_review': self.spec.require_review,
                'parallel': self.spec.parallel,
                'max_concurrency': self.spec.max_concurrency,
                'metadata': self.spec.metadata,
            },
            'proposed_graph': self.proposed_graph,
        }


class ReplanStore(JsonStateStore):
    def __init__(self, state_dir: Path | None = None) -> None:
        super().__init__(state_dir)
        self.path = self.state_dir / 'replans.json'

    def append(self, record: dict[str, Any]) -> dict[str, Any]:
        data = self._load_json(self.path, {'replans': []})
        if not isinstance(data, dict):
            data = {'replans': []}
        enriched = {'created_at': _now_iso(), **record}
        data.setdefault('replans', []).append(enriched)
        self._save_json(self.path, data)
        return enriched

    def list(self, *, task_id: str | None = None, run_id: str | None = None) -> list[dict[str, Any]]:
        data = self._load_json(self.path, {'replans': []})
        rows = data.get('replans') if isinstance(data, dict) else []
        if not isinstance(rows, list):
            return []
        if task_id:
            rows = [row for row in rows if row.get('task_id') == task_id]
        if run_id:
            rows = [row for row in rows if row.get('run_id') == run_id]
        return rows


class TeamReplanner:
    """Create bounded follow-up specs for failed non-approval team runs."""

    def __init__(self, state_dir: Path | None = None) -> None:
        self.store = ReplanStore(state_dir)
        self.events = TeamEventStore(state_dir)

    def evaluate(self, result: Any, original: 'TeamRunSpec') -> ReplanDecision:
        status = str(getattr(result, 'status', '') or '')
        errors = list(getattr(result, 'errors', []) or [])
        if status == 'completed':
            return ReplanDecision(False, 'run completed')
        if any('approval' in str(error).lower() for error in errors):
            return ReplanDecision(False, 'approval gate pending; human decision required')
        attempts = int((original.metadata or {}).get('replan_attempt', 0))
        max_attempts = int((original.metadata or {}).get('max_replan_attempts', 1))
        if attempts >= max_attempts:
            return ReplanDecision(False, f'max replan attempts reached: {attempts}/{max_attempts}')
        failed_roles = [str(step.get('role')) for step in getattr(result, 'steps', []) if step.get('status') != 'completed']
        if not failed_roles:
            failed_roles = ['executor']
        graph = [
            {
                'id': 'root-cause',
                'role': 'planner',
                'goal': f"Analyze failed team run in a sandbox and return the smallest corrective plan: {original.goal}",
                'context': '\n'.join(errors),
            },
            {
                'id': 'repair',
                'role': 'executor',
                'goal': f"Repair failed roles {failed_roles} for objective: {original.goal}",
                'depends_on': ['root-cause'],
                'context': original.context,
                'metadata': {'replan_repair': True},
            },
            {
                'id': 'verify',
                'role': 'reviewer',
                'goal': f"Verify the repair fully satisfies the original objective: {original.goal}",
                'depends_on': ['repair'],
            },
        ]
        from .orchestrator import TeamRunSpec

        spec = TeamRunSpec(
            goal=f"Replan recovery for failed run: {original.goal}",
            task_id=getattr(result, 'task_id', original.task_id),
            mode='dag',
            roles=['planner', 'executor', 'reviewer'],
            graph=graph,
            context=original.context,
            require_review=True,
            parallel=False,
            max_concurrency=original.max_concurrency,
            metadata={**(original.metadata or {}), 'replan_attempt': attempts + 1, 'parent_run_id': getattr(result, 'run_id', None)},
        )
        return ReplanDecision(True, f'failed run recovery for roles: {failed_roles}', spec=spec, proposed_graph=graph)

    def record(self, *, task_id: str, run_id: str, decision: ReplanDecision) -> dict[str, Any]:
        record = self.store.append({'task_id': task_id, 'run_id': run_id, 'decision': decision.to_dict()})
        self.events.append(TeamEvent(event='team.replan_proposed' if decision.needed else 'team.replan_skipped', task_id=task_id, run_id=run_id, payload=record))
        return record
