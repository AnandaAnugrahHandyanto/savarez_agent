"""Plan Mode tool for Hermes Agent (Phase B2).

Allows entering/exiting plan mode and querying status.
"""

import json

from tools.registry import registry

PLAN_MODE_SCHEMA = {
    "name": "plan_mode",
    "description": "Enter or exit plan mode. In plan mode only read-only and planning tools are available.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["enter", "exit", "status"],
                "description": "Action to perform: enter plan mode, exit plan mode, or check status.",
            },
        },
        "required": ["action"],
    },
}


def plan_mode_handler(args: dict, **kwargs) -> str:
    """Handle plan_mode tool calls."""
    import importlib
    import os

    action = args.get("action", "status")

    # Load plan_mode_hook via importlib (hyphenated directory)
    plugin_dir = os.path.join(
        os.path.dirname(__file__), os.pardir,
        "plugins", "hongxing-enhancements",
    )
    spec = importlib.util.spec_from_file_location(
        "plan_mode_hook",
        os.path.join(plugin_dir, "plan_mode_hook.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    if action == "enter":
        mod.enter_plan_mode()
        return json.dumps({"success": True, "plan_mode": True}, ensure_ascii=False)
    elif action == "exit":
        mod.exit_plan_mode()
        return json.dumps({"success": True, "plan_mode": False}, ensure_ascii=False)
    else:
        return json.dumps({"plan_mode": mod.is_active()}, ensure_ascii=False)


registry.register(
    name="plan_mode",
    toolset="core",
    schema=PLAN_MODE_SCHEMA,
    handler=plan_mode_handler,
    description="Enter or exit plan mode",
    emoji="📋",
    allowed_in_plan_mode_default=True,
)
