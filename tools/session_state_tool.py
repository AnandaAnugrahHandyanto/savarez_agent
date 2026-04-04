"""Session state tool — persistent key-value store that survives context compression.

Unlike conversation messages (which get summarized/dropped on compression), session
state persists for the entire session chain (including compression-triggered splits).
Use this for multi-step workflow progress, analysis state, and structured data that
the agent needs to track across many turns.

Inspired by agno's session_state pattern.
"""

import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Maximum total serialized size for the state dict (64 KB)
MAX_STATE_SIZE = 65_536
# Maximum number of keys
MAX_STATE_KEYS = 100


def session_state_tool(
    action: str,
    key: str = None,
    value: Any = None,
    db: Any = None,
    session_id: str = None,
) -> str:
    """Dispatch session state operations. Returns JSON string."""
    if db is None or session_id is None:
        return json.dumps(
            {"success": False, "error": "Session state not available (no session DB)."},
            ensure_ascii=False,
        )

    if action == "get":
        state = db.get_session_state(session_id)
        if key:
            val = state.get(key)
            if val is None:
                return json.dumps(
                    {"success": True, "key": key, "value": None, "exists": False},
                    ensure_ascii=False,
                )
            return json.dumps(
                {"success": True, "key": key, "value": val, "exists": True},
                ensure_ascii=False,
            )
        return json.dumps(
            {"success": True, "state": state, "key_count": len(state)},
            ensure_ascii=False,
        )

    elif action == "set":
        if not key:
            return json.dumps(
                {"success": False, "error": "key is required for 'set' action."},
                ensure_ascii=False,
            )
        if value is None:
            return json.dumps(
                {"success": False, "error": "value is required for 'set' action."},
                ensure_ascii=False,
            )
        state = db.get_session_state(session_id)
        if key not in state and len(state) >= MAX_STATE_KEYS:
            return json.dumps(
                {"success": False, "error": f"State has {len(state)} keys (max {MAX_STATE_KEYS}). Remove some before adding more."},
                ensure_ascii=False,
            )
        state[key] = value
        serialized = json.dumps(state, ensure_ascii=False)
        if len(serialized) > MAX_STATE_SIZE:
            return json.dumps(
                {"success": False, "error": f"State too large ({len(serialized)} bytes, max {MAX_STATE_SIZE}). Remove keys or reduce values."},
                ensure_ascii=False,
            )
        db.set_session_state(session_id, state)
        return json.dumps(
            {"success": True, "key": key, "action": "set", "key_count": len(state)},
            ensure_ascii=False,
        )

    elif action == "delete":
        if not key:
            return json.dumps(
                {"success": False, "error": "key is required for 'delete' action."},
                ensure_ascii=False,
            )
        state = db.get_session_state(session_id)
        existed = key in state
        state.pop(key, None)
        db.set_session_state(session_id, state)
        return json.dumps(
            {"success": True, "key": key, "action": "delete", "existed": existed, "key_count": len(state)},
            ensure_ascii=False,
        )

    elif action == "list":
        state = db.get_session_state(session_id)
        keys = sorted(state.keys())
        return json.dumps(
            {"success": True, "keys": keys, "key_count": len(keys)},
            ensure_ascii=False,
        )

    elif action == "clear":
        db.set_session_state(session_id, {})
        return json.dumps(
            {"success": True, "action": "clear"},
            ensure_ascii=False,
        )

    else:
        return json.dumps(
            {"success": False, "error": f"Unknown action '{action}'. Use: get, set, delete, list, clear"},
            ensure_ascii=False,
        )


def format_state_for_system_prompt(state: Dict[str, Any]) -> str:
    """Format session state dict as a compact block for the system prompt."""
    if not state:
        return ""
    lines = ["## Session State (persistent key-value store — survives context compression)"]
    for key, value in sorted(state.items()):
        val_str = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
        # Truncate very long values in the prompt (full value via tool)
        if len(val_str) > 200:
            val_str = val_str[:197] + "..."
        lines.append(f"- **{key}**: {val_str}")
    lines.append("")
    lines.append("Use the `session_state` tool to read full values or update state.")
    return "\n".join(lines)


def check_session_state_requirements() -> bool:
    """Session state has no external requirements."""
    return True


# =============================================================================
# OpenAI Function-Calling Schema
# =============================================================================

SESSION_STATE_SCHEMA = {
    "name": "session_state",
    "description": (
        "Read and write persistent session state — key-value pairs that survive context "
        "compression and session splits. Use this for multi-step workflow tracking, "
        "analysis progress, structured data, and anything that must persist across many turns.\n\n"
        "WHEN TO USE:\n"
        "- Tracking multi-step analysis progress (e.g., 'step 3 of 5 complete')\n"
        "- Storing structured intermediate results (portfolio positions, comparison tables)\n"
        "- Maintaining workflow context that would be lost to compression\n"
        "- Accumulating data across tool calls (running totals, collected findings)\n\n"
        "DO NOT USE for: user preferences (use memory tool), conversation history "
        "(use session_search), or ephemeral data that won't matter in 10 turns.\n\n"
        "ACTIONS: get (read key or all), set (write key), delete (remove key), list (show keys), clear (reset all)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["get", "set", "delete", "list", "clear"],
                "description": "The operation to perform.",
            },
            "key": {
                "type": "string",
                "description": "State key name. Required for set/delete, optional for get (omit to get all).",
            },
            "value": {
                "description": "Value to store (any JSON-serializable type). Required for set.",
            },
        },
        "required": ["action"],
    },
}

# --- Registry ---
from tools.registry import registry

registry.register(
    name="session_state",
    toolset="session_state",
    schema=SESSION_STATE_SCHEMA,
    handler=lambda args, **kw: session_state_tool(
        action=args.get("action", ""),
        key=args.get("key"),
        value=args.get("value"),
        db=kw.get("db"),
        session_id=kw.get("session_id"),
    ),
    check_fn=check_session_state_requirements,
    emoji="💾",
    mutates=True,
)
