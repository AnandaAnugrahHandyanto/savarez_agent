"""Native Hermes Computer Use tool registrations.

Greenfield Computer Use exposes explicit ``computer_use_*`` tools. There is no
model-facing catch-all action dispatcher; each tool name carries intent so
policy, approvals, logging, and the future Swift app can reason about calls
without reverse-parsing an ``action`` field.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

from tools.computer_use.tool import (
    check_computer_use_requirements,
    handle_computer_use,
    set_approval_callback,
)
from tools.registry import registry


def _schema(name: str, description: str, properties: Dict[str, Any] | None = None, required: list[str] | None = None) -> Dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": properties or {},
            "required": required or [],
        },
    }


def _handle(action: str, args: Dict[str, Any], **kwargs):
    payload = dict(args or {})
    payload["action"] = action
    return handle_computer_use(payload, **kwargs)


_COMMON_TARGET = {
    "app": {"type": "string", "description": "App name or bundle id, e.g. Safari or com.apple.Safari."},
    "element": {"type": "integer", "description": "Element index from the latest app state."},
    "coordinate": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2},
    "capture_after": {"type": "boolean", "description": "Take and return app state after the action."},
}

_TOOL_SPECS = [
    ("computer_use_list_apps", "List macOS apps/windows available to Computer Use.", {}, [], "list_apps"),
    ("computer_use_get_app_state", "Get app/window state. Call this before and after every action.", {
        "app": _COMMON_TARGET["app"],
        "mode": {"type": "string", "enum": ["som", "vision", "ax"], "description": "som: screenshot + accessibility elements; ax: tree only; vision: screenshot only."},
    }, [], "get_app_state"),
    ("computer_use_click", "Click an element or coordinate in the current app state.", {
        **_COMMON_TARGET,
        "button": {"type": "string", "enum": ["left", "right", "middle"]},
    }, [], "click"),
    ("computer_use_perform_secondary_action", "Perform an accessibility secondary action on an element, e.g. show menu.", {
        **_COMMON_TARGET,
        "secondary_action": {"type": "string", "description": "AX action name, e.g. AXShowMenu or AXPress."},
    }, [], "perform_secondary_action"),
    ("computer_use_scroll", "Scroll in an app/window or element.", {
        **_COMMON_TARGET,
        "direction": {"type": "string", "enum": ["up", "down", "left", "right"]},
        "amount": {"type": "integer"},
    }, ["direction"], "scroll"),
    ("computer_use_drag", "Drag from one element/coordinate to another.", {
        "app": _COMMON_TARGET["app"],
        "from_element": {"type": "integer"},
        "to_element": {"type": "integer"},
        "from_coordinate": _COMMON_TARGET["coordinate"],
        "to_coordinate": _COMMON_TARGET["coordinate"],
        "capture_after": _COMMON_TARGET["capture_after"],
    }, [], "drag"),
    ("computer_use_type_text", "Type text into the targeted app/window.", {
        "app": _COMMON_TARGET["app"],
        "text": {"type": "string"},
        "capture_after": _COMMON_TARGET["capture_after"],
    }, ["text"], "type_text"),
    ("computer_use_set_value", "Set a value on an element, including text fields, selects, popups, and sliders.", {
        "app": _COMMON_TARGET["app"],
        "element": _COMMON_TARGET["element"],
        "value": {"type": "string"},
        "capture_after": _COMMON_TARGET["capture_after"],
    }, ["value"], "set_value"),
    ("computer_use_press_key", "Press a key or key combo in the targeted app/window.", {
        "app": _COMMON_TARGET["app"],
        "key": {"type": "string", "description": "Key or combo, e.g. Return, Escape, cmd+s."},
        "capture_after": _COMMON_TARGET["capture_after"],
    }, ["key"], "press_key"),
    ("computer_use_select_text", "Select text in an element or text field.", {
        "app": _COMMON_TARGET["app"],
        "element": _COMMON_TARGET["element"],
        "text": {"type": "string", "description": "Exact text to select, if supported."},
        "selection": {"type": "string", "description": "Selection mode, usually all or text."},
        "capture_after": _COMMON_TARGET["capture_after"],
    }, [], "select_text"),
]

for tool_name, description, properties, required, action in _TOOL_SPECS:
    registry.register(
        name=tool_name,
        toolset="computer_use",
        schema=_schema(tool_name, description, deepcopy(properties), required),
        handler=lambda args, _action=action, **kw: _handle(_action, args, **kw),
        check_fn=check_computer_use_requirements,
        requires_env=[],
        description=description,
        override=True,
    )


__all__ = [
    "handle_computer_use",
    "set_approval_callback",
    "check_computer_use_requirements",
]
