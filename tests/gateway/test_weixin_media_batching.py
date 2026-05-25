"""Tests for WeixinAdapter media burst batching.

When a Weixin user sends multiple files in rapid succession, each file
arrives as an independent inbound event. The adapter should buffer them
into a sliding window and dispatch a single merged ``handle_message``
call to avoid hitting the gateway's interrupt-recursion guard.
"""

import asyncio
from unittest.mock import AsyncMock

import pytest

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import MessageEvent, MessageType, SessionSource
from gateway.platforms.weixin import WeixinAdapter


def _make_adapter(batch_delay: float = 0.1) -> WeixinAdapter:
    """Build a minimal WeixinAdapter for batching tests."""
    adapter = object.__new__(WeixinAdapter)
    adapter.platform = Platform.WEIXIN
    adapter.config = PlatformConfig(enabled=True, token="test-token")
    adapter._pending_media_batches = {}
    adapter._pending_media_batch_tasks = {}
    adapter._media_batch_delay_seconds = batch_delay
    adapter.handle_message = AsyncMock()
    return adapter


def _make_media_event(
    path: str,
    chat_id: str = "weixin-chat",
    text: str = "",
) -> MessageEvent:
    return MessageEvent(
        text=text,
        message_type=MessageType.DOCUMENT,
        source=SessionSource(platform=Platform.WEIXIN, chat_id=chat_id, chat_type="dm"),
        media_urls=[path],
        media_types=["application/octet-stream"],
    )


class TestWeixinMediaBurstBatching:
    @pytest.mark.asyncio
    async def test_single_file_dispatches_once_after_window(self):
        """A single file enqueue produces exactly one handle_message call."""
        adapter = _make_adapter()
        event = _make_media_event("/tmp/a.docx")

        adapter._enqueue_media_event("k", event)

        # Not yet dispatched; flush is debounced.
        adapter.handle_message.assert_not_called()

        await asyncio.sleep(0.25)

        adapter.handle_message.assert_called_once()
        dispatched = adapter.handle_message.call_args[0][0]
        assert dispatched.media_urls == ["/tmp/a.docx"]

    @pytest.mark.asyncio
    async def test_rapid_files_merge_into_single_dispatch(self):
        """Multiple rapid files in the same batch_key merge into one call."""
        adapter = _make_adapter()

        for i in range(8):
            adapter._enqueue_media_event(
                "k", _make_media_event(f"/tmp/file-{i}.docx")
            )
            await asyncio.sleep(0.01)  # within the 0.1s window

        adapter.handle_message.assert_not_called()

        await asyncio.sleep(0.25)

        adapter.handle_message.assert_called_once()
        dispatched = adapter.handle_message.call_args[0][0]
        assert len(dispatched.media_urls) == 8
        assert dispatched.media_urls[0] == "/tmp/file-0.docx"
        assert dispatched.media_urls[-1] == "/tmp/file-7.docx"

    @pytest.mark.asyncio
    async def test_cancel_restart_debounces_until_quiet(self):
        """Each new event cancels the prior flush task and restarts the timer."""
        adapter = _make_adapter(batch_delay=0.15)

        adapter._enqueue_media_event("k", _make_media_event("/tmp/a.docx"))
        first_task = adapter._pending_media_batch_tasks["k"]

        await asyncio.sleep(0.05)
        adapter._enqueue_media_event("k", _make_media_event("/tmp/b.docx"))
        second_task = adapter._pending_media_batch_tasks["k"]

        # First task should have been cancelled and replaced. Yield once so
        # the CancelledError can propagate through the awaited sleep.
        assert first_task is not second_task
        await asyncio.sleep(0)
        assert first_task.cancelled() or first_task.done()
        adapter.handle_message.assert_not_called()

        # Even after the original 0.15s would have elapsed, the second
        # event's timer has not yet fired.
        await asyncio.sleep(0.12)
        adapter.handle_message.assert_not_called()

        # Wait out the rest of the second window.
        await asyncio.sleep(0.15)
        adapter.handle_message.assert_called_once()
        dispatched = adapter.handle_message.call_args[0][0]
        assert dispatched.media_urls == ["/tmp/a.docx", "/tmp/b.docx"]

    @pytest.mark.asyncio
    async def test_different_batch_keys_dispatch_separately(self):
        """Distinct senders/chats do not collide in the same batch."""
        adapter = _make_adapter()

        adapter._enqueue_media_event(
            "user-a", _make_media_event("/tmp/a.docx", chat_id="chat-a")
        )
        adapter._enqueue_media_event(
            "user-b", _make_media_event("/tmp/b.docx", chat_id="chat-b")
        )

        await asyncio.sleep(0.25)

        assert adapter.handle_message.call_count == 2

    @pytest.mark.asyncio
    async def test_state_cleaned_up_after_flush(self):
        """After dispatch the pending dicts are empty."""
        adapter = _make_adapter()

        adapter._enqueue_media_event("k", _make_media_event("/tmp/a.docx"))
        await asyncio.sleep(0.25)

        assert adapter._pending_media_batches == {}
        assert adapter._pending_media_batch_tasks == {}


class TestWeixinMediaBatchConfig:
    """Config parsing must honor an explicit ``0`` from operator config."""

    def test_zero_in_extra_config_disables_batching(self, monkeypatch):
        """``extra.media_batch_delay_seconds: 0`` must not fall through to env default."""
        monkeypatch.setenv("WEIXIN_MEDIA_BATCH_DELAY_SECONDS", "5.0")
        adapter = WeixinAdapter(
            PlatformConfig(
                enabled=True,
                token="test-token",
                extra={"account_id": "test-account", "media_batch_delay_seconds": 0},
            )
        )
        assert adapter._media_batch_delay_seconds == 0.0

    def test_missing_config_uses_env_var(self, monkeypatch):
        monkeypatch.setenv("WEIXIN_MEDIA_BATCH_DELAY_SECONDS", "3.5")
        adapter = WeixinAdapter(
            PlatformConfig(
                enabled=True,
                token="test-token",
                extra={"account_id": "test-account"},
            )
        )
        assert adapter._media_batch_delay_seconds == 3.5

    def test_default_when_neither_config_nor_env_set(self, monkeypatch):
        monkeypatch.delenv("WEIXIN_MEDIA_BATCH_DELAY_SECONDS", raising=False)
        adapter = WeixinAdapter(
            PlatformConfig(
                enabled=True,
                token="test-token",
                extra={"account_id": "test-account"},
            )
        )
        assert adapter._media_batch_delay_seconds == 2.0
