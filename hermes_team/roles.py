from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TeamRole:
    """Hermes-native team role definition."""

    name: str
    description: str
    system_prompt: str
    toolsets: list[str] = field(default_factory=list)
    model: str | None = None
    provider: str | None = None
    max_iterations: int = 30
    can_delegate: bool = False
    requires_approval: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


DEFAULT_ROLES: dict[str, TeamRole] = {
    'cio': TeamRole(
        name='cio',
        description='Team coordinator: triage, route, and synthesize work.',
        system_prompt='You are the Hermes team coordinator. Clarify objectives, route work, and summarize verified outcomes.',
        toolsets=['delegation'],
        can_delegate=True,
    ),
    'researcher': TeamRole(
        name='researcher',
        description='Gather evidence, compare options, and report concise findings.',
        system_prompt='You are a Hermes researcher. Gather evidence and return sourced, concise findings.',
        toolsets=['web', 'file'],
    ),
    'planner': TeamRole(
        name='planner',
        description='Break objectives into executable, verifiable steps.',
        system_prompt='You are a Hermes planner. Produce a bounded, verifiable execution plan.',
        toolsets=['file'],
    ),
    'executor': TeamRole(
        name='executor',
        description='Execute implementation or operational tasks and verify results.',
        system_prompt='You are a Hermes executor. Implement the requested work and verify the result with real outputs.',
        toolsets=['terminal', 'file'],
    ),
    'reviewer': TeamRole(
        name='reviewer',
        description='Review outputs for spec compliance, quality, and risk.',
        system_prompt='You are a Hermes reviewer. Check spec compliance, quality, regressions, and risk. Return PASS or actionable gaps.',
        toolsets=['terminal', 'file'],
    ),
    'risk_officer': TeamRole(
        name='risk_officer',
        description='Evaluate destructive, production, credential, financial, or external side effects.',
        system_prompt='You are a Hermes risk officer. Approve only bounded safe actions and flag required human confirmation.',
        toolsets=[],
        requires_approval=True,
    ),
}


class RoleRegistry:
    """In-memory registry for Hermes team roles."""

    def __init__(self, roles: dict[str, TeamRole] | None = None) -> None:
        self._roles: dict[str, TeamRole] = dict(roles or DEFAULT_ROLES)

    @classmethod
    def default(cls) -> 'RoleRegistry':
        return cls(DEFAULT_ROLES)

    def register(self, role: TeamRole) -> None:
        if not role.name:
            raise ValueError('role name is required')
        self._roles[role.name] = role

    def get(self, name: str) -> TeamRole:
        try:
            return self._roles[name]
        except KeyError as exc:
            raise KeyError(f'unknown team role: {name}') from exc

    def list(self) -> list[TeamRole]:
        return [self._roles[name] for name in sorted(self._roles)]

    def names(self) -> list[str]:
        return sorted(self._roles)
