"""Telegram client-safe rich Markdown routing.

Bot API rich messages parse tables, GFM task lists, and <details> blocks on the
server, but clients can still show source Markdown. These tests pin the adapter's
HTML fallback path that renders cleanly in normal Telegram clients.
"""
import sys
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.config import PlatformConfig


def _ensure_telegram_mock():
    if "telegram" in sys.modules and hasattr(sys.modules["telegram"], "__file__"):
        return
    mod = MagicMock()
    mod.error.NetworkError = type("NetworkError", (OSError,), {})
    mod.error.TimedOut = type("TimedOut", (OSError,), {})
    mod.error.BadRequest = type("BadRequest", (Exception,), {})
    for name in ("telegram", "telegram.ext", "telegram.constants", "telegram.request"):
        sys.modules.setdefault(name, mod)
    sys.modules.setdefault("telegram.error", mod.error)


_ensure_telegram_mock()

from gateway.platforms.telegram import TelegramAdapter  # noqa: E402


RICH_SAMPLE = """## Sprint Status

| Task | Owner | Status |
|---|---|---|
| Driver App release | Alex | ✅ Done |
| Portal QA | Sam | In progress |

- [x] Review PR
- [ ] Run staging smoke test

<details>
<summary>Risks</summary>

- Staging data may be stale.

</details>
"""


def _make_adapter() -> TelegramAdapter:
    adapter = TelegramAdapter(PlatformConfig(enabled=True, token="***"))
    sent = MagicMock()
    sent.message_id = 42
    bot = MagicMock()
    bot._post = AsyncMock(return_value={"message_id": 42})
    bot.send_message = AsyncMock(return_value=sent)
    bot.edit_message_text = AsyncMock()
    bot.send_message_draft = AsyncMock(return_value=True)
    adapter._bot = cast(Any, bot)
    return adapter


def test_rich_markdown_to_telegram_html_formats_tables_checklists_details():
    html = TelegramAdapter._rich_markdown_to_telegram_html(RICH_SAMPLE)

    assert "<b>Sprint Status</b>" in html
    assert "<pre>Task" in html
    assert "Driver App release" in html
    assert "☑️ Review PR" in html
    assert "☐ Run staging smoke test" in html
    assert "<blockquote expandable><b>Risks</b>" in html
    assert "&lt;details&gt;" not in html
    assert "|---|---|---|" not in html


@pytest.mark.asyncio
async def test_send_uses_client_safe_html_for_tables_checklists_details():
    adapter = _make_adapter()

    result = await adapter.send("123", RICH_SAMPLE)

    bot = cast(Any, adapter._bot)
    assert result.success is True
    assert result.message_id == "42"
    bot.send_message.assert_awaited_once()
    kwargs = bot.send_message.await_args.kwargs
    assert kwargs["chat_id"] == 123
    assert kwargs["parse_mode"] == "HTML"
    assert kwargs["reply_markup"] is not None
    assert "<pre>Task" in kwargs["text"]
    assert "☑️ Review PR" in kwargs["text"]
    assert "<blockquote expandable><b>Risks</b>" in kwargs["text"]
    assert "123:42" in adapter._checklist_state
    bot._post.assert_not_awaited()


@pytest.mark.asyncio
async def test_finalize_edit_uses_client_safe_html():
    adapter = _make_adapter()

    result = await adapter.edit_message("123", "456", RICH_SAMPLE, finalize=True)

    bot = cast(Any, adapter._bot)
    assert result.success is True
    bot.edit_message_text.assert_awaited_once()
    kwargs = bot.edit_message_text.await_args.kwargs
    assert kwargs["message_id"] == 456
    assert kwargs["parse_mode"] == "HTML"
    assert kwargs["reply_markup"] is not None
    assert "<pre>Task" in kwargs["text"]
    assert "☐ Run staging smoke test" in kwargs["text"]
    assert "123:456" in adapter._checklist_state


@pytest.mark.asyncio
async def test_send_draft_disables_draft_transport_for_rich_markdown():
    adapter = _make_adapter()

    result = await adapter.send_draft("123", 7, RICH_SAMPLE)

    bot = cast(Any, adapter._bot)
    assert result.success is False
    assert result.error == "rich_markdown_requires_real_message"
    bot.send_message_draft.assert_not_awaited()
    bot._post.assert_not_awaited()


@pytest.mark.asyncio
async def test_checklist_callback_toggles_item_and_edits_message():
    adapter = _make_adapter()
    adapter._remember_checklist_message("123", "42", RICH_SAMPLE)
    message = MagicMock()
    message.chat_id = 123
    message.message_id = 42
    query = MagicMock()
    query.message = message
    query.edit_message_text = AsyncMock()
    query.answer = AsyncMock()

    await adapter._handle_checklist_callback(query, "ck:1")

    query.edit_message_text.assert_awaited_once()
    kwargs = query.edit_message_text.await_args.kwargs
    assert kwargs["parse_mode"] == "HTML"
    assert "☑️ Run staging smoke test" in kwargs["text"]
    assert kwargs["reply_markup"] is not None
    assert "- [x] Run staging smoke test" in adapter._checklist_state["123:42"]["content"]
    query.answer.assert_awaited_once_with(text="Checked")
