from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from .approval_store import ApprovalStore


@dataclass
class ApprovalAuditReport:
    total: int
    by_status: dict[str, int] = field(default_factory=dict)
    by_kind: dict[str, int] = field(default_factory=dict)
    pending: list[dict[str, Any]] = field(default_factory=list)
    stale_pending: list[dict[str, Any]] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            'total': self.total,
            'by_status': self.by_status,
            'by_kind': self.by_kind,
            'pending': self.pending,
            'stale_pending': self.stale_pending,
            'risks': self.risks,
        }


class ApprovalAuditReporter:
    def __init__(self, state_dir: Any | None = None) -> None:
        self.store = ApprovalStore(state_dir)

    def report(self) -> ApprovalAuditReport:
        approvals = self.store.list_approvals()
        by_status = Counter(str(item.get('status') or 'unknown') for item in approvals)
        by_kind = Counter(str(item.get('kind') or 'unknown') for item in approvals)
        pending = [item for item in approvals if str(item.get('status') or '').lower() == 'pending']
        risks: list[str] = []
        for item in pending:
            if not item.get('reason'):
                risks.append(f"pending approval {item.get('approval_id')} has no reason")
            scope = item.get('scope') or {}
            if not scope.get('task_id') or not scope.get('run_id'):
                risks.append(f"pending approval {item.get('approval_id')} has incomplete scope")
        return ApprovalAuditReport(
            total=len(approvals),
            by_status=dict(by_status),
            by_kind=dict(by_kind),
            pending=pending,
            stale_pending=[],
            risks=risks,
        )
