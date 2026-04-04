#!/usr/bin/env python3
"""macOS Workflow Tool — Execute multi-step compound macOS actions."""

import json
import platform
import subprocess
import time
from typing import Any, Dict, List, Optional


# --- Workflow Definitions ---

WORKFLOWS = {
    "presentation_mode": {
        "description": "DND on, mute audio, hide desktop icons, prevent sleep",
        "steps": [
            ("Enable Do Not Disturb", 'tell application "System Events" to tell process "Control Center" to click menu bar item "Focus" of menu bar 1'),
            ("Mute system audio", "set volume with output muted"),
            ("Hide Desktop icons", 'do shell script "defaults write com.apple.finder CreateDesktop false && killall Finder"'),
            ("Prevent sleep", 'do shell script "caffeinate -d &"'),
        ],
    },
    "deep_work": {
        "description": "DND on, close distracting apps, prevent sleep",
        "steps": [
            ("Enable Do Not Disturb", 'tell application "System Events" to tell process "Control Center" to click menu bar item "Focus" of menu bar 1'),
            ("Close Messages", 'tell application "Messages" to quit'),
            ("Close Mail", 'tell application "Mail" to quit'),
            ("Close Slack", 'tell application "Slack" to quit'),
            ("Prevent sleep", 'do shell script "caffeinate -d &"'),
        ],
    },
    "end_of_day": {
        "description": "Restore desktop icons, unmute audio, empty trash",
        "steps": [
            ("Restore Desktop icons", 'do shell script "defaults write com.apple.finder CreateDesktop true && killall Finder"'),
            ("Unmute audio", "set volume without output muted"),
            ("Empty Trash", 'tell application "Finder" to empty the trash'),
        ],
    },
    "meeting_prep": {
        "description": "DND on, unmute mic, prevent sleep",
        "steps": [
            ("Enable Do Not Disturb", 'tell application "System Events" to tell process "Control Center" to click menu bar item "Focus" of menu bar 1'),
            ("Unmute audio", "set volume without output muted"),
            ("Prevent sleep", 'do shell script "caffeinate -d &"'),
        ],
    },
    "creative_mode": {
        "description": "Stage Manager on, DND, prevent sleep",
        "steps": [
            ("Enable Stage Manager", 'do shell script "defaults write com.apple.WindowManager GloballyEnabled -bool true && killall Dock"'),
            ("Enable Do Not Disturb", 'tell application "System Events" to tell process "Control Center" to click menu bar item "Focus" of menu bar 1'),
            ("Prevent sleep", 'do shell script "caffeinate -d &"'),
        ],
    },
}


def _run_applescript(script: str) -> str:
    """Execute an AppleScript via osascript."""
    try:
        result = subprocess.run(
            ["/usr/bin/osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return f"Error: {result.stderr.strip()}"
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return "Error: AppleScript timed out"
    except Exception as e:
        return f"Error: {e}"


def mac_workflow_handler(
    workflow: str,
    action: str = "run",
    custom_steps: Optional[List[str]] = None,
) -> str:
    """Handle mac_workflow tool calls."""

    if action == "list":
        lines = ["Available workflows:\n"]
        for name, wf in WORKFLOWS.items():
            lines.append(f"- **{name}**: {wf['description']}")
        lines.append("\nActions: 'run' (execute), 'preview' (show steps), 'list' (this list)")
        return "\n".join(lines)

    wf = WORKFLOWS.get(workflow)
    if not wf:
        names = ", ".join(WORKFLOWS.keys())
        return json.dumps({"error": f"Unknown workflow: {workflow}. Available: {names}"})

    steps = wf["steps"]

    if action == "preview":
        lines = [f"Workflow: {workflow} ({len(steps)} steps)\n"]
        for i, (desc, _) in enumerate(steps, 1):
            lines.append(f"  {i}. {desc}")
        lines.append("\nUse action: 'run' to execute this workflow.")
        return "\n".join(lines)

    # Execute
    results = [f"Executing workflow: {workflow}"]
    for i, (desc, script) in enumerate(steps, 1):
        output = _run_applescript(script)
        status = "done" if not output.startswith("Error") else output
        results.append(f"  [{i}/{len(steps)}] {desc} — {status}")
        time.sleep(0.3)

    results.append(f"\nWorkflow '{workflow}' completed ({len(steps)} steps)")
    return "\n".join(results)


def check_mac_workflow_requirements() -> bool:
    """Only available on macOS."""
    return platform.system() == "Darwin"


MAC_WORKFLOW_SCHEMA = {
    "name": "mac_workflow",
    "description": (
        "Execute multi-step macOS workflows like 'set up for presentations', "
        "'prepare for deep work', or 'end of day routine'. "
        "Combines multiple system actions into a single command."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "workflow": {
                "type": "string",
                "enum": list(WORKFLOWS.keys()) + ["custom"],
                "description": "Predefined workflow name, or 'custom' with steps",
            },
            "action": {
                "type": "string",
                "enum": ["run", "preview", "list"],
                "description": (
                    "run = execute workflow, "
                    "preview = show steps without executing, "
                    "list = show available workflows"
                ),
            },
        },
        "required": ["workflow"],
    },
}


# --- Registry ---
from tools.registry import registry

registry.register(
    name="mac_workflow",
    toolset="macos",
    schema=MAC_WORKFLOW_SCHEMA,
    handler=lambda args, **kw: mac_workflow_handler(
        workflow=args.get("workflow", ""),
        action=args.get("action", "run"),
        custom_steps=args.get("custom_steps"),
    ),
    check_fn=check_mac_workflow_requirements,
    emoji="⚡",
    mutates=True,
)
