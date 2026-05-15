"""Tests for the Canon platform adapter plugin."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from tests.gateway._plugin_adapter_loader import load_plugin_adapter

_canon = load_plugin_adapter("canon")

CanonAdapter = _canon.CanonAdapter
CanonHttpClient = _canon.CanonHttpClient
CanonStreamFrame = _canon.CanonStreamFrame
DEFAULT_BASE_URL = _canon.DEFAULT_BASE_URL
DEFAULT_STREAM_URL = _canon.DEFAULT_STREAM_URL
TURN_COMPLETE_METADATA = _canon.TURN_COMPLETE_METADATA
_env_enablement = _canon._env_enablement
_parse_sse_frame = _canon._parse_sse_frame
_standalone_send = _canon._standalone_send
check_requirements = _canon.check_requirements
register = _canon.register
validate_config = _canon.validate_config


def _config(**kwargs):
    from gateway.config import PlatformConfig

    return PlatformConfig(enabled=True, **kwargs)


class TestCanonConfig:
    def test_init_from_config_extra(self, monkeypatch):
        monkeypatch.delenv("CANON_API_KEY", raising=False)
        cfg = _config(
            extra={
                "api_key": "config-key",
                "base_url": "https://api.example.test",
                "stream_url": "https://stream.example.test",
                "history_limit": "25",
            }
        )

        adapter = CanonAdapter(cfg)

        assert adapter.api_key == "config-key"
        assert adapter.base_url == "https://api.example.test"
        assert adapter.stream_url == "https://stream.example.test"
        assert adapter.history_limit == 25

    def test_env_overrides_config(self, monkeypatch):
        monkeypatch.setenv("CANON_API_KEY", "env-key")
        monkeypatch.setenv("CANON_BASE_URL", "https://api.env.test")

        adapter = CanonAdapter(
            _config(api_key="config-key", extra={"base_url": "https://api.config.test"})
        )

        assert adapter.api_key == "env-key"
        assert adapter.base_url == "https://api.env.test"

    def test_validate_config_accepts_env_or_config(self, monkeypatch):
        monkeypatch.delenv("CANON_API_KEY", raising=False)
        assert not validate_config(_config())
        assert validate_config(_config(api_key="config-key"))

        monkeypatch.setenv("CANON_API_KEY", "env-key")
        assert validate_config(_config())

    def test_env_enablement_seeds_extra_and_home_channel(self, monkeypatch):
        monkeypatch.setenv("CANON_API_KEY", "env-key")
        monkeypatch.setenv("CANON_BASE_URL", "https://api.env.test")
        monkeypatch.setenv("CANON_STREAM_URL", "https://stream.env.test")
        monkeypatch.setenv("CANON_HOME_CHANNEL", "convo-home")
        monkeypatch.setenv("CANON_HISTORY_LIMIT", "75")

        seed = _env_enablement()

        assert seed["api_key"] == "env-key"
        assert seed["base_url"] == "https://api.env.test"
        assert seed["stream_url"] == "https://stream.env.test"
        assert seed["history_limit"] == "75"
        assert seed["home_channel"]["chat_id"] == "convo-home"

    def test_requirements_are_core_dependency_only(self):
        assert check_requirements() is True


class TestCanonHttpClient:
    @pytest.mark.asyncio
    async def test_download_media_blocks_unsafe_url(self, monkeypatch):
        client = CanonHttpClient("key")
        client._client.get = AsyncMock()
        monkeypatch.setattr("tools.url_safety.is_safe_url", lambda _url: False)

        try:
            with pytest.raises(ValueError, match="SSRF"):
                await client.download_media("http://127.0.0.1/private")

            client._client.get.assert_not_called()
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_download_media_uses_redirect_guard(self, monkeypatch):
        client = CanonHttpClient("key")
        monkeypatch.setattr(
            "tools.url_safety.is_safe_url",
            lambda url: url == "https://media.example/voice.m4a",
        )
        redirect_response = SimpleNamespace(
            is_redirect=True,
            next_request=SimpleNamespace(
                url="http://169.254.169.254/latest/meta-data"
            ),
        )

        try:
            hooks = client._client.event_hooks["response"]
            assert hooks
            with pytest.raises(ValueError, match="Blocked redirect"):
                await hooks[0](redirect_response)
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_download_media_returns_bytes_for_safe_url(self, monkeypatch):
        response = SimpleNamespace(
            status_code=200,
            content=b"audio-bytes",
            text="",
            headers={"content-type": "audio/mp4"},
        )
        client = CanonHttpClient("key")
        client._client.get = AsyncMock(return_value=response)
        monkeypatch.setattr("tools.url_safety.is_safe_url", lambda _url: True)

        try:
            data, content_type = await client.download_media(
                "https://media.example/voice.m4a"
            )

            assert data == b"audio-bytes"
            assert content_type == "audio/mp4"
            client._client.get.assert_awaited_once_with(
                "https://media.example/voice.m4a",
                headers={"User-Agent": "HermesAgent/CanonPlatform"},
                follow_redirects=True,
            )
        finally:
            await client.close()


class TestCanonInbound:
    @pytest.mark.asyncio
    async def test_message_created_normalizes_to_message_event(self):
        from gateway.platforms.base import MessageType

        adapter = CanonAdapter(_config(extra={"api_key": "key"}))
        adapter._agent_id = "agent-1"
        adapter._conversation_cache["convo-1"] = {
            "id": "convo-1",
            "type": "group",
            "name": "Research",
        }
        adapter.handle_message = AsyncMock()

        await adapter._handle_message_payload({
            "conversationId": "convo-1",
            "message": {
                "id": "msg-1",
                "senderId": "human-1",
                "senderName": "Ada",
                "text": "/status please",
                "contentType": "text",
                "replyTo": "msg-parent",
            },
        })

        adapter.handle_message.assert_awaited_once()
        event = adapter.handle_message.await_args.args[0]
        assert event.text == "/status please"
        assert event.message_type == MessageType.COMMAND
        assert event.message_id == "msg-1"
        assert event.reply_to_message_id == "msg-parent"
        assert event.source.platform.value == "canon"
        assert event.source.chat_id == "convo-1"
        assert event.source.chat_type == "group"
        assert event.source.chat_name == "Research"
        assert event.source.user_id == "human-1"
        assert event.source.user_name == "Ada"

    @pytest.mark.asyncio
    async def test_ignores_self_messages_and_duplicates(self):
        adapter = CanonAdapter(_config(extra={"api_key": "key"}))
        adapter._agent_id = "agent-1"
        adapter.handle_message = AsyncMock()

        payload = {
            "conversationId": "convo-1",
            "message": {
                "id": "msg-1",
                "senderId": "agent-1",
                "text": "own echo",
                "contentType": "text",
            },
        }
        await adapter._handle_message_payload(payload)
        adapter.handle_message.assert_not_awaited()

        payload["message"]["senderId"] = "human-1"
        await adapter._handle_message_payload(payload)
        await adapter._handle_message_payload(payload)
        adapter.handle_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_attachment_only_message_gets_text_placeholder(self):
        adapter = CanonAdapter(_config(extra={"api_key": "key"}))
        adapter.handle_message = AsyncMock()

        await adapter._handle_message_payload({
            "conversationId": "convo-1",
            "message": {
                "id": "msg-2",
                "senderId": "human-1",
                "contentType": "image",
                "attachments": [{"kind": "image", "fileName": "plot.png"}],
            },
        })

        event = adapter.handle_message.await_args.args[0]
        assert event.text == "[image attachment: plot.png]"
        assert event.source.chat_type == "dm"

    @pytest.mark.asyncio
    async def test_audio_and_video_attachments_are_materialized(self, monkeypatch):
        from gateway.platforms.base import MessageType

        class FakeClient:
            async def download_media(self, url):
                if url.endswith("voice.m4a"):
                    return b"audio-bytes", "audio/mp4"
                return b"video-bytes", "video/mp4"

        monkeypatch.setattr(
            _canon,
            "cache_audio_from_bytes",
            lambda data, ext=".ogg": f"/tmp/canon-audio{ext}",
        )
        monkeypatch.setattr(
            _canon,
            "cache_video_from_bytes",
            lambda data, ext=".mp4": f"/tmp/canon-video{ext}",
        )

        adapter = CanonAdapter(_config(extra={"api_key": "key"}))
        adapter._client = FakeClient()
        adapter.handle_message = AsyncMock()

        await adapter._handle_message_payload({
            "conversationId": "convo-1",
            "message": {
                "id": "msg-media",
                "senderId": "human-1",
                "text": "review these",
                "contentType": "file",
                "attachments": [
                    {"kind": "audio", "url": "https://media.example/voice.m4a"},
                    {"kind": "file", "url": "https://media.example/demo.mp4"},
                ],
            },
        })

        event = adapter.handle_message.await_args.args[0]
        assert event.message_type == MessageType.VOICE
        assert event.media_urls == ["/tmp/canon-audio.m4a", "/tmp/canon-video.mp4"]
        assert event.media_types == ["audio/mp4", "video/mp4"]


class TestCanonOutbound:
    class FakeClient:
        def __init__(self):
            self.sent = []
            self.typing = []
            self.uploads = []
            self.closed = False

        async def send_message(
            self, conversation_id, text, *, reply_to=None, metadata=None, options=None
        ):
            self.sent.append({
                "conversation_id": conversation_id,
                "text": text,
                "reply_to": reply_to,
                "metadata": metadata,
                "options": options,
            })
            return {"messageId": "msg-out"}

        async def set_typing(self, conversation_id, typing, status=None):
            self.typing.append((conversation_id, typing, status))

        async def upload_media(
            self, conversation_id, data, mime_type, *, file_name=None
        ):
            self.uploads.append((conversation_id, data, mime_type, file_name))
            kind = "audio" if mime_type.startswith("audio/") else "file"
            return {
                "url": f"https://media.example/{file_name}",
                "attachment": {
                    "kind": kind,
                    "url": f"https://media.example/{file_name}",
                    "mimeType": mime_type,
                    "fileName": file_name,
                },
            }

        async def close(self):
            self.closed = True

    @pytest.mark.asyncio
    async def test_send_posts_turn_complete_metadata(self):
        adapter = CanonAdapter(_config(extra={"api_key": "key"}))
        fake = self.FakeClient()
        adapter._client = fake

        result = await adapter.send(
            "convo-1",
            "hello",
            reply_to="msg-parent",
            metadata={
                "canon_metadata": {"source": "test"},
                "canon_options": {"mentions": ["u1"]},
            },
        )

        assert result.success is True
        assert result.message_id == "msg-out"
        assert fake.sent == [
            {
                "conversation_id": "convo-1",
                "text": "hello",
                "reply_to": "msg-parent",
                "metadata": {"source": "test", **TURN_COMPLETE_METADATA},
                "options": {"mentions": ["u1"]},
            }
        ]

    @pytest.mark.asyncio
    async def test_typing_is_best_effort(self):
        adapter = CanonAdapter(_config(extra={"api_key": "key"}))
        fake = self.FakeClient()
        adapter._client = fake

        await adapter.send_typing("convo-1")
        await adapter.stop_typing("convo-1")

        assert fake.typing == [
            ("convo-1", True, "thinking"),
            ("convo-1", False, None),
        ]

    @pytest.mark.asyncio
    async def test_send_voice_uploads_audio_attachment(self, tmp_path):
        adapter = CanonAdapter(_config(extra={"api_key": "key"}))
        fake = self.FakeClient()
        adapter._client = fake
        audio_path = tmp_path / "reply.mp3"
        audio_path.write_bytes(b"audio-bytes")

        result = await adapter.send_voice(
            "convo-1", str(audio_path), caption="voice reply"
        )

        assert result.success is True
        assert fake.uploads[0][2] == "audio/mpeg"
        sent = fake.sent[0]
        assert sent["text"] == "voice reply"
        assert sent["options"]["contentType"] == "audio"
        assert sent["options"]["attachments"][0]["kind"] == "audio"
        assert sent["metadata"] == TURN_COMPLETE_METADATA

    @pytest.mark.asyncio
    async def test_send_video_uploads_file_attachment_with_video_mime(self, tmp_path):
        adapter = CanonAdapter(_config(extra={"api_key": "key"}))
        fake = self.FakeClient()
        adapter._client = fake
        video_path = tmp_path / "demo.mp4"
        video_path.write_bytes(b"video-bytes")

        result = await adapter.send_video("convo-1", str(video_path))

        assert result.success is True
        assert fake.uploads[0][2] == "video/mp4"
        sent = fake.sent[0]
        assert sent["options"]["contentType"] == "file"
        assert sent["options"]["attachments"][0]["mimeType"] == "video/mp4"


class TestCanonLifecycle:
    class FakeClient:
        def __init__(self):
            self.closed = False

        async def get_me(self):
            return {"agentId": "agent-1", "displayName": "Hermes"}

        async def get_conversations(self):
            return [{"id": "convo-1", "type": "direct", "name": "Ada"}]

        async def close(self):
            self.closed = True

    @pytest.mark.asyncio
    async def test_connect_hydrates_identity_and_conversations(self):
        adapter = CanonAdapter(_config(extra={"api_key": "key"}))
        fake = self.FakeClient()
        block = asyncio.Event()

        async def fake_stream_loop():
            await block.wait()

        adapter._make_client = lambda: fake
        adapter._stream_loop = fake_stream_loop

        assert await adapter.connect() is True
        assert adapter.is_connected is True
        assert adapter._agent_id == "agent-1"
        assert adapter._conversation_cache["convo-1"]["name"] == "Ada"

        block.set()
        await adapter.disconnect()
        assert fake.closed is True
        assert adapter.is_connected is False

    @pytest.mark.asyncio
    async def test_stream_frame_dispatches_message_created(self):
        adapter = CanonAdapter(_config(extra={"api_key": "key"}))
        adapter._handle_message_payload = AsyncMock()

        frame = CanonStreamFrame(
            event="message.created",
            data={"conversationId": "convo-1", "message": {"id": "m1"}},
            event_id="evt-1",
        )
        await adapter._handle_stream_frame(frame)

        adapter._handle_message_payload.assert_awaited_once_with(frame.data)


class TestCanonSSE:
    def test_parse_sse_frame(self):
        frame = _parse_sse_frame(
            'id: evt-1\nevent: message.created\ndata: {"conversationId":"convo-1"}'
        )

        assert frame.event == "message.created"
        assert frame.event_id == "evt-1"
        assert frame.data == {"conversationId": "convo-1"}

    def test_parse_sse_frame_ignores_comments(self):
        frame = _parse_sse_frame(": keepalive\nevent: heartbeat\ndata: ok")

        assert frame.event == "heartbeat"
        assert frame.data == "ok"


class TestCanonStandalone:
    class FakeClient:
        instances = []

        def __init__(
            self, api_key, *, base_url=DEFAULT_BASE_URL, stream_url=DEFAULT_STREAM_URL
        ):
            self.api_key = api_key
            self.base_url = base_url
            self.stream_url = stream_url
            self.sent = []
            self.closed = False
            self.instances.append(self)

        async def send_message(
            self, conversation_id, text, *, reply_to=None, metadata=None, options=None
        ):
            self.sent.append((conversation_id, text, reply_to, metadata, options))
            return {"messageId": "standalone-1"}

        async def close(self):
            self.closed = True

    @pytest.mark.asyncio
    async def test_standalone_send_uses_home_channel_and_closes(self, monkeypatch):
        self.FakeClient.instances = []
        monkeypatch.setattr(_canon, "CanonHttpClient", self.FakeClient)
        monkeypatch.setenv("CANON_API_KEY", "env-key")
        monkeypatch.setenv("CANON_HOME_CHANNEL", "convo-home")

        result = await _standalone_send(_config(), "", "hello cron")

        client = self.FakeClient.instances[0]
        assert result == {"success": True, "message_id": "standalone-1"}
        assert client.api_key == "env-key"
        assert client.sent == [
            ("convo-home", "hello cron", None, TURN_COMPLETE_METADATA, None)
        ]
        assert client.closed is True

    @pytest.mark.asyncio
    async def test_standalone_send_errors_without_api_key(self, monkeypatch):
        monkeypatch.delenv("CANON_API_KEY", raising=False)

        result = await _standalone_send(_config(), "convo-1", "hello")

        assert "error" in result
        assert "CANON_API_KEY" in result["error"]


class TestCanonRegister:
    def test_register_metadata(self):
        recorded = {}

        class Context:
            def register_platform(self, **kwargs):
                recorded.update(kwargs)

        register(Context())

        assert recorded["name"] == "canon"
        assert recorded["label"] == "Canon"
        assert recorded["required_env"] == ["CANON_API_KEY"]
        assert recorded["cron_deliver_env_var"] == "CANON_HOME_CHANNEL"
        assert recorded["standalone_sender_fn"] is _standalone_send
        assert recorded["allowed_users_env"] == "CANON_ALLOWED_USERS"
        assert recorded["allow_all_env"] == "CANON_ALLOW_ALL_USERS"
        assert recorded["max_message_length"] == 8000
