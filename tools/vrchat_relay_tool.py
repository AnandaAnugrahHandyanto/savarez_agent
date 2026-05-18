"""Agent tools: VRChat relay via harness HTTP (TS stays in vendor)."""

from __future__ import annotations

import json

from tools.openclaw.vrchat_relay_bridge import (
    auto_osc_start,
    auto_osc_status,
    auto_osc_stop,
    vrc_channels_readiness,
    vrc_chatbox,
    vrc_parameter,
    vrc_status,
)
from tools.registry import registry


def _json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


registry.register(
    name="vrc_relay_status",
    toolset="harness",
    schema={
        "name": "vrc_relay_status",
        "description": (
            "VRChat relay status from hypura-harness (bridge, avatar catalog, safety gate). "
            "Requires hermes harness start."
        ),
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    handler=lambda args, **kw: _json(vrc_status()),
    emoji="🌐",
)

registry.register(
    name="vrc_relay_channels_readiness",
    toolset="harness",
    schema={
        "name": "vrc_relay_channels_readiness",
        "description": "LINE/Telegram readiness via harness gateway config (same as channel_readiness_check).",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    handler=lambda args, **kw: _json(vrc_channels_readiness()),
    emoji="📡",
)

registry.register(
    name="vrc_relay_chatbox",
    toolset="harness",
    schema={
        "name": "vrc_relay_chatbox",
        "description": "Send VRChat chatbox text through harness safety-gated relay (not raw OSC).",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Chatbox message."},
                "send_immediately": {
                    "type": "boolean",
                    "description": "Send immediately (default true).",
                },
            },
            "required": ["text"],
        },
    },
    handler=lambda args, **kw: _json(
        vrc_chatbox(args["text"], send_immediately=args.get("send_immediately", True)),
    ),
    emoji="💭",
)

registry.register(
    name="vrc_relay_parameter",
    toolset="harness",
    schema={
        "name": "vrc_relay_parameter",
        "description": "Set avatar OSC parameter via harness safety gate.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Parameter name."},
                "value": {"description": "bool, int, or float value."},
            },
            "required": ["name", "value"],
        },
    },
    handler=lambda args, **kw: _json(vrc_parameter(args["name"], args["value"])),
    emoji="🎭",
)

registry.register(
    name="vrc_relay_auto_osc",
    toolset="harness",
    schema={
        "name": "vrc_relay_auto_osc",
        "description": "Start, stop, or query VRChat auto-OSC background loop in harness.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["status", "start", "stop"],
                    "description": "Auto-OSC control action.",
                },
            },
            "required": ["action"],
        },
    },
    handler=lambda args, **kw: _json(_auto_osc_dispatch(args.get("action", "status"))),
    emoji="🔄",
)


def _auto_osc_dispatch(action: str) -> dict:
    if action == "start":
        return auto_osc_start()
    if action == "stop":
        return auto_osc_stop()
    return auto_osc_status()
