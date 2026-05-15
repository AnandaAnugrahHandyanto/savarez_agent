from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from gateway.config import Platform
from gateway.platforms.telegram import ParseMode, TelegramAdapter, _strip_mdv2
from tools import slash_confirm


@pytest.mark.asyncio
async def test_slash_confirm_callback_retries_plain_text_on_markdown_parse_error(monkeypatch):
    """Telegram callback follow-up should not get stuck on Markdown parse errors.

    /new with "Always Approve" can return a reset banner plus config note. If
    Telegram rejects the MarkdownV2 parse, the callback must still send the
    result as plain text instead of leaving the user at a resolved prompt.
    """
    monkeypatch.delenv("TELEGRAM_ALLOWED_USERS", raising=False)

    adapter = object.__new__(TelegramAdapter)
    adapter.platform = Platform.TELEGRAM
    adapter._slash_confirm_state = {"42": "session-key"}
    adapter._approval_state = {}
    adapter._clarify_state = {}
    adapter._disable_link_previews = False
    adapter._message_handler = None

    send_calls = []

    async def fake_send(**kwargs):
        send_calls.append(dict(kwargs))
        if len(send_calls) == 1:
            raise RuntimeError(
                "Can't parse entities: can't find end of the entity starting at byte offset 20"
            )
        return SimpleNamespace(message_id=123)

    adapter._send_message_with_thread_fallback = fake_send

    async def handler(choice: str):
        assert choice == "always"
        return (
            "✨ Session reset! Starting fresh.\n\n"
            "ℹ️ Future /clear, /new, /reset, and /undo will run without confirmation. "
            "Re-enable via `approvals.destructive_slash_confirm: true` in config.yaml."
        )

    slash_confirm.register("session-key", "42", "new", handler)

    query = SimpleNamespace(
        data="sc:always:42",
        from_user=SimpleNamespace(id="12345", first_name="Thammachet"),
        message=SimpleNamespace(
            chat_id=999,
            chat=SimpleNamespace(type="private"),
            message_id=777,
            message_thread_id=None,
            text="prompt text",
        ),
        answer=AsyncMock(),
        edit_message_text=AsyncMock(),
    )
    update = SimpleNamespace(callback_query=query)

    await adapter._handle_callback_query(update, SimpleNamespace())

    assert len(send_calls) == 2
    assert send_calls[0]["parse_mode"] == ParseMode.MARKDOWN_V2
    assert "parse_mode" not in send_calls[1]
    assert send_calls[1]["text"] == _strip_mdv2(send_calls[0]["text"])
    assert query.answer.await_count == 1
