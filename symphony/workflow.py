"""Workflow loading utilities for Symphony orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from symphony.errors import SymphonyError


@dataclass(frozen=True, slots=True)
class Workflow:
    """Loaded Symphony workflow definition."""

    config: dict[str, Any]
    prompt_template: str


def resolve_workflow_path(raw_path: str | Path | None, cwd: str | Path | None = None) -> Path:
    """Resolve and validate a workflow path.

    An explicit path is used when provided. Otherwise ``WORKFLOW.md`` in *cwd*
    (or the current working directory) is used.
    """

    base_dir = Path(cwd) if cwd is not None else Path.cwd()
    if raw_path is None:
        path = base_dir / "WORKFLOW.md"
    else:
        path = Path(raw_path)
        if not path.is_absolute():
            path = base_dir / path

    if not path.exists():
        raise SymphonyError(
            "missing_workflow_file",
            f"Symphony workflow file not found: {path}",
        )
    return path


def load_workflow(path: str | Path) -> Workflow:
    """Load a Symphony ``WORKFLOW.md`` file."""

    workflow_path = resolve_workflow_path(path)
    content = workflow_path.read_text(encoding="utf-8")
    config, body = _split_front_matter(content)
    return Workflow(config=config, prompt_template=body.strip())


def _split_front_matter(content: str) -> tuple[dict[str, Any], str]:
    if not content.startswith("---"):
        return {}, content

    lines = content.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, content

    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            front_matter = "".join(lines[1:index])
            body = "".join(lines[index + 1 :])
            try:
                loaded = yaml.safe_load(front_matter) if front_matter.strip() else {}
            except yaml.YAMLError as exc:
                raise SymphonyError(
                    "workflow_front_matter_invalid_yaml",
                    f"Workflow front matter is not valid YAML: {exc}",
                ) from exc
            if loaded is None:
                loaded = {}
            if not isinstance(loaded, dict):
                raise SymphonyError(
                    "workflow_front_matter_not_a_map",
                    "Workflow front matter must be a YAML mapping at the root.",
                )
            return loaded, body

    return {}, content
