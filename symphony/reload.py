"""Tick-boundary workflow reload support for Symphony."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from symphony.config import SymphonyConfig, load_config
from symphony.errors import SymphonyError
from symphony.workflow import Workflow, load_workflow, resolve_workflow_path

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class WorkflowReloader:
    """Small helper that reloads a workflow only when its file mtime changes."""

    path: Path
    workflow: Workflow
    config: SymphonyConfig
    last_mtime_ns: int
    env: Mapping[str, str] | None = None
    last_error: SymphonyError | None = None

    def __init__(self, path: str | Path, *, env: Mapping[str, str] | None = None) -> None:
        resolved_path = resolve_workflow_path(path)
        workflow = load_workflow(resolved_path)
        config = load_config(workflow.config, workflow_dir=resolved_path.parent, env=env)

        self.path = resolved_path
        self.workflow = workflow
        self.config = config
        self.last_mtime_ns = resolved_path.stat().st_mtime_ns
        self.env = env
        self.last_error = None

    def reload_if_changed(self) -> bool:
        """Reload at a tick boundary if the workflow file changed.

        Returns ``True`` only when a changed file is loaded and validated. Invalid
        reloads keep the last good workflow/config active, expose ``last_error``,
        and do not raise.
        """

        observed_mtime_ns = self.path.stat().st_mtime_ns
        if observed_mtime_ns == self.last_mtime_ns:
            return False

        self.last_mtime_ns = observed_mtime_ns
        try:
            workflow = load_workflow(self.path)
            config = load_config(workflow.config, workflow_dir=self.path.parent, env=self.env)
        except SymphonyError as exc:
            self.last_error = exc
            logger.error("Symphony workflow reload failed: %s", exc.to_payload())
            return False

        self.workflow = workflow
        self.config = config
        self.last_error = None
        return True


ReloadableWorkflow = WorkflowReloader
