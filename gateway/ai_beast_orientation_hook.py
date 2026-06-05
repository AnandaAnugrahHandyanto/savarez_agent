"""Opt-in AI Beast orientation command hook.

This built-in hook is intentionally inert unless a caller supplies explicit
configuration with ``enabled`` and a safe local ``project_root``.  It only
handles read-only orientation commands and leaves Hermes-owned commands to the
normal gateway dispatch path.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any, Callable, Mapping

HERMES_OWNED_COMMANDS = frozenset({"status", "sessions"})
FORBIDDEN_COMMANDS = frozenset(
    {
        "task",
        "steer",
        "pause",
        "resume",
        "bindtopic",
        "switch",
        "open",
        "newsession",
    }
)
ORIENTATION_COMMANDS = frozenset({"whereami"})


def _get_value(source: Any, key: str, default: Any = None) -> Any:
    if isinstance(source, Mapping):
        return source.get(key, default)
    return getattr(source, key, default)


def _normalise_command(event_type: str, context: Mapping[str, Any]) -> str:
    command = str(context.get("command") or "").strip().lower()
    if not command and event_type.startswith("command:"):
        command = event_type.split(":", 1)[1].strip().lower()
    return command.lstrip("/")


def _orientation_config(context: Mapping[str, Any]) -> Any:
    gateway_config = context.get("gateway_config")
    if gateway_config is None:
        return {}
    return _get_value(gateway_config, "ai_beast_orientation", {}) or {}


async def _call_adapter(
    orientation_adapter: Callable[..., Any],
    *,
    command: str,
    project_root: Path,
    context: Mapping[str, Any],
) -> Any:
    try:
        result = orientation_adapter(
            command=command,
            project_root=project_root,
            context=context,
        )
    except TypeError:
        # Keep the test seam and future local adapters simple: callers may pass
        # a zero-argument adapter when they only need to prove dispatch.
        result = orientation_adapter()
    if inspect.isawaitable(result):
        result = await result
    return result


async def handle(
    event_type: str,
    context: Mapping[str, Any] | None,
    *,
    orientation_adapter: Callable[..., Any] | None = None,
    side_effects: Mapping[str, Callable[..., Any]] | None = None,
) -> dict[str, str] | None:
    """Handle a safe, explicitly enabled AI Beast orientation command.

    ``side_effects`` is accepted only as a test seam proving this hook does not
    invoke forbidden side-effect paths.  It is deliberately unused.
    """
    del side_effects

    if context is None:
        return None

    command = _normalise_command(event_type, context)
    if command in HERMES_OWNED_COMMANDS or command in FORBIDDEN_COMMANDS:
        return None
    if command not in ORIENTATION_COMMANDS:
        return None

    config = _orientation_config(context)
    if not bool(_get_value(config, "enabled", False)):
        return None

    project_root_value = _get_value(config, "project_root")
    if not project_root_value:
        return {
            "decision": "deny",
            "message": "AI Beast orientation root is not available.",
        }

    project_root = Path(str(project_root_value)).expanduser()
    if not project_root.exists() or not project_root.is_dir():
        return {
            "decision": "deny",
            "message": "AI Beast orientation root is not available.",
        }

    if orientation_adapter is None:
        return {
            "decision": "deny",
            "message": "AI Beast orientation adapter is not configured.",
        }

    message = await _call_adapter(
        orientation_adapter,
        command=command,
        project_root=project_root,
        context=context,
    )
    return {
        "decision": "handled",
        "message": str(message),
    }
