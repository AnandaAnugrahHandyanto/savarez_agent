"""Tests for generic Telegram quick-reply buttons."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

_repo = str(Path(__file__).resolve().parents[2])
if _repo not in sys.path:
    sys.path.insert(0, _repo)


def _ensure_telegram_mock():
    if "telegram" in sys.modules and hasattr(sys.modules["telegram"], "__file__"):
        return

    mod = MagicMock()
    mod.ext.ContextTypes.DEFAULT_TYPE = type(None)
    mod.constants.ParseMode.MARKDOWN = "Markdown"
    mod.constants.ParseMode.MARKDOWN_V2 = "MarkdownV2"
    mod.constants.ParseMode.HTML = "HTML"
    mod.constants.ChatType.PRIVATE = "private"
    mod.constants.ChatType.GROUP = "group"
    mod.constants.ChatType.SUPERGROUP = "supergroup"
    mod.constants.ChatType.CHANNEL = "channel"
    mod.error.NetworkError = type("NetworkError", (OSError,), {})
    mod.error.TimedOut = type("TimedOut", (OSError,), {})
    mod.error.BadRequest = type("BadRequest", (Exception,), {})
    for name in ("telegram", "telegram.ext", "telegram.constants", "telegram.request"):
        sys.modules.setdefault(name, mod)
    sys.modules.setdefault("telegram.error", mod.error)


_ensure_telegram_mock()

import gateway.platforms.telegram as telegram_mod  # noqa: E402
from gateway.config import PlatformConfig  # noqa: E402
from gateway.platforms.telegram import TelegramAdapter  # noqa: E402


def _make_adapter(extra=None):
    adapter = TelegramAdapter(PlatformConfig(enabled=True, token="token", extra=extra or {}))
    adapter._bot = AsyncMock()
    return adapter


def test_extracts_discord_component_blocks():
    components = {
        "reusable": True,
        "blocks": [
            {
                "type": "section",
                "text": "Approve?",
                "accessory": {
                    "type": "button",
                    "button": {"label": "Yes", "style": "success"},
                },
            },
            {
                "type": "actions",
                "buttons": [
                    {"label": "Review", "custom_id": "Review first"},
                    {"label": "Later"},
                ],
            },
        ],
    }

    rows = telegram_mod._extract_button_specs_from_components(components)

    assert [[button["label"] for button in row] for row in rows] == [["Yes"], ["Review", "Later"]]
    assert rows[1][0]["callback_data"] == "Review first"


def test_builds_inline_keyboard(monkeypatch):
    class FakeButton:
        def __init__(self, label, **kwargs):
            self.label = label
            self.kwargs = kwargs

    class FakeMarkup:
        def __init__(self, rows):
            self.rows = rows

    monkeypatch.setattr(telegram_mod, "InlineKeyboardButton", FakeButton)
    monkeypatch.setattr(telegram_mod, "InlineKeyboardMarkup", FakeMarkup)

    markup = telegram_mod._telegram_inline_keyboard_from_components({
        "buttons": [
            {"label": "Yes"},
            {"label": "Docs", "url": "https://example.com"},
        ]
    })

    assert markup.rows[0][0].label == "Yes"
    assert markup.rows[0][0].kwargs["callback_data"] == "qb:Yes"
    assert markup.rows[0][1].kwargs["url"] == "https://example.com"


def test_adapter_send_attaches_components_to_last_chunk(monkeypatch):
    class FakeButton:
        def __init__(self, label, **kwargs):
            self.label = label
            self.kwargs = kwargs

    class FakeMarkup:
        def __init__(self, rows):
            self.rows = rows

    monkeypatch.setattr(telegram_mod, "InlineKeyboardButton", FakeButton)
    monkeypatch.setattr(telegram_mod, "InlineKeyboardMarkup", FakeMarkup)

    adapter = _make_adapter()
    msg = MagicMock(message_id=123)
    adapter._bot.send_message = AsyncMock(return_value=msg)

    result = __import__("asyncio").run(adapter.send(
        "42",
        "Want me to continue?",
        metadata={"components": {"buttons": [{"label": "Continue"}, {"label": "Stop"}] }},
    ))

    assert result.success is True
    kwargs = adapter._bot.send_message.call_args.kwargs
    assert kwargs["reply_markup"].rows[0][0].kwargs["callback_data"] == "qb:Continue"


def test_quick_reply_callback_dispatches_as_message(monkeypatch):
    adapter = _make_adapter()
    handled = []

    async def fake_handle(event):
        handled.append(event)

    adapter.handle_message = fake_handle

    chat = MagicMock(id=42, type="private", title=None, full_name="Colm")
    message = MagicMock(chat=chat, message_thread_id=None, message_id=9, date=None)
    user = MagicMock(id=7, full_name="Colm Quish", first_name="Colm")
    query = MagicMock(data="qb:Continue", message=message, from_user=user)
    query.answer = AsyncMock()
    query.edit_message_reply_markup = AsyncMock()
    update = MagicMock(callback_query=query, update_id=99)

    __import__("asyncio").run(adapter._handle_callback_query(update, MagicMock()))

    assert len(handled) == 1
    assert handled[0].text == "Continue"
    assert handled[0].source.chat_id == "42"
    assert handled[0].source.user_id == "7"
    query.edit_message_reply_markup.assert_awaited_once_with(reply_markup=None)
