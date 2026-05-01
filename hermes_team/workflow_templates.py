from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .orchestrator import TeamRunSpec


@dataclass(frozen=True)
class WorkflowTemplate:
    name: str
    description: str
    mode: str = 'sequential'
    roles: list[str] = field(default_factory=list)
    graph: list[dict[str, Any]] | None = None
    parallel: bool = False
    max_concurrency: int | None = None
    require_review: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'name': self.name,
            'description': self.description,
            'mode': self.mode,
            'roles': list(self.roles),
            'graph': [dict(node) for node in self.graph] if self.graph else None,
            'parallel': self.parallel,
            'max_concurrency': self.max_concurrency,
            'require_review': self.require_review,
            'metadata': dict(self.metadata),
        }


class WorkflowTemplateRegistry:
    def __init__(self, templates: dict[str, WorkflowTemplate] | None = None) -> None:
        self._templates = templates or _DEFAULT_TEMPLATES

    @classmethod
    def default(cls) -> 'WorkflowTemplateRegistry':
        return cls(_DEFAULT_TEMPLATES)

    def get(self, name: str) -> WorkflowTemplate:
        key = (name or '').strip()
        if key not in self._templates:
            raise KeyError(f'unknown team workflow template: {name}')
        return self._templates[key]

    def list_templates(self) -> list[WorkflowTemplate]:
        return [self._templates[name] for name in sorted(self._templates)]


def apply_workflow_template(
    name: str,
    *,
    goal: str,
    context: str = '',
    task_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> TeamRunSpec:
    template = WorkflowTemplateRegistry.default().get(name)
    merged_metadata = dict(template.metadata)
    merged_metadata.update(metadata or {})
    merged_metadata['template'] = template.name
    return TeamRunSpec(
        goal=goal,
        task_id=task_id,
        mode=template.mode,
        roles=list(template.roles),
        graph=[dict(node) for node in template.graph] if template.graph else None,
        context=context,
        require_review=template.require_review,
        parallel=template.parallel,
        max_concurrency=template.max_concurrency,
        metadata=merged_metadata,
    )


_DEFAULT_TEMPLATES: dict[str, WorkflowTemplate] = {
    'implementation_review': WorkflowTemplate(
        name='implementation_review',
        description='Planner -> executor -> reviewer for bounded implementation tasks.',
        mode='sequential',
        roles=['planner', 'executor', 'reviewer'],
        require_review=True,
    ),
    'research_plan_execute': WorkflowTemplate(
        name='research_plan_execute',
        description='Researcher -> planner -> executor -> reviewer for evidence-backed execution.',
        mode='sequential',
        roles=['researcher', 'planner', 'executor', 'reviewer'],
        require_review=True,
    ),
    'parallel_audit': WorkflowTemplate(
        name='parallel_audit',
        description='Parallel security/test/docs audit with reviewer synthesis.',
        mode='dag',
        parallel=True,
        max_concurrency=3,
        require_review=False,
        graph=[
            {'id': 'security', 'role': 'reviewer', 'goal': 'Audit security and approval-gate risks for the objective.'},
            {'id': 'tests', 'role': 'reviewer', 'goal': 'Audit test coverage, regressions, and verification gaps for the objective.'},
            {'id': 'docs', 'role': 'reviewer', 'goal': 'Audit documentation and operator-facing usability for the objective.'},
            {
                'id': 'synthesis',
                'role': 'planner',
                'goal': 'Synthesize audit findings into prioritized remediation steps and stop/no-stop recommendation.',
                'depends_on': ['security', 'tests', 'docs'],
            },
        ],
    ),
}
