"""Telegram adapter resilience when Bot API connectivity fails during startup/send."""

from types import SimpleNamespace

import pytest

from gateway.config import PlatformConfig
from gateway.platforms import telegram as telegram_mod
from gateway.platforms.base import SendResult
from gateway.platforms.telegram import TelegramAdapter


class _UninitializedBot:
    def __init__(self):
        self._initialized = False
        self.send_message_calls = 0

    async def send_message(self, **kwargs):  # pragma: no cover - should not be reached
        self.send_message_calls += 1
        raise RuntimeError("ExtBot is not properly initialized. Call `ExtBot.initialize` before accessing this property.")


class _FakeUpdater:
    running = False


class _FakeApplication:
    def __init__(self):
        self.bot = _UninitializedBot()
        self.updater = _FakeUpdater()
        self.running = False
        self.shutdown_calls = 0

    def add_handler(self, handler):
        pass

    async def initialize(self):
        raise OSError("simulated Telegram Bot API timeout")

    async def shutdown(self):
        self.shutdown_calls += 1


class _FakeBuilder:
    app = None

    def token(self, token):
        return self

    def request(self, request):
        return self

    def get_updates_request(self, request):
        return self

    def build(self):
        self.app = _FakeApplication()
        return self.app


class _FakeApplicationFactory:
    builder_instance = None

    @classmethod
    def builder(cls):
        cls.builder_instance = _FakeBuilder()
        return cls.builder_instance


def _make_adapter() -> TelegramAdapter:
    return TelegramAdapter(PlatformConfig(enabled=True, token="123:TEST", extra={}))


@pytest.mark.asyncio
async def test_send_does_not_touch_uninitialized_bot_after_startup_failure():
    adapter = _make_adapter()
    bot = _UninitializedBot()
    adapter._bot = bot

    result = await adapter.send("12345", "hello")

    assert result == SendResult(success=False, error="Not connected")
    assert bot.send_message_calls == 0


@pytest.mark.asyncio
async def test_approval_prompt_does_not_touch_uninitialized_bot_after_startup_failure():
    adapter = _make_adapter()
    bot = _UninitializedBot()
    adapter._bot = bot

    result = await adapter.send_exec_approval(
        chat_id="12345",
        command="echo ok",
        session_key="agent:main:telegram:dm:12345",
    )

    assert result == SendResult(success=False, error="Not connected")
    assert bot.send_message_calls == 0
    assert adapter._approval_state == {}


@pytest.mark.asyncio
async def test_connect_timeout_cleans_partially_built_uninitialized_bot(monkeypatch):
    adapter = _make_adapter()
    monkeypatch.setattr(telegram_mod, "Application", _FakeApplicationFactory)

    async def _no_sleep(delay):
        pass

    monkeypatch.setattr(telegram_mod.asyncio, "sleep", _no_sleep)

    connected = await adapter.connect()

    assert connected is False
    assert adapter._bot is None
    assert adapter._app is None
    assert adapter.is_connected is False
    assert _FakeApplicationFactory.builder_instance.app.shutdown_calls == 1
