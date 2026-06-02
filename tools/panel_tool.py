"""Panel Tool — Send interactive card panels to Feishu chats.

Sends Feishu interactive cards with buttons, markdown, and action groups.
Button clicks are routed back through the gateway as synthetic ``/card button``
messages so the agent can respond to user interactions.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Card builder helpers
# ---------------------------------------------------------------------------

def _build_button(
    label: str,
    value: str,
    *,
    btn_type: str = "default",
    action_name: str = "quick",
) -> dict:
    """Build a Feishu card button element.

    Parameters
    ----------
    label:
        Button display text.
    value:
        Text sent back as a synthetic message when the button is clicked.
        Typically a command like ``/status`` or ``/model openai/gpt-4o``.
    btn_type:
        Visual style — ``primary``, ``danger``, or ``default``.
    action_name:
        Label stored in the value envelope for identification.
    """
    return {
        "tag": "button",
        "text": {"tag": "plain_text", "content": label},
        "type": btn_type,
        "value": {"action": action_name, "text": value},
    }


def _build_card(config: Dict[str, Any]) -> dict:
    """Build a full Feishu interactive card JSON object from caller config.

    ``config`` keys:
        title        — header title text
        template     — header colour template (blue / green / red / orange / purple / grey)
        sections     — list of ``{ content?, buttons? }`` dicts
        content      — shorthand: single markdown section (ignored when *sections* given)
        buttons      — shorthand: list of ``{ label, value, type? }`` (ignored when *sections* given)
    """
    title = config.get("title", "🐾 小爪面板")
    template = config.get("template", "blue")
    sections = config.get("sections")

    # Shorthand mode — single section with markdown + buttons
    if not sections:
        md_content = config.get("content", "")
        raw_buttons = config.get("buttons", [])
        sections = [{"content": md_content, "buttons": raw_buttons}] if (md_content or raw_buttons) else []

    elements: list[dict] = []
    for sec in sections:
        sec_content = sec.get("content", "")
        sec_buttons = sec.get("buttons", [])
        sec_label = sec.get("label", "")

        if sec_label:
            elements.append({"tag": "markdown", "content": f"**{sec_label}**"})

        if sec_content:
            elements.append({"tag": "markdown", "content": sec_content})

        if sec_buttons:
            actions = [
                _build_button(
                    btn["label"],
                    btn["value"],
                    btn_type=btn.get("type", "default"),
                    action_name=btn.get("action", "quick"),
                )
                for btn in sec_buttons
            ]
            elements.append({"tag": "action", "actions": actions})

        elements.append({"tag": "hr"})

    # Remove trailing hr
    if elements and elements[-1].get("tag") == "hr":
        elements.pop()

    return {
        "schema": "2.0",
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": title},
            "template": template,
        },
        "body": {
            "elements": elements,
        },
    }


# ---------------------------------------------------------------------------
# Main handler
# ---------------------------------------------------------------------------

async def panel_tool(args: Dict[str, Any], **kw: Any) -> Dict[str, Any]:
    """Send an interactive Feishu card panel.

    Parameters (from args):
        config     — card configuration dict (see ``_build_card``)
        chat_id    — target Feishu chat ID (optional, defaults to current chat)
        card_json  — raw card JSON override (optional, skips builder)

    Returns dict with ``success``, ``chat_id``, ``message_id`` or ``error``.
    """
    try:
        from gateway.platforms.feishu import FeishuAdapter, FEISHU_AVAILABLE
        if not FEISHU_AVAILABLE:
            return {"error": "Feishu dependencies not installed. Run: pip install 'hermes-agent[feishu]'"}
        from gateway.platforms.feishu import FEISHU_DOMAIN, LARK_DOMAIN
    except ImportError:
        return {"error": "Feishu dependencies not installed. Run: pip install 'hermes-agent[feishu]'"}

    # Build card JSON
    raw_card = args.get("card_json")
    if raw_card and isinstance(raw_card, (str, dict)):
        card = json.loads(raw_card) if isinstance(raw_card, str) else raw_card
    else:
        config = args.get("config", {})
        card = _build_card(config)

    # Resolve target chat_id
    chat_id = args.get("chat_id")
    if not chat_id:
        # Fall back to current session's chat
        from gateway.session_context import get_session_env
        chat_id = get_session_env("HERMES_SESSION_CHAT_ID", "")
    if not chat_id:
        return {"error": "No chat_id provided and no active session chat. Please specify chat_id."}

    # Get Feishu platform config (same pattern as send_message_tool)
    try:
        from gateway.config import load_gateway_config, Platform
        config_obj = load_gateway_config()
        pconfig = config_obj.platforms.get(Platform.FEISHU)
        if not pconfig or not pconfig.enabled:
            return {"error": "Feishu platform is not enabled in config."}
    except Exception as e:
        return {"error": f"Failed to load Feishu config: {e}"}

    # Build adapter and send
    try:
        adapter = FeishuAdapter(pconfig)
        domain_name = getattr(adapter, "_domain_name", "feishu")
        domain = FEISHU_DOMAIN if domain_name != "lark" else LARK_DOMAIN
        adapter._client = adapter._build_lark_client(domain)

        payload = json.dumps(card, ensure_ascii=False)
        raw_response = await adapter._feishu_send_with_retry(
            chat_id=chat_id,
            msg_type="interactive",
            payload=payload,
            reply_to=None,
            metadata=None,
        )

        send_result = adapter._finalize_send_result(raw_response, "send_panel failed")
        if send_result.success:
            return {
                "success": True,
                "chat_id": chat_id,
                "message_id": send_result.message_id,
                "info": "Card sent. Button clicks will be routed as /card button messages.",
            }
        else:
            return {"error": f"Feishu card send failed: {send_result.error}"}
    except Exception as e:
        logger.warning("[Panel] Send failed: %s", e, exc_info=True)
        return {"error": f"Panel send failed: {e}"}


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

PANEL_SCHEMA: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "send_panel",
        "description": (
            "Send an interactive Feishu card panel with buttons and markdown. "
            "Button clicks generate synthetic '/card button {value}' messages back to the agent. "
            "Use for quick-action panels, menus, approval flows, and interactive dashboards. "
            "Only works on Feishu (Lark) platform."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "config": {
                    "type": "object",
                    "description": "Card configuration. Keys: title (header text), template (color: blue/green/red/orange/purple/grey), content (markdown text), buttons (list of {label, value, type?, action?}), sections (list of {label?, content?, buttons?} for multi-section layout). Use either content+buttons (simple) or sections (multi-section), not both.",
                    "properties": {
                        "title": {"type": "string", "description": "Card header title"},
                        "template": {"type": "string", "enum": ["blue", "green", "red", "orange", "purple", "grey"], "description": "Header color theme"},
                        "content": {"type": "string", "description": "Markdown content for single-section cards"},
                        "buttons": {
                            "type": "array",
                            "description": "Buttons for single-section cards",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "label": {"type": "string", "description": "Button text"},
                                    "value": {"type": "string", "description": "Text/message sent when clicked"},
                                    "type": {"type": "string", "enum": ["primary", "danger", "default"], "description": "Button style"},
                                    "action": {"type": "string", "description": "Action name identifier"},
                                },
                                "required": ["label", "value"],
                            },
                        },
                        "sections": {
                            "type": "array",
                            "description": "Multi-section layout (overrides content/buttons)",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "label": {"type": "string", "description": "Section label (rendered bold)"},
                                    "content": {"type": "string", "description": "Markdown content"},
                                    "buttons": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "label": {"type": "string"},
                                                "value": {"type": "string"},
                                                "type": {"type": "string", "enum": ["primary", "danger", "default"]},
                                                "action": {"type": "string"},
                                            },
                                            "required": ["label", "value"],
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
                "chat_id": {
                    "type": "string",
                    "description": "Target Feishu chat ID (optional, defaults to current session chat)",
                },
                "card_json": {
                    "type": "object",
                    "description": "Raw Feishu card JSON (optional, overrides config entirely)",
                },
            },
            "required": ["config"],
        },
    },
}


# ---------------------------------------------------------------------------
# Availability check
# ---------------------------------------------------------------------------

def _check_panel_available() -> bool:
    """Return True when the Feishu adapter can be imported."""
    try:
        from gateway.platforms.feishu import FEISHU_AVAILABLE  # noqa: F811
        return bool(FEISHU_AVAILABLE)
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

from tools.registry import registry  # noqa: E402

registry.register(
    name="send_panel",
    toolset="feishu",
    schema=PANEL_SCHEMA,
    handler=lambda args, **kw: panel_tool(args, **kw),
    check_fn=_check_panel_available,
    emoji="🃏",
)
