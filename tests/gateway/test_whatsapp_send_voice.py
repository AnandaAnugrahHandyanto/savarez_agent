"""Test for WhatsApp send_voice() override.

Regression test for #4979: WhatsApp adapter was missing send_voice() override,
causing voice messages to be sent as text instead of native audio.
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway.config import Platform
from gateway.platforms.base import SendResult


def _make_adapter():
    """Create a WhatsAppAdapter with test attributes (bypass __init__)."""
    from gateway.platforms.whatsapp import WhatsAppAdapter

    adapter = WhatsAppAdapter.__new__(WhatsAppAdapter)
    adapter.platform = Platform.WHATSAPP
    adapter.config = MagicMock()
    adapter._bridge_port = 19876
    adapter._bridge_script = "/tmp/test-bridge.js"
    adapter._session_path = Path("/tmp/test-wa-session")
    adapter._bridge_log_fh = None
    adapter._bridge_log = None
    adapter._bridge_process = None
    adapter._reply_prefix = None
    adapter._running = True
    adapter._message_handler = None
    adapter._fatal_error_code = None
    adapter._fatal_error_message = None
    adapter._fatal_error_retryable = True
    adapter._fatal_error_handler = None
    adapter._active_sessions = {}
    adapter._pending_messages = {}
    adapter._background_tasks = set()
    adapter._auto_tts_disabled_chats = set()
    adapter._message_queue = asyncio.Queue()
    adapter._http_session = MagicMock()
    return adapter


def test_send_voice_calls_send_media_to_bridge():
    """send_voice() should route audio through _send_media_to_bridge()."""
    async def run():
        adapter = _make_adapter()
        
        # Mock _send_media_to_bridge to verify it's called
        expected_result = SendResult(success=True, message_id="voice-123")
        adapter._send_media_to_bridge = AsyncMock(return_value=expected_result)
        
        result = await adapter.send_voice(
            chat_id="123456789@c.us",
            audio_path="/tmp/test-voice.ogg",
            caption="Test caption",
        )
        
        # Verify _send_media_to_bridge was called with correct args
        adapter._send_media_to_bridge.assert_called_once_with(
            "123456789@c.us",
            "/tmp/test-voice.ogg",
            "audio",
            "Test caption",
        )
        assert result == expected_result
    
    asyncio.get_event_loop().run_until_complete(run())


def test_send_voice_without_caption():
    """send_voice() should work without a caption."""
    async def run():
        adapter = _make_adapter()
        
        expected_result = SendResult(success=True, message_id="voice-456")
        adapter._send_media_to_bridge = AsyncMock(return_value=expected_result)
        
        result = await adapter.send_voice(
            chat_id="123456789@c.us",
            audio_path="/tmp/test-voice.ogg",
        )
        
        adapter._send_media_to_bridge.assert_called_once_with(
            "123456789@c.us",
            "/tmp/test-voice.ogg",
            "audio",
            None,  # No caption
        )
        assert result.success is True
    
    asyncio.get_event_loop().run_until_complete(run())


def test_send_voice_method_exists():
    """WhatsAppAdapter should have its own send_voice implementation."""
    from gateway.platforms.whatsapp import WhatsAppAdapter
    from gateway.platforms.base import BasePlatformAdapter
    
    # Verify WhatsAppAdapter has its own send_voice (not inherited from base)
    assert hasattr(WhatsAppAdapter, 'send_voice')
    assert WhatsAppAdapter.send_voice is not BasePlatformAdapter.send_voice
