from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from .approval_store import ApprovalStore

TZ = timezone(timedelta(hours=8))
DANGEROUS_KEYWORDS = (
    'production', 'prod', 'deploy', 'credential', 'secret', 'api key', 'token',
    'financial', 'trade', 'trading', 'payment', 'delete', 'destructive', 'external',
    'send_message', 'webhook', 'real order', 'irreversible',
)
DANGEROUS_TOOLSETS = {'messaging', 'cronjob'}
DANGEROUS_ROLES = {'risk_officer'}


@dataclass
class ApprovalDecision:
    allowed: bool
    reason: str | None = None
    approval_id: str | None = None
    required: bool = False
    signals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            'allowed': self.allowed,
            'reason': self.reason,
            'approval_id': self.approval_id,
            'required': self.required,
            'signals': self.signals,
        }


class ApprovalGate:
    def __init__(self, store: ApprovalStore | None = None, state_dir: Any | None = None) -> None:
        self.store = store or ApprovalStore(state_dir)

    def evaluate(
        self,
        *,
        task_id: str,
        run_id: str,
        role: str,
        goal: str,
        context: str = '',
        toolsets: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ApprovalDecision:
        metadata = metadata or {}
        signals = self._signals(role=role, goal=goal, context=context, toolsets=toolsets or [], metadata=metadata)
        if not signals:
            return ApprovalDecision(allowed=True, signals=[])
        existing = self._find_approved(task_id=task_id, run_id=run_id, role=role)
        if existing:
            return ApprovalDecision(allowed=True, approval_id=existing.get('approval_id') or existing.get('approvalId'), signals=signals)
        approval_id = self._record_pending(task_id=task_id, run_id=run_id, role=role, goal=goal, signals=signals, metadata=metadata)
        return ApprovalDecision(
            allowed=False,
            required=True,
            approval_id=approval_id,
            reason=f'approval required for {role}: ' + ', '.join(signals),
            signals=signals,
        )

    def _signals(self, *, role: str, goal: str, context: str, toolsets: list[str], metadata: dict[str, Any]) -> list[str]:
        text = f'{goal}\n{context}\n{metadata}'.lower()
        safe_text = text.replace('non-production sandbox', 'sandbox').replace('production sandbox', 'sandbox').replace('non-production', '').replace('non production', '').replace('not production', '')
        signals = [f'keyword:{kw}' for kw in DANGEROUS_KEYWORDS if kw in safe_text]
        signals.extend(f'toolset:{toolset}' for toolset in toolsets if toolset in DANGEROUS_TOOLSETS)
        if role in DANGEROUS_ROLES:
            signals.append(f'role:{role}')
        if metadata.get('requires_approval') is True or metadata.get('risk') in {'high', 'critical'}:
            signals.append('metadata:requires_approval')
        return sorted(set(signals))

    def _find_approved(self, *, task_id: str, run_id: str, role: str) -> dict[str, Any] | None:
        for approval in self.store.list_approvals():
            status = str(approval.get('status') or '').lower()
            scope = approval.get('scope') or {}
            if status != 'approved':
                continue
            if scope.get('task_id') == task_id and scope.get('run_id') == run_id and scope.get('role') == role:
                return approval
        return None

    def _record_pending(self, *, task_id: str, run_id: str, role: str, goal: str, signals: list[str], metadata: dict[str, Any]) -> str:
        approval_id = f'apr-{uuid4().hex[:12]}'
        self.store.upsert({
            'approval_id': approval_id,
            'status': 'pending',
            'kind': 'team_dispatch',
            'scope': {'task_id': task_id, 'run_id': run_id, 'role': role},
            'reason': ', '.join(signals),
            'goal': goal,
            'metadata': metadata,
            'created_at': datetime.now(TZ).isoformat(),
            'updated_at': datetime.now(TZ).isoformat(),
        })
        return approval_id
