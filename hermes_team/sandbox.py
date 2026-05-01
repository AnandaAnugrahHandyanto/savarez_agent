from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .json_store import JsonStateStore

TZ = timezone(timedelta(hours=8))


def _now_iso() -> str:
    return datetime.now(TZ).isoformat()


@dataclass
class TeamSandboxPolicy:
    """Runtime isolation and capability limits for a team role dispatch."""

    enabled: bool = True
    read_only: bool = False
    workspace: str | None = None
    allowed_paths: list[str] = field(default_factory=list)
    denied_paths: list[str] = field(default_factory=list)
    network: str = 'restricted'
    timeout_seconds: int | None = None
    max_iterations: int | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            'enabled': self.enabled,
            'read_only': self.read_only,
            'workspace': self.workspace,
            'allowed_paths': self.allowed_paths,
            'denied_paths': self.denied_paths,
            'network': self.network,
            'timeout_seconds': self.timeout_seconds,
            'max_iterations': self.max_iterations,
            'notes': self.notes,
        }


class TeamSandboxPolicyEngine:
    """Derive sandbox policy from role/toolsets/metadata without mutating live systems."""

    WRITE_TOOLSETS = {'terminal', 'file', 'browser', 'cronjob'}
    NETWORK_TOOLSETS = {'web', 'browser', 'mcp'}

    def derive(self, *, role: str, toolsets: list[str] | None, metadata: dict[str, Any] | None = None) -> TeamSandboxPolicy:
        metadata = dict(metadata or {})
        requested_toolsets = set(toolsets or [])
        sandbox_meta = dict(metadata.get('sandbox') or {})
        read_only = bool(sandbox_meta.get('read_only', role in {'reviewer', 'risk_officer'}))
        if requested_toolsets & self.WRITE_TOOLSETS and role not in {'executor'}:
            read_only = True
        network = str(sandbox_meta.get('network') or ('restricted' if requested_toolsets & self.NETWORK_TOOLSETS else 'disabled'))
        policy = TeamSandboxPolicy(
            enabled=bool(sandbox_meta.get('enabled', True)),
            read_only=read_only,
            workspace=sandbox_meta.get('workspace'),
            allowed_paths=[str(item) for item in sandbox_meta.get('allowed_paths', [])],
            denied_paths=[str(item) for item in sandbox_meta.get('denied_paths', [])],
            network=network,
            timeout_seconds=(int(sandbox_meta['timeout_seconds']) if sandbox_meta.get('timeout_seconds') else None),
            max_iterations=(int(sandbox_meta['max_iterations']) if sandbox_meta.get('max_iterations') else None),
        )
        if read_only:
            policy.notes.append('role is constrained to read-only review unless explicitly executed by executor')
        if network != 'open':
            policy.notes.append(f'network={network}')
        return policy


class TeamSandboxAuditStore(JsonStateStore):
    def __init__(self, state_dir: Path | None = None) -> None:
        super().__init__(state_dir)
        self.path = self.state_dir / 'sandbox_audit.json'

    def append(self, record: dict[str, Any]) -> dict[str, Any]:
        data = self._load_json(self.path, {'records': []})
        if not isinstance(data, dict):
            data = {'records': []}
        records = data.setdefault('records', [])
        enriched = {'created_at': _now_iso(), **record}
        records.append(enriched)
        self._save_json(self.path, data)
        return enriched

    def list(self, *, task_id: str | None = None, run_id: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
        data = self._load_json(self.path, {'records': []})
        records = data.get('records') if isinstance(data, dict) else []
        if not isinstance(records, list):
            return []
        if task_id:
            records = [item for item in records if item.get('task_id') == task_id]
        if run_id:
            records = [item for item in records if item.get('run_id') == run_id]
        if limit:
            records = records[-int(limit):]
        return records
