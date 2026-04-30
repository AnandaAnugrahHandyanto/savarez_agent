"""Tests for event-loop mismatch guard in send_weixin_direct.  See #18014."""

import asyncio
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_session(*, closed: bool = False, loop=None):
    session = MagicMock()
    session.closed = closed
    session._loop = loop
    return session


def _make_mock_adapter(session):
    adapter = MagicMock()
    adapter._send_session = session
    adapter.format_message = MagicMock(return_value="hello")
    result = MagicMock()
    result.success = True
    result.message_id = "mid-1"
    adapter.send = AsyncMock(return_value=result)
    adapter.send_image_file = AsyncMock(return_value=result)
    adapter.send_document = AsyncMock(return_value=result)
    return adapter


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_weixin_direct_skips_stale_loop_session():
    """When the live adapter's session belongs to a different event loop,
    send_weixin_direct should NOT reuse it — it should fall through to the
    one-shot aiohttp.ClientSession path."""

    stale_loop = MagicMock()  # some other loop
    session = _make_mock_session(loop=stale_loop)
    adapter = _make_mock_adapter(session)

    mock_session_ctx = AsyncMock()
    mock_new_session = MagicMock()
    mock_new_session.closed = False
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_new_session)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch.dict("gateway.platforms.weixin._LIVE_ADAPTERS", {"tok": adapter}), \
         patch("gateway.platforms.weixin.ContextTokenStore") as MockCTS, \
         patch("gateway.platforms.weixin.aiohttp") as mock_aiohttp, \
         patch("gateway.platforms.weixin.WeixinAdapter") as MockWA, \
         patch("gateway.platforms.weixin.get_hermes_home", return_value="/tmp"), \
         patch("gateway.platforms.weixin._make_ssl_connector", return_value=None):

        MockCTS.return_value.restore = MagicMock()
        MockCTS.return_value.get = MagicMock(return_value=None)

        mock_aiohttp.ClientSession.return_value = mock_session_ctx

        wa_inst = MagicMock()
        wa_inst.format_message = MagicMock(return_value="hello")
        send_result = MagicMock()
        send_result.success = True
        send_result.message_id = "mid-2"
        wa_inst.send = AsyncMock(return_value=send_result)
        MockWA.return_value = wa_inst

        from gateway.platforms.weixin import send_weixin_direct

        result = await send_weixin_direct(
            extra={"account_id": "acc1"},
            token="tok",
            chat_id="user1",
            message="hi",
        )

    # The live adapter's send must NOT have been called (stale loop)
    adapter.send.assert_not_called()
    # The one-shot path's adapter send SHOULD have been called
    wa_inst.send.assert_called_once()
    assert result.get("success") is True


@pytest.mark.asyncio
async def test_send_weixin_direct_reuses_same_loop_session():
    """When the live adapter's session belongs to the SAME event loop,
    it should be reused (the fast path)."""

    current_loop = asyncio.get_running_loop()
    session = _make_mock_session(loop=current_loop)
    adapter = _make_mock_adapter(session)

    with patch.dict("gateway.platforms.weixin._LIVE_ADAPTERS", {"tok": adapter}), \
         patch("gateway.platforms.weixin.ContextTokenStore") as MockCTS, \
         patch("gateway.platforms.weixin.get_hermes_home", return_value="/tmp"):

        MockCTS.return_value.restore = MagicMock()
        MockCTS.return_value.get = MagicMock(return_value=None)

        from gateway.platforms.weixin import send_weixin_direct

        result = await send_weixin_direct(
            extra={"account_id": "acc1"},
            token="tok",
            chat_id="user1",
            message="hi",
        )

    # The live adapter's send SHOULD have been called (same loop)
    adapter.send.assert_called_once()
    assert result.get("success") is True
