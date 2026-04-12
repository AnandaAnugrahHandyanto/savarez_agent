"""Plan Mode hook plugin for Hermes Agent (Phase B2).

When plan mode is active, only read-only / planning tools are allowed.
Write operations and heavy tools are denied via pre_tool_call.
"""

# ── State ──────────────────────────────────────────────────────────────
_plan_mode_active = False

# Tools always allowed in plan mode
_PLAN_ALLOW = {
    "read_file", "search_files", "session_search",
    "skills_list", "skill_view", "tool_search",
    "plan_mode",
}


def enter_plan_mode():
    global _plan_mode_active
    _plan_mode_active = True


def exit_plan_mode():
    global _plan_mode_active
    _plan_mode_active = False


def is_active() -> bool:
    return _plan_mode_active


# ── Hook entry point ────────────────────────────────────────────────────
def pre_tool_call(tool_name: str, args: dict, **kwargs) -> dict | None:
    """Called by the plugin system before each tool invocation."""
    if not _plan_mode_active:
        return None

    # Always-allowed tools
    if tool_name in _PLAN_ALLOW:
        return None

    # memory: read allowed, writes denied
    if tool_name == "memory":
        if args.get("action") == "read":
            return None
        return {
            "action": "deny",
            "reason": "Plan Mode: memory write operations not allowed",
        }

    # Everything else denied in plan mode
    return {
        "action": "deny",
        "reason": f"Plan Mode: {tool_name} not allowed",
    }
