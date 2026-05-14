"""Tool schema for the Dreaming plugin.

Registers the ``dream_run`` tool that can be called by the LLM during
a cron-triggered dreaming cycle, and ``dream_status`` for querying state.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from plugins.dreaming import run_dreaming_cycle, is_enabled, _get_config, _get_last_user_activity

logger = logging.getLogger(__name__)

DREAM_RUN_SCHEMA = {
    "name": "dream_run",
    "description": (
        "Run a Dreaming memory consolidation cycle. This is normally called "
        "automatically by a cron job during quiet hours. Use force=True to "
        "run immediately regardless of user activity. Returns a summary of "
        "what was consolidated."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "force": {
                "type": "boolean",
                "description": "Skip the user-activity quiet check and run immediately. Default: false.",
                "default": False,
            },
            "verbose": {
                "type": "boolean",
                "description": "Log detailed progress. Default: false.",
                "default": False,
            },
        },
        "required": [],
    },
}

DREAM_STATUS_SCHEMA = {
    "name": "dream_status",
    "description": (
        "Get the current status of the Dreaming memory consolidation system. "
        "Shows whether it is enabled, when the last cycle ran, user activity "
        "state, and file paths."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

ALL_TOOL_SCHEMAS = [DREAM_RUN_SCHEMA, DREAM_STATUS_SCHEMA]


def dream_run(force: bool = False, verbose: bool = False) -> Dict[str, Any]:
    """Run a dreaming cycle and return a summary dict."""
    result = run_dreaming_cycle(force=force, verbose=verbose)
    if result is None:
        return {
            "status": "skipped",
            "reason": "user_active_or_disabled",
        }
    return {
        "status": "complete",
        "candidates_staged": result.light_count,
        "themes_found": len(result.rem_themes),
        "promoted": len(result.deep_promoted),
        "skipped": len(result.deep_skipped),
        "promoted_memories": result.deep_promoted,
        "dream_diary_entry": result.to_markdown(),
    }


def dream_status() -> Dict[str, Any]:
    """Return current dreaming status."""
    cfg = _get_config()
    last_active = _get_last_user_activity()
    return {
        "enabled": is_enabled(),
        "frequency": cfg.get("frequency", "0 3 * * *"),
        "quiet_minutes": cfg.get("quiet_minutes", 60),
        "lookback_days": cfg.get("lookback_days", 7),
        "promotion_threshold": cfg.get("promotion_threshold", 0.6),
        "last_user_activity": str(last_active) if last_active else None,
    }


def get_tool_schemas() -> list:
    """Return tool schemas for registration."""
    return ALL_TOOL_SCHEMAS


def handle_tool_call(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatch a tool call by name."""
    if name == "dream_run":
        return dream_run(
            force=args.get("force", False),
            verbose=args.get("verbose", False),
        )
    if name == "dream_status":
        return dream_status()
    return {"error": f"Unknown dreaming tool: {name}"}
