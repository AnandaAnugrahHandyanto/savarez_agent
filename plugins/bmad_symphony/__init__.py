"""BMad/Symphony plugin — deep planning + isolated implementation runs.

This plugin combines:
- a planning/intake layer (BMad)
- a Symphony execution brief / worker fan-out layer
- a proof-of-work gate that keeps handoffs honest
- a plugin-local skill that teaches the agent when to use the workflow
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from . import core
from . import cli as workflow_cli
from . import tools as workflow_tools

logger = logging.getLogger(__name__)


def _skill_path() -> Path:
    return Path(__file__).resolve().parent / "skill" / "SKILL.md"


def _session_injection(*, messages: Any = None, conversation_history: Any = None, user_message: Any = None, **_: Any) -> Optional[str]:
    if not core.wants_injection(
        messages=messages,
        conversation_history=conversation_history,
        user_message=user_message,
    ):
        return None
    return core.build_injection()


def _session_end(*_: Any, **__: Any) -> None:
    try:
        core.record_event("session_end", "BMad/Symphony session ended")
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("bmad-symphony session_end hook failed: %s", exc)


def register(ctx) -> None:
    """Register tools, hooks, CLI commands, slash commands, and the plugin skill."""
    workflow_tools.register_toolset(ctx)

    ctx.register_hook("pre_llm_call", _session_injection)
    ctx.register_hook("on_session_end", _session_end)

    ctx.register_cli_command(
        name="bmad-symphony",
        help="BMad planning + Symphony implementation runs",
        setup_fn=workflow_cli.register_cli,
        handler_fn=lambda args: workflow_cli.dispatch_namespace(
            args,
            dispatcher=ctx.dispatch_tool,
            emit="print",
        )[0],
        description=(
            "Create a BMad intake, turn it into a story, fan out Symphony "
            "workers, and evaluate proof-of-work before handoff."
        ),
    )

    ctx.register_command(
        "bmad-symphony",
        handler=lambda raw_args: workflow_cli.handle_slash(
            raw_args,
            dispatcher=ctx.dispatch_tool,
        ),
        description=(
            "BMad/Symphony workflow: /bmad-symphony plan|story|run|proof|status|reset"
        ),
        args_hint="plan|story|run|proof|status|reset",
    )

    ctx.register_command(
        "bmad",
        handler=lambda raw_args: workflow_cli.handle_slash(
            raw_args,
            dispatcher=ctx.dispatch_tool,
        ),
        description="Shortcut alias for /bmad-symphony.",
        args_hint="plan|story|run|proof|status|reset",
    )

    ctx.register_skill(
        name="workflow",
        path=_skill_path(),
        description="Deep BMad/Symphony workflow playbook for planning, implementation, and proof.",
    )
