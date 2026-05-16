"""Strict prompt rendering for Symphony runner workflows."""

from __future__ import annotations

from os import PathLike
from typing import Any

from jinja2 import Environment, StrictUndefined, TemplateError

from symphony.errors import SymphonyError

_ENVIRONMENT = Environment(
    autoescape=False,
    undefined=StrictUndefined,
)


def render_prompt(template: str, **context: Any) -> str:
    """Render a workflow prompt template with strict undefined variables."""

    try:
        return _ENVIRONMENT.from_string(template).render(**context)
    except TemplateError as exc:
        raise SymphonyError(
            "template_render_error",
            f"Failed to render Symphony prompt template: {exc}",
        ) from exc


def build_runner_prompt(
    workflow_prompt_template: str,
    *,
    workspace_path: str | PathLike[str],
    evidence_dir: str | PathLike[str],
    issue: dict[str, Any] | None,
    attempt: int,
) -> str:
    """Build the final runner prompt with deterministic runtime context first."""

    issue_context: dict[str, Any] = issue or {}
    rendered_body = render_prompt(
        workflow_prompt_template,
        issue=issue_context,
        attempt=attempt,
    )

    prelude_lines = [
        "# Symphony Runtime Context",
        f"Workspace: {workspace_path}",
        f"Evidence directory: {evidence_dir}",
    ]

    identifier = issue_context.get("identifier")
    if identifier:
        prelude_lines.append(f"Issue identifier: {identifier}")

    title = issue_context.get("title")
    if title:
        prelude_lines.append(f"Issue title: {title}")

    prelude_lines.extend(
        [
            f"Attempt: {attempt}",
            "",
            "--- Workflow Prompt ---",
        ]
    )

    return "\n".join(prelude_lines) + "\n" + rendered_body
