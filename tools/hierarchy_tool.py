#!/usr/bin/env python3
"""
Hierarchy Tool Module — Bridges the Hierarchical Agent Architecture into Hermes.

Registers hierarchy tools (send_to_profile, check_inbox, org_chart, profile_status,
spawn_tracked_worker, get_project_status) with the Hermes tool registry so agents
can use them mid-conversation.

Requires the hierarchy package (installed as part of hermes-agent)
and hierarchy data at ~/.hermes/hierarchy/.
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Availability check
# ---------------------------------------------------------------------------

def check_hierarchy_requirements():
    """Check if hierarchy system is available."""
    db_dir = Path.home() / ".hermes" / "hierarchy"
    if not db_dir.exists():
        return False, "Hierarchy not initialized. Run: python ~/.hermes/hierarchy/hierarchy_manager.py init"
    if not (db_dir / "registry.db").exists():
        return False, "Registry database not found at ~/.hermes/hierarchy/registry.db"
    return True, "Hierarchy system available"


# ---------------------------------------------------------------------------
# Import hierarchy tools lazily to avoid import errors if not installed
# ---------------------------------------------------------------------------

def _get_tools():
    """Lazy import of hierarchy_tools module."""
    try:
        from hierarchy.tools.hierarchy_tools import (
            send_to_profile, check_inbox, org_chart_tool,
            profile_status, spawn_tracked_worker, get_project_status
        )
        return {
            "send_to_profile": send_to_profile,
            "check_inbox": check_inbox,
            "org_chart": org_chart_tool,
            "profile_status": profile_status,
            "spawn_tracked_worker": spawn_tracked_worker,
            "get_project_status": get_project_status,
        }
    except ImportError as e:
        logger.warning(f"Hierarchy tools not available: {e}")
        return None


# ---------------------------------------------------------------------------
# Tool Handlers
# ---------------------------------------------------------------------------

def _handle(tool_name: str, args: dict, **kwargs) -> str:
    """Generic handler that routes to the correct hierarchy tool."""
    tools = _get_tools()
    if not tools:
        return json.dumps({"error": "Hierarchy tools not installed"})
    fn = tools.get(tool_name)
    if not fn:
        return json.dumps({"error": f"Unknown hierarchy tool: {tool_name}"})
    result = fn(args, **kwargs)
    return result if isinstance(result, str) else json.dumps(result)


def handle_send_to_profile(args: dict, **kwargs) -> str:
    return _handle("send_to_profile", args, **kwargs)

def handle_check_inbox(args: dict, **kwargs) -> str:
    return _handle("check_inbox", args, **kwargs)

def handle_org_chart(args: dict, **kwargs) -> str:
    return _handle("org_chart", args, **kwargs)

def handle_profile_status(args: dict, **kwargs) -> str:
    return _handle("profile_status", args, **kwargs)

def handle_spawn_tracked_worker(args: dict, **kwargs) -> str:
    return _handle("spawn_tracked_worker", args, **kwargs)

def handle_get_project_status(args: dict, **kwargs) -> str:
    return _handle("get_project_status", args, **kwargs)


# ---------------------------------------------------------------------------
# Tool Schemas
# ---------------------------------------------------------------------------

SEND_TO_PROFILE_SCHEMA = {
    "name": "send_to_profile",
    "description": (
        "Send a message to another profile in the hierarchy via IPC. "
        "Use this to delegate tasks, ask questions, or request status from "
        "department heads, project managers, or the CEO.\n\n"
        "Set deliver_to='telegram' (or 'origin', 'local') to fire-and-forget: "
        "a one-shot cron job is scheduled immediately — the target profile runs "
        "autonomously and its response is delivered to the specified destination. "
        "This is the RECOMMENDED async path and works from any context.\n\n"
        "Set wait_for_response=true for synchronous spawning (requires parent_agent "
        "context; falls back to async IPC if unavailable).\n\n"
        "Omit both for a simple fire-and-forget IPC queue message."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "to": {
                "type": "string",
                "description": "Target profile name (e.g., 'cto', 'pm-hier-arch', 'hermes')"
            },
            "message": {
                "type": "string",
                "description": "The message / task to send to the target profile"
            },
            "priority": {
                "type": "string",
                "enum": ["urgent", "normal", "low"],
                "description": "Message priority. Default: normal"
            },
            "deliver_to": {
                "type": "string",
                "description": (
                    "Delivery target for the async cron job response. "
                    "Examples: 'telegram', 'origin', 'local', "
                    "'telegram:-1001234567890:17585'. "
                    "When set, a one-shot cron job runs the target profile and "
                    "delivers its response here. Preferred over wait_for_response."
                )
            },
            "track": {
                "type": "boolean",
                "description": (
                    "When true, creates a DelegationChain that tracks the task "
                    "through the hierarchy and auto-activates the target profile's "
                    "gateway so it wakes up and executes the task. RECOMMENDED "
                    "for all task delegation."
                )
            },
            "wait_for_response": {
                "type": "boolean",
                "description": (
                    "Legacy: spawn the target profile synchronously and wait for "
                    "their response. Requires parent_agent context in the Hermes "
                    "handler chain; falls back to async IPC if unavailable. "
                    "Use deliver_to instead for reliable async execution."
                )
            }
        },
        "required": ["to", "message"]
    }
}

CHECK_INBOX_SCHEMA = {
    "name": "check_inbox",
    "description": (
        "Check pending IPC messages for a profile. Shows unread messages "
        "waiting to be processed. Use this to see what tasks or responses "
        "are waiting for you or another profile."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "profile": {
                "type": "string",
                "description": "Profile to check inbox for. Defaults to current profile."
            }
        },
        "required": []
    }
}

ORG_CHART_SCHEMA = {
    "name": "org_chart",
    "description": (
        "Display the current organizational hierarchy showing all profiles, "
        "their roles, departments, and reporting structure."
    ),
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": []
    }
}

PROFILE_STATUS_SCHEMA = {
    "name": "profile_status",
    "description": (
        "Get detailed status for a specific profile including memory stats, "
        "worker counts, pending messages, and direct reports."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "profile": {
                "type": "string",
                "description": "Profile name to check status for"
            }
        },
        "required": ["profile"]
    }
}

SPAWN_TRACKED_WORKER_SCHEMA = {
    "name": "spawn_tracked_worker",
    "description": (
        "Spawn a worker subagent for a specific task AND register it in the "
        "SubagentRegistry for lifecycle tracking. The worker's progress, "
        "completion, and artifacts are all tracked."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "Task description for the worker"
            },
            "model": {
                "type": "string",
                "description": "Model to use for the worker (e.g., 'opus', 'sonnet', 'haiku'). Optional."
            }
        },
        "required": ["task"]
    }
}

GET_PROJECT_STATUS_SCHEMA = {
    "name": "get_project_status",
    "description": (
        "Get the status of all workers under a project manager — "
        "running workers, completed tasks, sleeping workers, and stats."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "project_manager": {
                "type": "string",
                "description": "PM profile name (e.g., 'pm-hier-arch', 'pm-counter-liquid')"
            }
        },
        "required": ["project_manager"]
    }
}


# ---------------------------------------------------------------------------
# Register with Hermes tool registry
# ---------------------------------------------------------------------------

from tools.registry import registry

registry.register(
    name="send_to_profile",
    toolset="hierarchy",
    schema=SEND_TO_PROFILE_SCHEMA,
    handler=handle_send_to_profile,
    check_fn=check_hierarchy_requirements,
    emoji="📨",
)

registry.register(
    name="check_inbox",
    toolset="hierarchy",
    schema=CHECK_INBOX_SCHEMA,
    handler=handle_check_inbox,
    check_fn=check_hierarchy_requirements,
    emoji="📬",
)

registry.register(
    name="org_chart",
    toolset="hierarchy",
    schema=ORG_CHART_SCHEMA,
    handler=handle_org_chart,
    check_fn=check_hierarchy_requirements,
    emoji="🏢",
)

registry.register(
    name="profile_status",
    toolset="hierarchy",
    schema=PROFILE_STATUS_SCHEMA,
    handler=handle_profile_status,
    check_fn=check_hierarchy_requirements,
    emoji="📊",
)

registry.register(
    name="spawn_tracked_worker",
    toolset="hierarchy",
    schema=SPAWN_TRACKED_WORKER_SCHEMA,
    handler=handle_spawn_tracked_worker,
    check_fn=check_hierarchy_requirements,
    emoji="👷",
)

registry.register(
    name="get_project_status",
    toolset="hierarchy",
    schema=GET_PROJECT_STATUS_SCHEMA,
    handler=handle_get_project_status,
    check_fn=check_hierarchy_requirements,
    emoji="📋",
)
