"""Janitor plugin for Hermes."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from . import cli as janitor_cli
from . import core
from . import tools as janitor_tools


def _skill_path() -> Path:
    return Path(__file__).resolve().parent / "skill" / "SKILL.md"


def _session_injection(*, messages: Any = None, conversation_history: Any = None, user_message: Any = None, **_: Any) -> Optional[str]:
    if not core.wants_injection(messages=messages, conversation_history=conversation_history, user_message=user_message):
        return None
    return core.build_injection()


def register(ctx) -> None:
    janitor_tools.register_toolset(ctx)
    ctx.register_hook("pre_llm_call", _session_injection)
    ctx.register_cli_command(
        name="janitor",
        help="Run senior-engineer cleanup workflows and daily repo janitor automation",
        setup_fn=janitor_cli.register_cli,
        handler_fn=lambda args: janitor_cli.dispatch_namespace(args, emit="print")[0],
        description="Hermes-native Janitor workflow for codebase cleanup, TDD proof gates, and daily GitHub repository sweeps.",
    )
    ctx.register_command(
        "janitor",
        handler=janitor_cli.handle_slash,
        description="Janitor workflow: /janitor start|review|story|run|proof|status|reset|daily-prompt",
        args_hint="start|review|story|run|proof|status|reset|daily-prompt",
    )
    ctx.register_skill(
        name="workflow",
        path=_skill_path(),
        description="Use Janitor cleanup workflows, TDD proof gates, and daily repository PR automation inside Hermes.",
    )
