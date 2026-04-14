import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.config import PlatformConfig


def _ensure_telegram_mock():
    if "telegram" in sys.modules and hasattr(sys.modules["telegram"], "__file__"):
        return

    telegram_mod = MagicMock()
    telegram_mod.ext.ContextTypes.DEFAULT_TYPE = type(None)
    telegram_mod.constants.ParseMode.MARKDOWN_V2 = "MarkdownV2"
    telegram_mod.constants.ChatType.GROUP = "group"
    telegram_mod.constants.ChatType.SUPERGROUP = "supergroup"
    telegram_mod.constants.ChatType.CHANNEL = "channel"
    telegram_mod.constants.ChatType.PRIVATE = "private"
    telegram_mod.error.NetworkError = type("NetworkError", (OSError,), {})
    telegram_mod.error.TimedOut = type("TimedOut", (OSError,), {})
    telegram_mod.error.BadRequest = type("BadRequest", (Exception,), {})

    for name in ("telegram", "telegram.ext", "telegram.constants", "telegram.request"):
        sys.modules.setdefault(name, telegram_mod)
    sys.modules.setdefault("telegram.error", telegram_mod.error)


_ensure_telegram_mock()

from gateway.platforms.base import MessageType  # noqa: E402
from gateway.platforms.telegram import TelegramAdapter  # noqa: E402


@pytest.fixture(autouse=True)
def _no_auto_discovery(monkeypatch):
    async def _noop():
        return []

    monkeypatch.setattr("gateway.platforms.telegram.discover_fallback_ips", _noop)


@pytest.mark.asyncio
async def test_handle_command_accepts_channel_posts():
    adapter = object.__new__(TelegramAdapter)
    message = SimpleNamespace(text="/sethome")
    event = object()
    adapter._should_process_message = MagicMock(return_value=True)
    adapter._build_message_event = MagicMock(return_value=event)
    adapter.handle_message = AsyncMock()

    update = SimpleNamespace(message=None, channel_post=message, edited_channel_post=None)

    await adapter._handle_command(update, None)

    adapter._should_process_message.assert_called_once_with(message, is_command=True)
    adapter._build_message_event.assert_called_once_with(message, MessageType.COMMAND)
    adapter.handle_message.assert_awaited_once_with(event)


@pytest.mark.asyncio
async def test_connect_registers_channel_post_command_handler(monkeypatch):
    adapter = TelegramAdapter(PlatformConfig(enabled=True, token="***"))

    monkeypatch.setattr(
        "gateway.status.acquire_scoped_lock",
        lambda scope, identity, metadata=None: (True, None),
    )
    monkeypatch.setattr(
        "gateway.status.release_scoped_lock",
        lambda scope, identity: None,
    )

    handlers = []
    monkeypatch.setattr(
        "gateway.platforms.telegram.TelegramMessageHandler",
        lambda filters_arg, callback: SimpleNamespace(filters=filters_arg, callback=callback),
    )

    updater = SimpleNamespace(
        start_polling=AsyncMock(),
        stop=AsyncMock(),
        running=True,
    )
    bot = SimpleNamespace(
        delete_webhook=AsyncMock(),
        set_my_commands=AsyncMock(),
    )
    app = SimpleNamespace(
        bot=bot,
        updater=updater,
        add_handler=MagicMock(side_effect=handlers.append),
        initialize=AsyncMock(),
        start=AsyncMock(),
    )
    builder = MagicMock()
    builder.token.return_value = builder
    builder.request.return_value = builder
    builder.get_updates_request.return_value = builder
    builder.base_url.return_value = builder
    builder.base_file_url.return_value = builder
    builder.build.return_value = app
    monkeypatch.setattr(
        "gateway.platforms.telegram.Application",
        SimpleNamespace(builder=MagicMock(return_value=builder)),
    )

    ok = await adapter.connect()

    assert ok is True
    command_handlers = [
        handler for handler in handlers
        if getattr(handler, "callback", None) == adapter._handle_command
    ]
    assert len(command_handlers) >= 2
    assert any("CHANNEL_POSTS" in repr(getattr(handler, "filters", "")) for handler in command_handlers)
