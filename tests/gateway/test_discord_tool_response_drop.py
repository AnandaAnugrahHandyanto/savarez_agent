"""Regression tests for Discord tool-using response silent drop (issue #29346).

When the agent returns a non-empty response that the extract pipeline
(extract_media / extract_images / extract_local_files / inline directive
strips) happens to reduce to an empty string, the ``if text_content:`` guard
in ``BasePlatformAdapter._process_message_background`` previously bypassed
the send entirely. The symptom was a ``response ready`` log followed by
silence — no ``Sending response`` line, no error — and the final answer
never reaching the Discord channel.

The fix preserves the pre-extract response and, when no native attachment
was produced to deliver in its place, sanitizes the original text and
sends it as a fallback (with a WARNING log so the silent-drop pattern is
observable next time it happens).
"""

import asyncio
import logging

import pytest

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import (
    BasePlatformAdapter,
    MessageEvent,
    SendResult,
)
from gateway.session import SessionSource, build_session_key


class DummyDiscordAdapter(BasePlatformAdapter):
    """Minimal BasePlatformAdapter wired to Platform.DISCORD for dispatch tests."""

    def __init__(self):
        super().__init__(PlatformConfig(enabled=True, token="fake-token"), Platform.DISCORD)
        self.sent: list[dict] = []

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
        return SendResult(success=True, message_id="discord-1")

    async def send_typing(self, chat_id: str, metadata=None) -> None:
        return None

    async def get_chat_info(self, chat_id: str):
        return {"id": chat_id}


class DummyTelegramAdapter(BasePlatformAdapter):
    """Non-Discord adapter used to assert the fallback is Discord-scoped."""

    def __init__(self):
        super().__init__(PlatformConfig(enabled=True, token="fake-token"), Platform.TELEGRAM)
        self.sent: list[dict] = []

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
        return SendResult(success=True, message_id="tg-1")

    async def send_typing(self, chat_id: str, metadata=None) -> None:
        return None

    async def get_chat_info(self, chat_id: str):
        return {"id": chat_id}


def _make_event(platform: Platform, chat_id: str = "111", message_id: str = "m1") -> MessageEvent:
    return MessageEvent(
        text="hello",
        source=SessionSource(
            platform=platform,
            chat_id=chat_id,
            chat_type="dm",
        ),
        message_id=message_id,
    )


async def _hold_typing(_chat_id, interval=2.0, metadata=None, stop_event=None):
    if stop_event is not None:
        await stop_event.wait()
    else:
        await asyncio.Event().wait()


class TestDiscordEmptyAfterStripFallback:
    """When extract pipeline strips a non-empty response to empty on Discord,
    the original response (sanitized) must still be delivered (#29346)."""

    @pytest.mark.asyncio
    async def test_response_reduced_to_empty_is_recovered_and_sent(self, monkeypatch, caplog):
        """Simulate the exact failure mode: handler returns non-empty content
        but the extract pipeline strips it to empty.  Patch the extract helpers
        on the adapter instance to be deterministic — the bug is in the SEND
        path's handling of an empty result, not the strip heuristics themselves.
        """
        adapter = DummyDiscordAdapter()
        adapter._keep_typing = _hold_typing

        tool_response = (
            "Based on my search, the cheapest TPE-PAR flight on Dec 14 is $632 "
            "via Saudia. Here are the top options sorted by price..."
        ) * 5  # Mimic a 1000+ char tool-using response from the issue
        assert len(tool_response) > 500

        async def handler(_event):
            return tool_response

        adapter.set_message_handler(handler)

        # Force the strip pipeline to reduce text_content to "" — this is what
        # made the bug invisible.  No images / local files / media extracted.
        monkeypatch.setattr(
            type(adapter), "extract_media", staticmethod(lambda content: ([], content))
        )
        monkeypatch.setattr(
            type(adapter), "extract_images", staticmethod(lambda content: ([], ""))
        )
        monkeypatch.setattr(
            type(adapter),
            "extract_local_files",
            staticmethod(lambda content: ([], "")),
        )

        event = _make_event(Platform.DISCORD)
        with caplog.at_level(logging.WARNING, logger="gateway.platforms.base"):
            await adapter._process_message_background(event, build_session_key(event.source))

        # Critical assertion: the response WAS delivered, not silently dropped.
        assert len(adapter.sent) == 1, (
            f"Expected 1 send (the recovered response), got {len(adapter.sent)}: {adapter.sent}"
        )
        assert adapter.sent[0]["content"] == tool_response

        # A WARNING must be logged so future occurrences are observable.
        warning_logs = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert any(
            "stripped to empty" in r.getMessage().lower() for r in warning_logs
        ), f"Expected 'stripped to empty' warning, got: {[r.getMessage() for r in warning_logs]}"

    @pytest.mark.asyncio
    async def test_directives_stripped_from_fallback_text(self, monkeypatch):
        """Fallback must sanitize internal directives so they don't leak to
        the user. This mirrors the strips performed on the normal path."""
        adapter = DummyDiscordAdapter()
        adapter._keep_typing = _hold_typing

        raw = (
            "[[audio_as_voice]]\n"
            "[[as_document]]\n"
            "MEDIA: /tmp/nope.ogg\n"
            "The real answer the user should see."
        )

        async def handler(_event):
            return raw

        adapter.set_message_handler(handler)

        # Pipeline reduces to empty but no attachments are produced (e.g.
        # MEDIA path didn't validate as a real file → media_files is []).
        monkeypatch.setattr(
            type(adapter), "extract_media", staticmethod(lambda content: ([], content))
        )
        monkeypatch.setattr(
            type(adapter), "extract_images", staticmethod(lambda content: ([], ""))
        )
        monkeypatch.setattr(
            type(adapter),
            "extract_local_files",
            staticmethod(lambda content: ([], "")),
        )

        event = _make_event(Platform.DISCORD)
        await adapter._process_message_background(event, build_session_key(event.source))

        assert len(adapter.sent) == 1
        delivered = adapter.sent[0]["content"]
        assert "[[audio_as_voice]]" not in delivered
        assert "[[as_document]]" not in delivered
        assert "MEDIA:" not in delivered
        assert "The real answer the user should see." in delivered

    @pytest.mark.asyncio
    async def test_no_fallback_when_attachment_produced(self, monkeypatch):
        """When an image/media/local-file attachment IS extracted, the empty
        text_content is intentional — fallback must NOT re-send the response
        text and duplicate the attachment's content."""
        adapter = DummyDiscordAdapter()
        adapter._keep_typing = _hold_typing

        async def handler(_event):
            return "![chart](https://example.com/chart.png)"

        adapter.set_message_handler(handler)

        # Simulate extract_images consuming the entire response → text empty,
        # but an image WAS extracted to send natively.
        monkeypatch.setattr(
            type(adapter), "extract_media", staticmethod(lambda content: ([], content))
        )
        monkeypatch.setattr(
            type(adapter),
            "extract_images",
            staticmethod(lambda content: ([("https://example.com/chart.png", "chart")], "")),
        )
        monkeypatch.setattr(
            type(adapter),
            "extract_local_files",
            staticmethod(lambda content: ([], "")),
        )
        # Stub the native image-send path so the test doesn't try to upload.
        adapter.send_multiple_images = lambda *a, **kw: asyncio.sleep(0, result=None)

        event = _make_event(Platform.DISCORD)
        await adapter._process_message_background(event, build_session_key(event.source))

        # No text send — the image-only response is delivered as a native
        # attachment, NOT as a text echo of the original markdown.
        assert adapter.sent == [], (
            f"Expected no text send when image attachment handles delivery, got: {adapter.sent}"
        )

    @pytest.mark.asyncio
    async def test_fallback_is_discord_scoped(self, monkeypatch):
        """Other platforms keep current behavior to avoid unintended
        regressions in their own pipelines."""
        adapter = DummyTelegramAdapter()
        adapter._keep_typing = _hold_typing

        async def handler(_event):
            return "non-empty tool reply"

        adapter.set_message_handler(handler)

        monkeypatch.setattr(
            type(adapter), "extract_media", staticmethod(lambda content: ([], content))
        )
        monkeypatch.setattr(
            type(adapter), "extract_images", staticmethod(lambda content: ([], ""))
        )
        monkeypatch.setattr(
            type(adapter),
            "extract_local_files",
            staticmethod(lambda content: ([], "")),
        )

        event = _make_event(Platform.TELEGRAM)
        await adapter._process_message_background(event, build_session_key(event.source))

        # Telegram path is unchanged: empty text_content → no send.
        assert adapter.sent == []
