from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .approval_store import ApprovalStore
from .messages import TeamEvent, TeamEventStore
from .registry_store import RegistryStore

TZ = timezone(timedelta(hours=8))


def _now_iso() -> str:
    return datetime.now(TZ).isoformat()


class TeamApprovalManager:
    """Approve/reject Hermes team pending approvals without bypassing audit state."""

    def __init__(self, state_dir: Path | None = None) -> None:
        self.store = ApprovalStore(state_dir)
        self.events = TeamEventStore(self.store.state_dir)
        self.registry = RegistryStore(self.store.state_dir)

    def list(self, status: str | None = None) -> list[dict[str, Any]]:
        approvals = self.store.list_approvals()
        if status:
            approvals = [item for item in approvals if str(item.get('status') or '').lower() == status.lower()]
        return approvals

    def decide(self, approval_id: str, *, decision: str, by: str = 'hermes_team.approval_manager', reason: str = '') -> dict[str, Any]:
        normalized = decision.lower().strip()
        if normalized not in {'approved', 'rejected'}:
            raise ValueError("decision must be 'approved' or 'rejected'")
        approvals = self.store.list_approvals()
        for index, approval in enumerate(approvals):
            if approval.get('approval_id') != approval_id and approval.get('approvalId') != approval_id:
                continue
            updated = {
                **approval,
                'status': normalized,
                'decided_by': by,
                'decision_reason': reason,
                'updated_at': _now_iso(),
                'decided_at': _now_iso(),
            }
            approvals[index] = updated
            self.store.save(approvals)
            scope = updated.get('scope') or {}
            task_id = str(scope.get('task_id') or '')
            run_id = str(scope.get('run_id') or '')
            role = str(scope.get('role') or '')
            if task_id and run_id:
                event = 'team.approval_approved' if normalized == 'approved' else 'team.approval_rejected'
                self.events.append(TeamEvent(event=event, task_id=task_id, run_id=run_id, role=role or None, payload=updated))
                self.registry.update_mapping_status(
                    task_id,
                    'approved' if normalized == 'approved' else 'rejected',
                    note=reason or f'approval {normalized}: {approval_id}',
                    source=by,
                )
            return updated
        raise KeyError(f'approval not found: {approval_id}')
