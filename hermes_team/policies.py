from __future__ import annotations

from dataclasses import dataclass, field

from .roles import TeamRole


@dataclass
class TeamPolicy:
    max_concurrency: int = 3
    max_spawn_depth: int = 2
    child_timeout_seconds: int = 300
    require_review: bool = True
    allowed_toolsets_by_role: dict[str, list[str]] = field(default_factory=dict)


class PolicyEngine:
    def __init__(self, policy: TeamPolicy | None = None) -> None:
        self.policy = policy or TeamPolicy()

    def check_toolsets(self, role: TeamRole, requested: list[str] | None = None) -> list[str]:
        requested_toolsets = list(requested if requested is not None else role.toolsets)
        allowed = self.policy.allowed_toolsets_by_role.get(role.name)
        if allowed is None:
            allowed = role.toolsets
        return [toolset for toolset in requested_toolsets if toolset in allowed]

    def check_dispatch(self, role: TeamRole, requested_toolsets: list[str] | None = None) -> tuple[bool, str | None]:
        if role.requires_approval:
            return False, f'role requires approval: {role.name}'
        filtered = self.check_toolsets(role, requested_toolsets)
        if requested_toolsets is not None and set(filtered) != set(requested_toolsets):
            return False, f'toolset not allowed for role {role.name}'
        return True, None
