"""Tests for Telegram send_model_picker thread_id handling.

send_model_picker was bypassing _message_thread_id_for_send() and directly
converting thread_id to int, which meant thread_id "1" (Telegram's General
topic in supergroups) was passed as message_thread_id=1.  The Telegram API
rejects this with "Message thread not found" because the General topic
doesn't use a message_thread_id parameter.

This test file guards the fix that makes send_model_picker use the same
helper methods as every other inline-keyboard method.
"""

import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway.config import PlatformConfig, Platform
from gateway.platforms.base import SendResult

# ── Fake telegram module tree ──────────────────────────────────────────

class FakeNetworkError(Exception):
    pass

class FakeBadRequest(FakeNetworkError):
    pass

_fake_telegram = types.ModuleType("telegram")
_fake_telegram.Update = object
_fake_telegram.Bot = object
_fake_telegram.Message = object

# InlineKeyboardButton / InlineKeyboardMarkup need to be callable
class _FakeInlineKeyboardButton:
    def __init__(self, text, callback_data=None, **kw):
        self.text = text
        self.callback_data = callback_data

class _FakeInlineKeyboardMarkup:
    def __init__(self, keyboard=None, **kw):
        self.keyboard = keyboard or []

_fake_telegram.InlineKeyboardButton = _FakeInlineKeyboardButton
_fake_telegram.InlineKeyboardMarkup = _FakeInlineKeyboardMarkup

_fake_telegram_error = types.ModuleType("telegram.error")
_fake_telegram_error.NetworkError = FakeNetworkError
_fake_telegram_error.BadRequest = FakeBadRequest
_fake_telegram.error = _fake_telegram_error

_fake_telegram_constants = types.ModuleType("telegram.constants")
_fake_telegram_constants.ParseMode = SimpleNamespace(MARKDOWN="Markdown", MARKDOWN_V2="MarkdownV2")
_fake_telegram_constants.ChatType = SimpleNamespace(
    GROUP="group",
    SUPERGROUP="supergroup",
    CHANNEL="channel",
)
_fake_telegram.constants = _fake_telegram_constants

_fake_telegram_ext = types.ModuleType("telegram.ext")
_fake_telegram_ext.Application = object
_fake_telegram_ext.CommandHandler = object
_fake_telegram_ext.CallbackQueryHandler = object
_fake_telegram_ext.MessageHandler = object
_fake_telegram_ext.ContextTypes = SimpleNamespace(DEFAULT_TYPE=object)
_fake_telegram_ext.filters = object

_fake_telegram_request = types.ModuleType("telegram.request")
_fake_telegram_request.HTTPXRequest = object


@pytest.fixture(autouse=True)
def _inject_fake_telegram(monkeypatch):
    """Inject fake telegram modules so the adapter can import from them."""
    monkeypatch.setitem(sys.modules, "telegram", _fake_telegram)
    monkeypatch.setitem(sys.modules, "telegram.error", _fake_telegram_error)
    monkeypatch.setitem(sys.modules, "telegram.constants", _fake_telegram_constants)
    monkeypatch.setitem(sys.modules, "telegram.ext", _fake_telegram_ext)
    monkeypatch.setitem(sys.modules, "telegram.request", _fake_telegram_request)


def _make_adapter():
    from gateway.platforms.telegram import TelegramAdapter

    config = PlatformConfig(enabled=True, token="fake-token")
    adapter = object.__new__(TelegramAdapter)
    adapter.config = config
    adapter._config = config
    adapter._platform = Platform.TELEGRAM
    adapter._connected = True
    adapter._dm_topics = {}
    adapter._dm_topics_config = []
    adapter._reply_to_mode = "first"
    adapter._fallback_ips = []
    adapter._polling_conflict_count = 0
    adapter._polling_network_error_count = 0
    adapter._polling_error_callback_ref = None
    adapter.platform = Platform.TELEGRAM
    return adapter


# ── Tests ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_model_picker_omits_general_topic_thread_id():
    """send_model_picker in a forum General topic should NOT pass
    message_thread_id=1 (which Telegram rejects with 'Message thread not found').
    It should omit the parameter entirely, just like send() does.
    """
    from gateway.platforms.telegram import TelegramAdapter

    adapter = _make_adapter()
    call_log = []

    async def mock_send_message(**kwargs):
        call_log.append(dict(kwargs))
        return SimpleNamespace(message_id=99)

    adapter._bot = SimpleNamespace(send_message=mock_send_message)
    adapter._model_picker_state = {}

    # Mock provider list
    providers = [
        {"slug": "test-provider", "name": "Test Provider", "models": ["gpt-4"], "total_models": 1, "is_current": True},
    ]

    result = await adapter.send_model_picker(
        chat_id="-100123456",
        providers=providers,
        current_model="gpt-4",
        current_provider="test-provider",
        session_key="test-session",
        on_model_selected=lambda *a, **kw: None,
        metadata={"thread_id": "1"},  # General topic thread_id
    )

    assert result.success is True
    assert len(call_log) == 1
    # The critical assertion: message_thread_id must NOT be 1
    # (General topic should omit it entirely)
    assert call_log[0].get("message_thread_id") is None


@pytest.mark.asyncio
async def test_send_model_picker_preserves_real_topic_thread_id():
    """send_model_picker in a real (non-General) topic should pass
    message_thread_id=<int> correctly.
    """
    adapter = _make_adapter()
    call_log = []

    async def mock_send_message(**kwargs):
        call_log.append(dict(kwargs))
        return SimpleNamespace(message_id=100)

    adapter._bot = SimpleNamespace(send_message=mock_send_message)
    adapter._model_picker_state = {}

    providers = [
        {"slug": "test-provider", "name": "Test Provider", "models": ["gpt-4"], "total_models": 1, "is_current": True},
    ]

    result = await adapter.send_model_picker(
        chat_id="-100123456",
        providers=providers,
        current_model="gpt-4",
        current_provider="test-provider",
        session_key="test-session",
        on_model_selected=lambda *a, **kw: None,
        metadata={"thread_id": "42"},  # A real topic, not General
    )

    assert result.success is True
    assert len(call_log) == 1
    assert call_log[0]["message_thread_id"] == 42


@pytest.mark.asyncio
async def test_send_model_picker_no_metadata_no_thread_id():
    """send_model_picker with no metadata should not set message_thread_id."""
    adapter = _make_adapter()
    call_log = []

    async def mock_send_message(**kwargs):
        call_log.append(dict(kwargs))
        return SimpleNamespace(message_id=101)

    adapter._bot = SimpleNamespace(send_message=mock_send_message)
    adapter._model_picker_state = {}

    providers = [
        {"slug": "test-provider", "name": "Test Provider", "models": ["gpt-4"], "total_models": 1, "is_current": True},
    ]

    result = await adapter.send_model_picker(
        chat_id="-100123456",
        providers=providers,
        current_model="gpt-4",
        current_provider="test-provider",
        session_key="test-session",
        on_model_selected=lambda *a, **kw: None,
        metadata=None,
    )

    assert result.success is True
    assert len(call_log) == 1
    assert "message_thread_id" not in call_log[0] or call_log[0].get("message_thread_id") is None