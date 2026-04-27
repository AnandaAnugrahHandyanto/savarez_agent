"""Tests for BasePlatformAdapter topic-aware session handling."""

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import BasePlatformAdapter, MessageEvent, ProcessingOutcome, SendResult
from gateway.session import SessionSource, build_session_key


class DummyTelegramAdapter(BasePlatformAdapter):
    def __init__(self):
        super().__init__(PlatformConfig(enabled=True, token="fake-token"), Platform.TELEGRAM)
        self.sent = []
        self.image_files = []
        self.remote_images = []
        self.typing = []
        self.processing_hooks = []

    async def connect(self) -> bool:
        return True

    async def disconnect(self) -> None:
        return None

    async def send(self, chat_id, content, reply_to=None, metadata=None) -> SendResult:
        self.sent.append(
            {
                "chat_id": chat_id,
                "content": content,
                "reply_to": reply_to,
                "metadata": metadata,
            }
        )
        return SendResult(success=True, message_id="1")

    async def send_image_file(self, chat_id, image_path, caption=None, reply_to=None, **kwargs) -> SendResult:
        self.image_files.append(
            {
                "chat_id": chat_id,
                "image_path": image_path,
                "caption": caption,
                "reply_to": reply_to,
                "metadata": kwargs.get("metadata"),
            }
        )
        return SendResult(success=True, message_id="img1")

    async def send_image(self, chat_id, image_url, caption=None, reply_to=None, metadata=None) -> SendResult:
        self.remote_images.append(
            {
                "chat_id": chat_id,
                "image_url": image_url,
                "caption": caption,
                "reply_to": reply_to,
                "metadata": metadata,
            }
        )
        return SendResult(success=True, message_id="remote-img1")

    async def send_typing(self, chat_id: str, metadata=None) -> None:
        self.typing.append({"chat_id": chat_id, "metadata": metadata})
        return None

    async def get_chat_info(self, chat_id: str):
        return {"id": chat_id}

    async def on_processing_start(self, event: MessageEvent) -> None:
        self.processing_hooks.append(("start", event.message_id))

    async def on_processing_complete(self, event: MessageEvent, outcome: ProcessingOutcome) -> None:
        self.processing_hooks.append(("complete", event.message_id, outcome))


def _make_event(chat_id: str, thread_id: str, message_id: str = "1") -> MessageEvent:
    return MessageEvent(
        text="hello",
        source=SessionSource(
            platform=Platform.TELEGRAM,
            chat_id=chat_id,
            chat_type="group",
            thread_id=thread_id,
        ),
        message_id=message_id,
    )


class TestBasePlatformTopicSessions:
    @pytest.mark.asyncio
    async def test_handle_message_does_not_interrupt_different_topic(self, monkeypatch):
        adapter = DummyTelegramAdapter()
        adapter.set_message_handler(lambda event: asyncio.sleep(0, result=None))

        active_event = _make_event("-1001", "10")
        adapter._active_sessions[build_session_key(active_event.source)] = asyncio.Event()

        scheduled = []

        def fake_create_task(coro):
            scheduled.append(coro)
            coro.close()
            return SimpleNamespace()

        monkeypatch.setattr(asyncio, "create_task", fake_create_task)

        await adapter.handle_message(_make_event("-1001", "11"))

        assert len(scheduled) == 1
        assert adapter._pending_messages == {}

    @pytest.mark.asyncio
    async def test_handle_message_interrupts_same_topic(self, monkeypatch):
        adapter = DummyTelegramAdapter()
        adapter.set_message_handler(lambda event: asyncio.sleep(0, result=None))

        active_event = _make_event("-1001", "10")
        adapter._active_sessions[build_session_key(active_event.source)] = asyncio.Event()

        scheduled = []

        def fake_create_task(coro):
            scheduled.append(coro)
            coro.close()
            return SimpleNamespace()

        monkeypatch.setattr(asyncio, "create_task", fake_create_task)

        pending_event = _make_event("-1001", "10", message_id="2")
        await adapter.handle_message(pending_event)

        assert scheduled == []
        assert adapter.get_pending_message(build_session_key(pending_event.source)) == pending_event

    @pytest.mark.asyncio
    async def test_process_message_background_replies_in_same_topic(self):
        adapter = DummyTelegramAdapter()
        typing_calls = []

        async def handler(_event):
            await asyncio.sleep(0)
            return "ack"

        async def hold_typing(_chat_id, interval=2.0, metadata=None):
            typing_calls.append({"chat_id": _chat_id, "metadata": metadata})
            await asyncio.Event().wait()

        adapter.set_message_handler(handler)
        adapter._keep_typing = hold_typing

        event = _make_event("-1001", "17585")
        await adapter._process_message_background(event, build_session_key(event.source))

        assert adapter.sent == [
            {
                "chat_id": "-1001",
                "content": "ack",
                "reply_to": "1",
                "metadata": {"thread_id": "17585"},
            }
        ]
        assert typing_calls == [
            {
                "chat_id": "-1001",
                "metadata": {"thread_id": "17585"},
            }
        ]
        assert adapter.processing_hooks == [
            ("start", "1"),
            ("complete", "1", ProcessingOutcome.SUCCESS),
        ]

    @pytest.mark.asyncio
    async def test_process_message_background_routes_data_url_image_as_local_file(self, tmp_path, monkeypatch):
        from gateway.platforms import base as base_module

        monkeypatch.setattr(base_module, "IMAGE_CACHE_DIR", tmp_path)
        adapter = DummyTelegramAdapter()
        typing_calls = []
        png_data_url = (
            "data:image/png;base64,"
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
            "AAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )

        async def handler(_event):
            await asyncio.sleep(0)
            return f"Generated image:\n![tiny]({png_data_url})\nDone."

        async def hold_typing(_chat_id, interval=2.0, metadata=None):
            typing_calls.append({"chat_id": _chat_id, "metadata": metadata})
            await asyncio.Event().wait()

        adapter.set_message_handler(handler)
        adapter._keep_typing = hold_typing

        event = _make_event("-1001", "17585")
        await adapter._process_message_background(event, build_session_key(event.source))

        assert adapter.sent == [
            {
                "chat_id": "-1001",
                "content": "Generated image:\n\nDone.",
                "reply_to": "1",
                "metadata": {"thread_id": "17585"},
            }
        ]
        assert len(adapter.image_files) == 1
        image_delivery = adapter.image_files[0]
        assert image_delivery["chat_id"] == "-1001"
        assert image_delivery["caption"] == "tiny"
        assert image_delivery["metadata"] == {"thread_id": "17585"}
        image_path = Path(image_delivery["image_path"])
        assert image_path.suffix == ".png"
        assert image_path.is_file()
        assert image_path.parent == tmp_path
        assert adapter.remote_images == []
        assert "data:image" not in adapter.sent[0]["content"]
        assert "base64" not in adapter.sent[0]["content"]

    @pytest.mark.asyncio
    async def test_process_message_background_never_treats_remote_url_as_local_file(self, tmp_path, monkeypatch):
        """Remote image URLs must not be uploaded as local files even if a matching path exists."""
        adapter = DummyTelegramAdapter()
        matching_local = tmp_path / "https:" / "example.com"
        matching_local.mkdir(parents=True)
        (matching_local / "image.png").write_bytes(b"not the remote image")
        monkeypatch.chdir(tmp_path)

        async def handler(_event):
            await asyncio.sleep(0)
            return "Remote image:\n![remote](https://example.com/image.png)"

        async def hold_typing(_chat_id, interval=2.0, metadata=None):
            await asyncio.Event().wait()

        adapter.set_message_handler(handler)
        adapter._keep_typing = hold_typing

        event = _make_event("-1001", "17585")
        await adapter._process_message_background(event, build_session_key(event.source))

        assert adapter.image_files == []
        assert adapter.remote_images == [
            {
                "chat_id": "-1001",
                "image_url": "https://example.com/image.png",
                "caption": "remote",
                "reply_to": None,
                "metadata": {"thread_id": "17585"},
            }
        ]

    @pytest.mark.asyncio
    async def test_process_message_background_marks_total_send_failure_unsuccessful(self):
        adapter = DummyTelegramAdapter()

        async def handler(_event):
            await asyncio.sleep(0)
            return "ack"

        async def failing_send(*_args, **_kwargs):
            return SendResult(success=False, error="send failed")

        async def hold_typing(_chat_id, interval=2.0, metadata=None):
            await asyncio.Event().wait()

        adapter.set_message_handler(handler)
        adapter.send = failing_send
        adapter._keep_typing = hold_typing

        event = _make_event("-1001", "17585")
        await adapter._process_message_background(event, build_session_key(event.source))

        assert adapter.processing_hooks == [
            ("start", "1"),
            ("complete", "1", ProcessingOutcome.FAILURE),
        ]

    @pytest.mark.asyncio
    async def test_process_message_background_marks_exception_unsuccessful(self):
        adapter = DummyTelegramAdapter()

        async def handler(_event):
            await asyncio.sleep(0)
            raise RuntimeError("boom")

        async def hold_typing(_chat_id, interval=2.0, metadata=None):
            await asyncio.Event().wait()

        adapter.set_message_handler(handler)
        adapter._keep_typing = hold_typing

        event = _make_event("-1001", "17585")
        await adapter._process_message_background(event, build_session_key(event.source))

        assert adapter.processing_hooks == [
            ("start", "1"),
            ("complete", "1", ProcessingOutcome.FAILURE),
        ]

    @pytest.mark.asyncio
    async def test_process_message_background_marks_cancellation_unsuccessful(self):
        adapter = DummyTelegramAdapter()
        release = asyncio.Event()

        async def handler(_event):
            await release.wait()
            return "ack"

        async def hold_typing(_chat_id, interval=2.0, metadata=None):
            await asyncio.Event().wait()

        adapter.set_message_handler(handler)
        adapter._keep_typing = hold_typing

        event = _make_event("-1001", "17585")
        task = asyncio.create_task(adapter._process_message_background(event, build_session_key(event.source)))
        await asyncio.sleep(0)
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        assert adapter.processing_hooks == [
            ("start", "1"),
            ("complete", "1", ProcessingOutcome.FAILURE),
        ]

    @pytest.mark.asyncio
    async def test_cancel_background_tasks_marks_expected_cancellation_cancelled(self):
        adapter = DummyTelegramAdapter()
        release = asyncio.Event()

        async def handler(_event):
            await release.wait()
            return "ack"

        async def hold_typing(_chat_id, interval=2.0, metadata=None):
            await asyncio.Event().wait()

        adapter.set_message_handler(handler)
        adapter._keep_typing = hold_typing

        event = _make_event("-1001", "17585")
        await adapter.handle_message(event)
        await asyncio.sleep(0)

        await adapter.cancel_background_tasks()

        assert adapter.processing_hooks == [
            ("start", "1"),
            ("complete", "1", ProcessingOutcome.CANCELLED),
        ]
