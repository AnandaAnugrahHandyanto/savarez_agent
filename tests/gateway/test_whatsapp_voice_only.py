import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import BasePlatformAdapter, MessageEvent, MessageType, SendResult
from gateway.session import SessionSource


class _FakePlatformAdapter(BasePlatformAdapter):
    def __init__(self, platform: Platform = Platform.WHATSAPP):
        super().__init__(PlatformConfig(enabled=True, extra={}), platform)
        self.sent_messages = []
        self.sent_voices = []

    async def connect(self) -> bool:
        return True

    async def disconnect(self) -> None:
        return None

    async def send(self, chat_id: str, content: str, reply_to=None, metadata=None) -> SendResult:
        self.sent_messages.append(
            {
                "chat_id": chat_id,
                "content": content,
                "reply_to": reply_to,
                "metadata": metadata,
            }
        )
        return SendResult(success=True, message_id="txt-1")

    async def send_voice(self, chat_id: str, audio_path: str, caption=None, reply_to=None, **kwargs) -> SendResult:
        self.sent_voices.append(
            {
                "chat_id": chat_id,
                "audio_path": audio_path,
                "caption": caption,
                "reply_to": reply_to,
                "kwargs": kwargs,
            }
        )
        return SendResult(success=True, message_id="voice-1")

    async def get_chat_info(self, chat_id: str):
        return {}


@pytest.mark.asyncio
async def test_whatsapp_voice_only_sends_voice_without_text(tmp_path):
    adapter = _FakePlatformAdapter(Platform.WHATSAPP)
    adapter._run_processing_hook = AsyncMock()
    adapter._keep_typing = AsyncMock()
    adapter._send_with_retry = AsyncMock(side_effect=adapter.send)

    async def _handler(_event):
        return "It lands at 8:10 p.m. Vegas time tomorrow. VS155."

    adapter.set_message_handler(_handler)

    chat_id = "179143169863708@lid"
    adapter._active_sessions = {}
    adapter._auto_tts_enabled_chats.add(chat_id)

    source = SessionSource(
        platform=Platform.WHATSAPP,
        chat_id=chat_id,
        user_id="447875356339",
        user_name="Ben Hopkins",
    )
    event = MessageEvent(
        text="",
        message_type=MessageType.VOICE,
        source=source,
        message_id="msg-1",
    )

    tts_result = '{"success": true, "file_path": "/tmp/reply.ogg"}'

    with patch("tools.tts_tool.check_tts_requirements", return_value=True), \
         patch("tools.tts_tool.text_to_speech_tool", return_value=tts_result), \
         patch("pathlib.Path.exists", return_value=True), \
         patch("os.remove"), \
         patch("os.makedirs"):
        adapter._process_message_background = BasePlatformAdapter._process_message_background.__get__(adapter)
        await adapter._process_message_background(event, session_key=chat_id)

    assert len(adapter.sent_voices) == 1
    assert adapter.sent_voices[0]["chat_id"] == chat_id
    assert adapter.sent_messages == []


@pytest.mark.asyncio
async def test_non_whatsapp_voice_reply_still_sends_text_after_voice(tmp_path):
    adapter = _FakePlatformAdapter(Platform.TELEGRAM)
    adapter._run_processing_hook = AsyncMock()
    adapter._keep_typing = AsyncMock()
    adapter._send_with_retry = AsyncMock(side_effect=adapter.send)

    async def _handler(_event):
        return "Telegram can keep the text copy."

    adapter.set_message_handler(_handler)
    adapter._auto_tts_enabled_chats.add("123")

    source = SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="123",
        user_id="u1",
        user_name="Ben Hopkins",
    )
    event = MessageEvent(
        text="",
        message_type=MessageType.VOICE,
        source=source,
        message_id="msg-2",
    )

    tts_result = '{"success": true, "file_path": "/tmp/reply.ogg"}'

    with patch("tools.tts_tool.check_tts_requirements", return_value=True), \
         patch("tools.tts_tool.text_to_speech_tool", return_value=tts_result), \
         patch("pathlib.Path.exists", return_value=True), \
         patch("os.remove"), \
         patch("os.makedirs"):
        adapter._process_message_background = BasePlatformAdapter._process_message_background.__get__(adapter)
        await adapter._process_message_background(event, session_key="123")

    assert len(adapter.sent_voices) == 1
    assert len(adapter.sent_messages) == 1
    assert adapter.sent_messages[0]["content"] == "Telegram can keep the text copy."


@pytest.mark.asyncio
async def test_whatsapp_voice_only_caps_spoken_text_for_slow_cloned_tts(tmp_path):
    adapter = _FakePlatformAdapter(Platform.WHATSAPP)
    adapter._run_processing_hook = AsyncMock()
    adapter._keep_typing = AsyncMock()
    adapter._send_with_retry = AsyncMock(side_effect=adapter.send)

    long_reply = "First sentence. " + ("This is extra spoken detail that would force another cloned voice chunk. " * 40)

    async def _handler(_event):
        return long_reply

    adapter.set_message_handler(_handler)

    chat_id = "179143169863708@lid"
    adapter._active_sessions = {}
    adapter._auto_tts_enabled_chats.add(chat_id)

    source = SessionSource(
        platform=Platform.WHATSAPP,
        chat_id=chat_id,
        user_id="447875356339",
        user_name="Ben Hopkins",
    )
    event = MessageEvent(
        text="",
        message_type=MessageType.VOICE,
        source=source,
        message_id="msg-3",
    )

    captured = {}

    def _fake_tts(*, text, output_path=None, **_kwargs):
        captured["text"] = text
        return '{"success": true, "file_path": "/tmp/reply.ogg"}'

    with patch("tools.tts_tool.check_tts_requirements", return_value=True), \
         patch("tools.tts_tool.text_to_speech_tool", side_effect=_fake_tts), \
         patch("pathlib.Path.exists", return_value=True), \
         patch("os.remove"), \
         patch("os.makedirs"):
        adapter._process_message_background = BasePlatformAdapter._process_message_background.__get__(adapter)
        await adapter._process_message_background(event, session_key=chat_id)

    assert len(adapter.sent_voices) == 1
    assert adapter.sent_messages == []
    assert captured["text"].endswith("…")
    assert len(captured["text"]) <= 321
