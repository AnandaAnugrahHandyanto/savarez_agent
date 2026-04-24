from __future__ import annotations

from typing import Any

from agent.task_contracts import (
    ORCHESTRATION_HINTS_SCHEMA,
    ORCHESTRATION_HINTS_VERSION,
    validate_orchestration_hints,
    validate_task_contract,
)


def _request_text(raw_args: str | None) -> str:
    text = str(raw_args or "").strip()
    return text or "Perform deep initialization for the current task."


def build_init_deep_task_contract(*, raw_args: str, session_id: str | None, cwd: str | None) -> dict[str, Any]:
    """Build the structured contract for the /init-deep command.

    Kept in agent/ to avoid importing the CLI command-template module from the
    runtime activation tests while still giving /init-deep an execution-real
    contract builder.
    """
    request = _request_text(raw_args)
    return validate_task_contract(
        {
            "task": request,
            "expected_outcome": "A grounded initialization pass that maps the repo, task state, risks, and next execution steps.",
            "required_skills": ["repo-navigation", "planning", "verification"],
            "required_tools": ["read_file", "search_files", "terminal"],
            "must_do": [
                "inspect the active workspace before proposing or editing anything",
                "identify relevant files, tests, docs, and active task state",
                {"output": ["repo map", "risk list", "next execution plan"]},
            ],
            "must_not_do": [
                "do not modify files during initialization unless explicitly requested",
                "do not claim verification without fresh command output",
            ],
            "context": {
                "command": "init-deep",
                "request": request,
                "session_id": session_id,
                "cwd": cwd,
                "initialization_mode": "deep",
            },
        }
    ).model_dump()


def build_init_deep_hints(*, raw_args: str, session_id: str | None, cwd: str | None) -> dict[str, Any]:
    request = _request_text(raw_args)
    return validate_orchestration_hints(
        {
            "schema": ORCHESTRATION_HINTS_SCHEMA,
            "schema_version": ORCHESTRATION_HINTS_VERSION,
            "command": "init-deep",
            "loop_style": "single_pass",
            "request": request,
            "bounded_context": {
                "enabled": True,
                "max_hermes_hierarchy_files": 5,
                "task_contract_precedence": "preserve_existing_fields",
            },
            "invocation_metadata": {
                "command": "init-deep",
                "session_id": session_id,
                "cwd": cwd,
                "initialization_mode": "deep",
            },
        }
    ).model_dump()
