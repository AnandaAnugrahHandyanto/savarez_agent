import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from gateway.config import Platform
from tools.send_message_tool import _parse_target_ref, send_message_tool


def _run_async_immediately(coro):
    return asyncio.run(coro)


def test_parse_target_ref_accepts_whatsapp_lid_jid():
    assert _parse_target_ref("whatsapp", "15551234567@lid") == (
        "15551234567@lid",
        None,
        True,
    )


def test_parse_target_ref_accepts_whatsapp_phone_jid():
    assert _parse_target_ref("whatsapp", "15551234567@s.whatsapp.net") == (
        "15551234567@s.whatsapp.net",
        None,
        True,
    )


def test_parse_target_ref_accepts_whatsapp_group_jid():
    assert _parse_target_ref("whatsapp", "120363001234567890@g.us") == (
        "120363001234567890@g.us",
        None,
        True,
    )


def test_parse_target_ref_accepts_legacy_e164_whatsapp_target():
    assert _parse_target_ref("whatsapp", "+15551234567") == (
        "+15551234567",
        None,
        True,
    )


def test_send_message_whatsapp_lid_target_does_not_fall_back_to_home_channel():
    whatsapp_cfg = SimpleNamespace(enabled=True, token="***", extra={})
    home = SimpleNamespace(chat_id="operator-home@lid")
    config = SimpleNamespace(
        platforms={Platform.WHATSAPP: whatsapp_cfg},
        get_home_channel=lambda _platform: home,
    )

    with patch("gateway.config.load_gateway_config", return_value=config), \
         patch("tools.interrupt.is_interrupted", return_value=False), \
         patch("model_tools._run_async", side_effect=_run_async_immediately), \
         patch("tools.send_message_tool._send_to_platform", new=AsyncMock(return_value={"success": True})) as send_mock, \
         patch("gateway.mirror.mirror_to_session", return_value=True):
        result = json.loads(
            send_message_tool(
                {
                    "action": "send",
                    "target": "whatsapp:15551234567@lid",
                    "message": "hello",
                }
            )
        )

    assert result["success"] is True
    assert "note" not in result
    send_mock.assert_awaited_once_with(
        Platform.WHATSAPP,
        whatsapp_cfg,
        "15551234567@lid",
        "hello",
        thread_id=None,
        media_files=[],
        force_document=False,
    )
