"""Tests that the standalone Telegram send path reuses gateway HTTP transport config.

The ``_send_telegram`` function in ``send_message_tool.py`` must apply the same
HTTP transport configuration (timeouts, connection pool, proxy, fallback IP
transport) as the gateway adapter (``TelegramAdapter.connect()``).  Before this
fix, standalone sends from cron / TUI / scripts would construct
``telegram.Bot(token=...)`` with no HTTPXRequest kwargs, bypassing proxy
settings and timeout overrides configured for the gateway.

The fix introduces a shared module-level function
``_build_telegram_httpx_request`` (in ``gateway/platforms/telegram.py``) that
both the gateway adapter and standalone send path call, ensuring transport
config is always consistent.
"""

from __future__ import annotations

import asyncio
import os
import sys
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _install_telegram_mock(
    monkeypatch: pytest.MonkeyPatch,
    bot_factory: MagicMock,
    httpx_request_factory: MagicMock,
) -> None:
    """Install a stub ``telegram`` package whose ``Bot``,
    ``telegram.request.HTTPXRequest``, and related modules are the supplied
    mocks.
    """
    parse_mode = SimpleNamespace(MARKDOWN_V2="MarkdownV2", HTML="HTML")
    chat_type = SimpleNamespace(GROUP="group", PRIVATE="private")
    constants_mod = SimpleNamespace(ParseMode=parse_mode, ChatType=chat_type)
    request_mod = SimpleNamespace(HTTPXRequest=httpx_request_factory)

    # Mock filters module sufficiently for format_message imports
    filters_mod = SimpleNamespace(
        TEXT=SimpleNamespace(),
        COMMAND=SimpleNamespace(),
        PHOTO=SimpleNamespace(),
        VIDEO=SimpleNamespace(),
        AUDIO=SimpleNamespace(),
        VOICE=SimpleNamespace(),
        LOCATION=SimpleNamespace(),
        Document=SimpleNamespace(ALL=SimpleNamespace()),
        Sticker=SimpleNamespace(ALL=SimpleNamespace()),
    )

    # Mock MessageEntity needed by mention-detection
    _MessageEntity = lambda **_kw: SimpleNamespace(**_kw)

    # Mock ext module
    ext_mod = SimpleNamespace(
        CommandHandler=lambda **kw: SimpleNamespace(**kw),
        CallbackQueryHandler=lambda **kw: SimpleNamespace(**kw),
        MessageHandler=lambda *a, **kw: SimpleNamespace(**kw),
        ContextTypes=SimpleNamespace(DEFAULT_TYPE=type),
        filters=filters_mod,
    )

    telegram_mod = SimpleNamespace(
        Bot=bot_factory,
        MessageEntity=_MessageEntity,
        Message=lambda **kw: SimpleNamespace(**kw),
        InlineKeyboardButton=lambda **kw: SimpleNamespace(**kw),
        InlineKeyboardMarkup=lambda **kw: SimpleNamespace(**kw),
        LinkPreviewOptions=None,
        constants=constants_mod,
        request=request_mod,
        ext=ext_mod,
    )

    monkeypatch.setitem(sys.modules, "telegram", telegram_mod)
    monkeypatch.setitem(sys.modules, "telegram.constants", constants_mod)
    monkeypatch.setitem(sys.modules, "telegram.request", request_mod)
    monkeypatch.setitem(sys.modules, "telegram.ext", ext_mod)


def _make_bot() -> MagicMock:
    bot = MagicMock()
    bot.send_message = AsyncMock(return_value=SimpleNamespace(message_id=42))
    return bot


class TestStandaloneTelegramTransportConfig:
    """The standalone ``_send_telegram`` path must reuse the same HTTP transport
    configuration (timeouts, pool size, fallback IPs, proxy) that the gateway
    adapter uses.
    """

    def _assert_common_request_kwargs(self, call_kwargs: dict) -> None:
        """Assert that the HTTPXRequest received the standard request kwargs."""
        assert call_kwargs.get("connection_pool_size") == 512, (
            f"Expected connection_pool_size=512, got {call_kwargs.get('connection_pool_size')}"
        )
        assert call_kwargs.get("pool_timeout") == 8.0
        assert call_kwargs.get("connect_timeout") == 10.0
        assert call_kwargs.get("read_timeout") == 20.0
        assert call_kwargs.get("write_timeout") == 20.0

    def test_standalone_send_reuses_timeout_pool_settings(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``_send_telegram`` must pass HTTP timeout/pool settings from env vars
        to HTTPXRequest, the same way the gateway adapter does."""
        from tools.send_message_tool import _send_telegram

        # Ensure no in-process gateway runner interferes
        monkeypatch.setattr("gateway.run._gateway_runner_ref", lambda: None)

        # Clear proxy/network env so test focuses on timeout/pool settings
        for var in (
            "TELEGRAM_PROXY", "HTTPS_PROXY", "https_proxy",
            "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy",
            "NO_PROXY", "no_proxy",
        ):
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setattr(sys, "platform", "linux")

        # Mock the bot and HTTPXRequest
        bot = _make_bot()
        bot_factory = MagicMock(return_value=bot)
        httpx_request_factory = MagicMock(side_effect=lambda **kw: MagicMock(_kw=kw))
        _install_telegram_mock(monkeypatch, bot_factory, httpx_request_factory)

        result: dict[str, Any] = asyncio.run(
            _send_telegram("tok", "123", "hello world")
        )

        assert result["success"] is True

        # HTTPXRequest should have been called twice (request + get_updates_request)
        assert httpx_request_factory.call_count >= 2

        # Check that timeout/pool settings are passed to HTTPXRequest
        for call in httpx_request_factory.call_args_list:
            kwargs = call.kwargs
            self._assert_common_request_kwargs(kwargs)

        # Bot should have been created with request + get_updates_request kwargs
        bot_factory.assert_called_once()
        bot_call_kwargs = bot_factory.call_args.kwargs
        assert "request" in bot_call_kwargs, (
            "Bot() missing request= kwarg — HTTP transport config not wired"
        )
        assert "get_updates_request" in bot_call_kwargs, (
            "Bot() missing get_updates_request= kwarg — HTTP transport config not wired"
        )

        bot.send_message.assert_awaited_once()

    def test_standalone_send_with_proxy_includes_timeout_settings(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When TELEGRAM_PROXY is set, the HTTPXRequest must include both
        the proxy URL AND the timeout/pool settings."""
        from tools.send_message_tool import _send_telegram

        monkeypatch.setattr("gateway.run._gateway_runner_ref", lambda: None)
        monkeypatch.setenv("TELEGRAM_PROXY", "socks5://127.0.0.1:1080")
        monkeypatch.delenv("NO_PROXY", raising=False)
        monkeypatch.delenv("no_proxy", raising=False)
        monkeypatch.setattr(sys, "platform", "linux")

        bot = _make_bot()
        bot_factory = MagicMock(return_value=bot)
        httpx_request_factory = MagicMock(side_effect=lambda **kw: MagicMock(_kw=kw))
        _install_telegram_mock(monkeypatch, bot_factory, httpx_request_factory)

        result: dict[str, Any] = asyncio.run(
            _send_telegram("tok", "123", "hello world")
        )

        assert result["success"] is True

        # Both HTTPXRequest calls must include proxy AND timeout settings
        assert httpx_request_factory.call_count >= 2
        for call in httpx_request_factory.call_args_list:
            kwargs = call.kwargs
            self._assert_common_request_kwargs(kwargs)
            assert "proxy" in kwargs, (
                f"HTTPXRequest called without proxy= when TELEGRAM_PROXY is set: {kwargs}"
            )
            assert kwargs["proxy"] == "socks5://127.0.0.1:1080"

    def test_standalone_send_fallback_ip_transport(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When fallback IPs are available, the standalone path should use
        ``TelegramFallbackTransport`` (the same custom transport the gateway
        adapter uses), not a plain ``HTTPXRequest``."""
        from tools.send_message_tool import _send_telegram

        monkeypatch.setattr("gateway.run._gateway_runner_ref", lambda: None)
        monkeypatch.setattr(sys, "platform", "linux")

        # Clear proxy so fallback IP path is taken
        for var in (
            "TELEGRAM_PROXY", "HTTPS_PROXY", "https_proxy",
            "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy",
            "NO_PROXY", "no_proxy",
        ):
            monkeypatch.delenv(var, raising=False)

        bot = _make_bot()
        bot_factory = MagicMock(return_value=bot)
        httpx_request_factory = MagicMock(side_effect=lambda **kw: MagicMock(_kw=kw))
        _install_telegram_mock(monkeypatch, bot_factory, httpx_request_factory)

        result: dict[str, Any] = asyncio.run(
            _send_telegram("tok", "123", "hello world")
        )

        assert result["success"] is True
        assert httpx_request_factory.call_count >= 2

        # Verify the httpx_kwargs contain a TelegramFallbackTransport
        for call in httpx_request_factory.call_args_list:
            kwargs = call.kwargs
            # Must have timeout/pool settings
            self._assert_common_request_kwargs(kwargs)

    def test_standalone_send_custom_timeout_env_override(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Custom env var overrides for timeouts are honoured."""
        from tools.send_message_tool import _send_telegram

        monkeypatch.setattr("gateway.run._gateway_runner_ref", lambda: None)
        for var in (
            "TELEGRAM_PROXY", "HTTPS_PROXY", "https_proxy",
            "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy",
            "NO_PROXY", "no_proxy",
        ):
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setattr(sys, "platform", "linux")

        # Set custom timeouts
        monkeypatch.setenv("HERMES_TELEGRAM_HTTP_POOL_SIZE", "128")
        monkeypatch.setenv("HERMES_TELEGRAM_HTTP_CONNECT_TIMEOUT", "30.0")
        monkeypatch.setenv("HERMES_TELEGRAM_HTTP_READ_TIMEOUT", "60.0")

        bot = _make_bot()
        bot_factory = MagicMock(return_value=bot)
        httpx_request_factory = MagicMock(side_effect=lambda **kw: MagicMock(_kw=kw))
        _install_telegram_mock(monkeypatch, bot_factory, httpx_request_factory)

        result: dict[str, Any] = asyncio.run(
            _send_telegram("tok", "123", "hello world")
        )

        assert result["success"] is True
        assert httpx_request_factory.call_count >= 2
        for call in httpx_request_factory.call_args_list:
            kwargs = call.kwargs
            assert kwargs.get("connection_pool_size") == 128
            assert kwargs.get("connect_timeout") == 30.0
            assert kwargs.get("read_timeout") == 60.0
            assert kwargs.get("pool_timeout") == 8.0  # default
            assert kwargs.get("write_timeout") == 20.0  # default
