"""Tool registrations for Janitor."""

from __future__ import annotations

import json
from typing import Any

from . import core

TOOLSET = "janitor"


def _json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def _handler(fn):
    return lambda args, **kw: _json(fn(**(args or {})))


def register_toolset(ctx) -> None:
    ctx.register_tool(
        name="janitor_start",
        toolset=TOOLSET,
        description="Start a Senior Engineer Benchmark-inspired cleanup workflow for vibe-coded or slop-coded codebases.",
        schema={
            "name": "janitor_start",
            "description": "Start a senior-engineer janitor workflow for slop-code cleanup and first-principles rewrites.",
            "parameters": {
                "type": "object",
                "properties": {
                    "goal": {"type": "string", "description": "Cleanup outcome to achieve."},
                    "codebase_path": {"type": "string", "description": "Repository or subsystem path."},
                    "symptoms": {"type": "string", "description": "Comma/newline separated failures, production symptoms, or code smells."},
                    "constraints": {"type": "string", "description": "Comma/newline separated constraints, contracts, or risk boundaries."},
                    "rewrite_policy": {"type": "string", "default": "first-principles-when-needed"},
                },
            },
        },
        handler=_handler(core.janitor),
    )
    ctx.register_tool(
        name="janitor_review",
        toolset=TOOLSET,
        description="Apply the Senior Engineer Benchmark scorecard to a cleanup plan or completed rewrite.",
        schema={
            "name": "janitor_review",
            "description": "Return the janitor-mode scorecard, review questions, and pass standard for senior-engineer cleanup work.",
            "parameters": {
                "type": "object",
                "properties": {
                    "evidence": {"type": "string", "description": "Comma/newline separated evidence items to review."},
                    "notes": {"type": "string", "description": "Free-form assessment notes or plan summary."},
                },
            },
        },
        handler=_handler(core.janitor_review),
    )
    ctx.register_tool(
        name="janitor_story",
        toolset=TOOLSET,
        description="Add an acceptance-testable Janitor implementation story.",
        schema={
            "name": "janitor_story",
            "description": "Create a Janitor implementation story with acceptance criteria.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "acceptance": {"type": "string", "description": "Comma/newline separated acceptance criteria."},
                    "notes": {"type": "string"},
                    "priority": {"type": "string", "default": "normal"},
                },
                "required": ["title", "acceptance"],
            },
        },
        handler=_handler(core.add_story),
    )
    ctx.register_tool(
        name="janitor_run",
        toolset=TOOLSET,
        description="Prepare explicit Janitor story handoff payloads for execution/delegation.",
        schema={
            "name": "janitor_run",
            "description": "Prepare Janitor execution handoffs for selected stories.",
            "parameters": {
                "type": "object",
                "properties": {
                    "parallelism": {"type": "integer", "default": 1},
                    "story_ids": {"type": "string", "description": "Optional comma separated story ids."},
                },
            },
        },
        handler=_handler(core.prepare_run),
    )
    ctx.register_tool(
        name="janitor_proof",
        toolset=TOOLSET,
        description="Record tests, files, logs, traces, and other proof evidence for Janitor proof gates.",
        schema={
            "name": "janitor_proof",
            "description": "Record proof evidence for a Janitor story or workflow.",
            "parameters": {
                "type": "object",
                "properties": {
                    "evidence": {"type": "string", "description": "Comma/newline separated evidence items."},
                    "tests": {"type": "string", "description": "Comma/newline separated test/log/trace commands or results."},
                    "files": {"type": "string", "description": "Comma/newline separated relevant files."},
                    "story_id": {"type": "string"},
                },
            },
        },
        handler=_handler(core.record_proof),
    )
    ctx.register_tool(
        name="janitor_status",
        toolset=TOOLSET,
        description="Inspect persisted Janitor workflow state and proof gate status.",
        schema={"name": "janitor_status", "description": "Return Janitor workflow state.", "parameters": {"type": "object", "properties": {}}},
        handler=_handler(core.status),
    )
    ctx.register_tool(
        name="janitor_reset",
        toolset=TOOLSET,
        description="Clear Janitor workflow state.",
        schema={"name": "janitor_reset", "description": "Reset Janitor workflow state.", "parameters": {"type": "object", "properties": {}}},
        handler=_handler(core.reset),
    )
    ctx.register_tool(
        name="janitor_daily_prompt",
        toolset=TOOLSET,
        description="Build the daily GitHub Janitor sweep prompt for repos with charges or recent activity.",
        schema={
            "name": "janitor_daily_prompt",
            "description": "Return a self-contained daily Janitor cron prompt for GitHub repositories with charges in a lookback window.",
            "parameters": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "default": "crisweber2600"},
                    "lookback_hours": {"type": "integer", "default": 24},
                    "schedule": {"type": "string", "default": "0 9 * * *"},
                },
            },
        },
        handler=_handler(core.daily_prompt),
    )
