from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from .roles import TeamRole


@dataclass
class TeamRunnerResult:
    status: str
    summary: str = ''
    session_id: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class RoleExecutor(Protocol):
    def __call__(self, role: TeamRole, goal: str, context: str, task_id: str | None, run_id: str | None) -> TeamRunnerResult | dict[str, Any]:
        ...


class TeamRunner:
    """Execute a Hermes team role.

    The default path uses AIAgent lazily. Tests and higher-level orchestrators can inject
    a deterministic executor to avoid real LLM calls.
    """

    def __init__(self, executor: RoleExecutor | None = None) -> None:
        self.executor = executor

    def run_role(
        self,
        role: TeamRole,
        goal: str,
        context: str = '',
        task_id: str | None = None,
        run_id: str | None = None,
    ) -> TeamRunnerResult:
        if self.executor is not None:
            return self._normalize(self.executor(role, goal, context, task_id, run_id))
        return self._run_with_ai_agent(role, goal, context, task_id, run_id)

    def _run_with_ai_agent(self, role: TeamRole, goal: str, context: str, task_id: str | None, run_id: str | None) -> TeamRunnerResult:
        from run_agent import AIAgent  # Lazy import keeps store-only tests lightweight.

        system_message = f"{role.system_prompt}\n\nTeam role: {role.name}\nRun ID: {run_id or 'n/a'}\nTask ID: {task_id or 'n/a'}\nContext:\n{context}".strip()
        agent = AIAgent(
            model=role.model,
            provider=role.provider,
            max_iterations=role.max_iterations,
            enabled_toolsets=role.toolsets,
            skip_memory=True,
            skip_context_files=True,
        )
        raw = agent.run_conversation(user_message=goal, system_message=system_message, task_id=task_id)
        summary = raw.get('final_response') or raw.get('response') or raw.get('summary') or ''
        enriched = dict(raw)
        usage = enriched.setdefault('usage', {}) if isinstance(enriched.get('usage', {}), dict) else {}
        for source_key, target_key in (
            ('estimated_cost_usd', 'estimated_cost_usd'),
            ('cost_usd', 'cost_usd'),
            ('total_tokens', 'total_tokens'),
            ('input_tokens', 'input_tokens'),
            ('output_tokens', 'output_tokens'),
        ):
            if source_key in raw and target_key not in usage:
                usage[target_key] = raw[source_key]
        if usage:
            enriched['usage'] = usage
        return TeamRunnerResult(status='completed', summary=str(summary), session_id=getattr(agent, 'session_id', None), raw=enriched)

    @staticmethod
    def _normalize(result: TeamRunnerResult | dict[str, Any]) -> TeamRunnerResult:
        if isinstance(result, TeamRunnerResult):
            return result
        status = str(result.get('status') or 'completed')
        return TeamRunnerResult(
            status=status,
            summary=str(result.get('summary') or result.get('final_response') or ''),
            session_id=result.get('session_id') or result.get('sessionId'),
            raw=dict(result),
            error=result.get('error'),
        )
