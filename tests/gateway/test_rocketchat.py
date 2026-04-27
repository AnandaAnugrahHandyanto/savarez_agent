"""Tests for the Rocket.Chat platform adapter."""
import os
import time
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from gateway.config import Platform, PlatformConfig


# ---------------------------------------------------------------------------
# Platform & Config
# ---------------------------------------------------------------------------

class TestRocketchatConfigLoading:
    def test_apply_env_overrides_rocketchat(self, monkeypatch):
        monkeypatch.setenv("ROCKETCHAT_TOKEN", "rc-tok-abc123")
        monkeypatch.setenv("ROCKETCHAT_URL", "https://rc.example.com")
        monkeypatch.setenv("ROCKETCHAT_USER_ID", "uid_bot123")

        from gateway.config import GatewayConfig, _apply_env_overrides
        config = GatewayConfig()
        _apply_env_overrides(config)

        assert Platform.ROCKETCHAT in config.platforms
        pc = config.platforms[Platform.ROCKETCHAT]
        assert pc.enabled is True
        assert pc.token == "rc-tok-abc123"
        assert pc.extra.get("url") == "https://rc.example.com"
        assert pc.extra.get("user_id") == "uid_bot123"

    def test_rocketchat_not_loaded_without_token(self, monkeypatch):
        monkeypatch.delenv("ROCKETCHAT_TOKEN", raising=False)
        monkeypatch.delenv("ROCKETCHAT_URL", raising=False)
        monkeypatch.delenv("ROCKETCHAT_USER_ID", raising=False)

        from gateway.config import GatewayConfig, _apply_env_overrides
        config = GatewayConfig()
        _apply_env_overrides(config)

        assert Platform.ROCKETCHAT not in config.platforms

    def test_rocketchat_home_channel(self, monkeypatch):
        monkeypatch.setenv("ROCKETCHAT_TOKEN", "rc-tok-abc123")
        monkeypatch.setenv("ROCKETCHAT_URL", "https://rc.example.com")
        monkeypatch.setenv("ROCKETCHAT_USER_ID", "uid_bot123")
        monkeypatch.setenv("ROCKETCHAT_HOME_CHANNEL", "rid_GENERAL")
        monkeypatch.setenv("ROCKETCHAT_HOME_CHANNEL_NAME", "general")

        from gateway.config import GatewayConfig, _apply_env_overrides
        config = GatewayConfig()
        _apply_env_overrides(config)

        home = config.get_home_channel(Platform.ROCKETCHAT)
        assert home is not None
        assert home.chat_id == "rid_GENERAL"
        assert home.name == "general"

    def test_rocketchat_url_warning_without_url(self, monkeypatch):
        """ROCKETCHAT_TOKEN set but ROCKETCHAT_URL missing should still load."""
        monkeypatch.setenv("ROCKETCHAT_TOKEN", "rc-tok-abc123")
        monkeypatch.delenv("ROCKETCHAT_URL", raising=False)
        monkeypatch.setenv("ROCKETCHAT_USER_ID", "uid_bot123")

        from gateway.config import GatewayConfig, _apply_env_overrides
        config = GatewayConfig()
        _apply_env_overrides(config)

        assert Platform.ROCKETCHAT in config.platforms
        assert config.platforms[Platform.ROCKETCHAT].extra.get("url") == ""


# ---------------------------------------------------------------------------
# Adapter format / truncate
# ---------------------------------------------------------------------------

def _make_adapter():
    """Create a RocketchatAdapter with mocked config."""
    from gateway.platforms.rocketchat import RocketchatAdapter
    config = PlatformConfig(
        enabled=True,
        token="test-token",
        extra={"url": "https://rc.example.com", "user_id": "bot_user_id"},
    )
    adapter = RocketchatAdapter(config)
    return adapter


class TestRocketchatFormatMessage:
    def setup_method(self):
        self.adapter = _make_adapter()

    def test_image_markdown_to_url(self):
        """![alt](url) should be converted to just the URL."""
        result = self.adapter.format_message("![cat](https://img.example.com/cat.png)")
        assert result == "https://img.example.com/cat.png"

    def test_image_markdown_strips_alt_text(self):
        result = self.adapter.format_message("Here: ![my image](https://x.com/a.jpg) done")
        assert "![" not in result
        assert "https://x.com/a.jpg" in result

    def test_regular_markdown_preserved(self):
        content = "**bold** and *italic* and `code`"
        assert self.adapter.format_message(content) == content

    def test_regular_links_preserved(self):
        content = "[click](https://example.com)"
        assert self.adapter.format_message(content) == content

    def test_plain_text_unchanged(self):
        content = "Hello, world!"
        assert self.adapter.format_message(content) == content


class TestRocketchatTruncateMessage:
    def setup_method(self):
        self.adapter = _make_adapter()

    def test_short_message_single_chunk(self):
        msg = "Hello, world!"
        chunks = self.adapter.truncate_message(msg, 5000)
        assert len(chunks) == 1
        assert chunks[0] == msg

    def test_long_message_splits(self):
        msg = "a " * 3000  # 6000 chars
        chunks = self.adapter.truncate_message(msg, 5000)
        assert len(chunks) >= 2
        for chunk in chunks:
            assert len(chunk) <= 5000

    def test_exactly_at_limit(self):
        msg = "x" * 5000
        chunks = self.adapter.truncate_message(msg, 5000)
        assert len(chunks) == 1


# ---------------------------------------------------------------------------
# Send
# ---------------------------------------------------------------------------

class TestRocketchatSend:
    def setup_method(self):
        self.adapter = _make_adapter()
        self.adapter._session = MagicMock()

    @pytest.mark.asyncio
    async def test_send_calls_chat_postmessage(self):
        """send() should POST to /api/v1/chat.postMessage with roomId and text."""
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={
            "success": True, "message": {"_id": "msg123"}
        })
        mock_resp.text = AsyncMock(return_value="")
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        self.adapter._session.post = MagicMock(return_value=mock_resp)

        result = await self.adapter.send("rid_general", "Hello!")

        assert result.success is True
        assert result.message_id == "msg123"

        call_args = self.adapter._session.post.call_args
        assert "/api/v1/chat.postMessage" in call_args[0][0]
        payload = call_args[1]["json"]
        assert payload["roomId"] == "rid_general"
        assert payload["text"] == "Hello!"

    @pytest.mark.asyncio
    async def test_send_empty_content_succeeds(self):
        result = await self.adapter.send("rid_general", "")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_send_with_thread_reply(self):
        """When reply_mode is 'thread', reply_to should become tmid."""
        self.adapter._reply_mode = "thread"

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={
            "success": True, "message": {"_id": "msg456"}
        })
        mock_resp.text = AsyncMock(return_value="")
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        self.adapter._session.post = MagicMock(return_value=mock_resp)

        result = await self.adapter.send("rid_general", "Reply!", reply_to="root_msg")

        assert result.success is True
        payload = self.adapter._session.post.call_args[1]["json"]
        assert payload["tmid"] == "root_msg"

    @pytest.mark.asyncio
    async def test_send_without_thread_no_tmid(self):
        """When reply_mode is 'off', reply_to should NOT set tmid."""
        self.adapter._reply_mode = "off"

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={
            "success": True, "message": {"_id": "msg789"}
        })
        mock_resp.text = AsyncMock(return_value="")
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        self.adapter._session.post = MagicMock(return_value=mock_resp)

        result = await self.adapter.send("rid_general", "Reply!", reply_to="root_msg")

        assert result.success is True
        payload = self.adapter._session.post.call_args[1]["json"]
        assert "tmid" not in payload

    @pytest.mark.asyncio
    async def test_send_api_failure(self):
        mock_resp = AsyncMock()
        mock_resp.status = 500
        mock_resp.json = AsyncMock(return_value={})
        mock_resp.text = AsyncMock(return_value="Internal Server Error")
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        self.adapter._session.post = MagicMock(return_value=mock_resp)

        result = await self.adapter.send("rid_general", "Hello!")
        assert result.success is False

    @pytest.mark.asyncio
    async def test_send_success_false_payload(self):
        """Rocket.Chat returns 200 with success=False on some failures."""
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={"success": False, "error": "nope"})
        mock_resp.text = AsyncMock(return_value="")
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        self.adapter._session.post = MagicMock(return_value=mock_resp)

        result = await self.adapter.send("rid_general", "Hello!")
        assert result.success is False


# ---------------------------------------------------------------------------
# DDP message parsing
# ---------------------------------------------------------------------------

class TestRocketchatMessageParsing:
    def setup_method(self):
        self.adapter = _make_adapter()
        self.adapter._bot_user_id = "bot_user_id"
        self.adapter._bot_username = "hermes-bot"
        self.adapter.handle_message = AsyncMock()
        # Seed the room cache so _handle_message doesn't try to REST-lookup.
        self.adapter._room_type_cache = {
            "chan_456": "channel",
            "chan_dm": "dm",
        }

    @pytest.mark.asyncio
    async def test_parse_message(self):
        """A DDP message should produce a MessageEvent with stripped @mention."""
        post = {
            "_id": "msg_abc",
            "rid": "chan_456",
            "msg": "@hermes-bot Hello from RC!",
            "u": {"_id": "user_123", "username": "alice"},
            "mentions": [{"_id": "bot_user_id", "username": "hermes-bot"}],
        }
        await self.adapter._handle_message(post)
        assert self.adapter.handle_message.called
        msg = self.adapter.handle_message.call_args[0][0]
        assert "@hermes-bot" not in msg.text
        assert "Hello from RC!" in msg.text
        assert msg.message_id == "msg_abc"

    @pytest.mark.asyncio
    async def test_ignore_own_messages(self):
        """Messages authored by the bot should be ignored."""
        post = {
            "_id": "msg_self",
            "rid": "chan_456",
            "msg": "Bot echo",
            "u": {"_id": "bot_user_id", "username": "hermes-bot"},
        }
        await self.adapter._handle_message(post)
        assert not self.adapter.handle_message.called

    @pytest.mark.asyncio
    async def test_ignore_system_messages(self):
        """Messages with a ``t`` field (uj=user joined, ul=user left, ...) are system."""
        post = {
            "_id": "sys_msg",
            "rid": "chan_456",
            "msg": "",
            "u": {"_id": "user_123", "username": "alice"},
            "t": "uj",
        }
        await self.adapter._handle_message(post)
        assert not self.adapter.handle_message.called

    @pytest.mark.asyncio
    async def test_dm_channel_type(self):
        """A message in a DM room should carry chat_type='dm'."""
        post = {
            "_id": "dm_msg",
            "rid": "chan_dm",
            "msg": "DM message",
            "u": {"_id": "user_123", "username": "bob"},
        }
        await self.adapter._handle_message(post)
        assert self.adapter.handle_message.called
        msg = self.adapter.handle_message.call_args[0][0]
        assert msg.source.chat_type == "dm"

    @pytest.mark.asyncio
    async def test_thread_id_from_tmid(self):
        """A message with tmid should have thread_id set."""
        post = {
            "_id": "reply_msg",
            "rid": "chan_456",
            "msg": "@hermes-bot Thread reply",
            "u": {"_id": "user_123", "username": "alice"},
            "mentions": [{"_id": "bot_user_id", "username": "hermes-bot"}],
            "tmid": "parent_msg_id",
        }
        await self.adapter._handle_message(post)
        assert self.adapter.handle_message.called
        msg = self.adapter.handle_message.call_args[0][0]
        assert msg.source.thread_id == "parent_msg_id"

    @pytest.mark.asyncio
    async def test_room_without_rid_ignored(self):
        """Messages missing rid should be silently skipped."""
        post = {
            "_id": "no_rid",
            "msg": "orphan",
            "u": {"_id": "user_123", "username": "alice"},
        }
        await self.adapter._handle_message(post)
        assert not self.adapter.handle_message.called


# ---------------------------------------------------------------------------
# Mention behavior
# ---------------------------------------------------------------------------

class TestRocketchatMentionBehavior:
    def setup_method(self):
        self.adapter = _make_adapter()
        self.adapter._bot_user_id = "bot_user_id"
        self.adapter._bot_username = "hermes-bot"
        self.adapter.handle_message = AsyncMock()
        self.adapter._room_type_cache = {
            "chan_456": "channel",
            "chan_789": "channel",
        }

    def _post(self, text, room_id="chan_456", mentions=None):
        return {
            "_id": f"msg_{hash(text) & 0xFFFFFF}",
            "rid": room_id,
            "msg": text,
            "u": {"_id": "user_123", "username": "alice"},
            "mentions": mentions or [],
        }

    @pytest.mark.asyncio
    async def test_require_mention_default_skips_without_mention(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ROCKETCHAT_REQUIRE_MENTION", None)
            os.environ.pop("ROCKETCHAT_FREE_RESPONSE_CHANNELS", None)
            await self.adapter._handle_message(self._post("hello"))
            assert not self.adapter.handle_message.called

    @pytest.mark.asyncio
    async def test_require_mention_false_responds_to_all(self):
        with patch.dict(os.environ, {"ROCKETCHAT_REQUIRE_MENTION": "false"}):
            await self.adapter._handle_message(self._post("hello"))
            assert self.adapter.handle_message.called

    @pytest.mark.asyncio
    async def test_free_response_channel_bypasses_mention(self):
        with patch.dict(os.environ, {"ROCKETCHAT_FREE_RESPONSE_CHANNELS": "chan_456,chan_789"}):
            os.environ.pop("ROCKETCHAT_REQUIRE_MENTION", None)
            await self.adapter._handle_message(self._post("hello", room_id="chan_456"))
            assert self.adapter.handle_message.called

    @pytest.mark.asyncio
    async def test_non_free_channel_still_requires_mention(self):
        with patch.dict(os.environ, {"ROCKETCHAT_FREE_RESPONSE_CHANNELS": "chan_789"}):
            os.environ.pop("ROCKETCHAT_REQUIRE_MENTION", None)
            await self.adapter._handle_message(self._post("hello", room_id="chan_456"))
            assert not self.adapter.handle_message.called

    @pytest.mark.asyncio
    async def test_dm_always_responds(self):
        self.adapter._room_type_cache["chan_dm"] = "dm"
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ROCKETCHAT_REQUIRE_MENTION", None)
            await self.adapter._handle_message(self._post("hello", room_id="chan_dm"))
            assert self.adapter.handle_message.called

    @pytest.mark.asyncio
    async def test_mention_via_mentions_array(self):
        """The mentions[] array is the authoritative source — should match even without @text."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ROCKETCHAT_REQUIRE_MENTION", None)
            post = self._post(
                "hey, what's 2+2?",
                mentions=[{"_id": "bot_user_id", "username": "hermes-bot"}],
            )
            await self.adapter._handle_message(post)
            assert self.adapter.handle_message.called

    @pytest.mark.asyncio
    async def test_mention_via_text_fallback(self):
        """If mentions[] is empty (edit, unresolved), text-scan @username."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ROCKETCHAT_REQUIRE_MENTION", None)
            await self.adapter._handle_message(
                self._post("@hermes-bot help me", mentions=[])
            )
            assert self.adapter.handle_message.called
            msg = self.adapter.handle_message.call_args[0][0]
            assert "@hermes-bot" not in msg.text


# ---------------------------------------------------------------------------
# Dedup cache
# ---------------------------------------------------------------------------

class TestRocketchatDedup:
    def setup_method(self):
        self.adapter = _make_adapter()
        self.adapter._bot_user_id = "bot_user_id"
        self.adapter._bot_username = "hermes-bot"
        self.adapter.handle_message = AsyncMock()
        self.adapter._room_type_cache = {"chan_456": "channel"}

    @pytest.mark.asyncio
    async def test_duplicate_message_ignored(self):
        post = {
            "_id": "msg_dup",
            "rid": "chan_456",
            "msg": "@hermes-bot hi",
            "u": {"_id": "user_123", "username": "alice"},
            "mentions": [{"_id": "bot_user_id", "username": "hermes-bot"}],
        }
        await self.adapter._handle_message(post)
        assert self.adapter.handle_message.call_count == 1
        await self.adapter._handle_message(post)
        assert self.adapter.handle_message.call_count == 1  # deduped

    @pytest.mark.asyncio
    async def test_different_ids_both_processed(self):
        for i, mid in enumerate(["msg_a", "msg_b"]):
            post = {
                "_id": mid,
                "rid": "chan_456",
                "msg": f"@hermes-bot message {i}",
                "u": {"_id": "user_123", "username": "alice"},
                "mentions": [{"_id": "bot_user_id", "username": "hermes-bot"}],
            }
            await self.adapter._handle_message(post)
        assert self.adapter.handle_message.call_count == 2

    def test_prune_seen_clears_expired(self):
        now = time.time()
        dedup = self.adapter._dedup
        for i in range(dedup._max_size + 10):
            dedup._seen[f"old_{i}"] = now - 600
        dedup._seen["fresh"] = now
        dedup.is_duplicate("trigger_prune")
        assert "fresh" in dedup._seen
        assert len(dedup._seen) < dedup._max_size + 10


# ---------------------------------------------------------------------------
# Requirements check
# ---------------------------------------------------------------------------

class TestRocketchatRequirements:
    def test_check_requirements_with_all_vars(self, monkeypatch):
        monkeypatch.setenv("ROCKETCHAT_TOKEN", "test-token")
        monkeypatch.setenv("ROCKETCHAT_URL", "https://rc.example.com")
        monkeypatch.setenv("ROCKETCHAT_USER_ID", "bot_user_id")
        from gateway.platforms.rocketchat import check_rocketchat_requirements
        assert check_rocketchat_requirements() is True

    def test_check_requirements_without_token(self, monkeypatch):
        monkeypatch.delenv("ROCKETCHAT_TOKEN", raising=False)
        monkeypatch.delenv("ROCKETCHAT_URL", raising=False)
        monkeypatch.delenv("ROCKETCHAT_USER_ID", raising=False)
        from gateway.platforms.rocketchat import check_rocketchat_requirements
        assert check_rocketchat_requirements() is False

    def test_check_requirements_without_url(self, monkeypatch):
        monkeypatch.setenv("ROCKETCHAT_TOKEN", "test-token")
        monkeypatch.delenv("ROCKETCHAT_URL", raising=False)
        monkeypatch.setenv("ROCKETCHAT_USER_ID", "bot_user_id")
        from gateway.platforms.rocketchat import check_rocketchat_requirements
        assert check_rocketchat_requirements() is False

    def test_check_requirements_without_user_id(self, monkeypatch):
        monkeypatch.setenv("ROCKETCHAT_TOKEN", "test-token")
        monkeypatch.setenv("ROCKETCHAT_URL", "https://rc.example.com")
        monkeypatch.delenv("ROCKETCHAT_USER_ID", raising=False)
        from gateway.platforms.rocketchat import check_rocketchat_requirements
        assert check_rocketchat_requirements() is False


# ---------------------------------------------------------------------------
# Media type propagation (MIME types, not bare strings)
# ---------------------------------------------------------------------------

class TestRocketchatMediaTypes:
    """Verify that media_types contains actual MIME types (e.g. 'image/png')
    rather than bare category strings ('image'), so downstream
    ``mtype.startswith("image/")`` checks in run.py work correctly."""

    def setup_method(self):
        self.adapter = _make_adapter()
        self.adapter._bot_user_id = "bot_user_id"
        self.adapter._bot_username = "hermes-bot"
        self.adapter.handle_message = AsyncMock()
        self.adapter._room_type_cache = {"chan_456": "channel"}

    def _file_post(self, file_obj, attachments=None):
        return {
            "_id": f"msg_media_{file_obj.get('_id')}",
            "rid": "chan_456",
            "msg": "@hermes-bot file attached",
            "u": {"_id": "user_123", "username": "alice"},
            "mentions": [{"_id": "bot_user_id", "username": "hermes-bot"}],
            "file": file_obj,
            "attachments": attachments or [],
        }

    @pytest.mark.asyncio
    async def test_image_media_type_is_full_mime(self):
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.content_type = "image/png"
        mock_resp.read = AsyncMock(return_value=b"\x89PNG fake")
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)
        self.adapter._session = MagicMock()
        self.adapter._session.get = MagicMock(return_value=mock_resp)

        with patch("gateway.platforms.base.cache_image_from_bytes", return_value="/tmp/photo.png"):
            await self.adapter._handle_message(
                self._file_post({"_id": "f1", "name": "photo.png", "type": "image/png"})
            )

        msg = self.adapter.handle_message.call_args[0][0]
        assert msg.media_types == ["image/png"]
        assert msg.media_types[0].startswith("image/")

    @pytest.mark.asyncio
    async def test_audio_media_type_is_full_mime(self):
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.content_type = "audio/ogg"
        mock_resp.read = AsyncMock(return_value=b"OGG fake")
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)
        self.adapter._session = MagicMock()
        self.adapter._session.get = MagicMock(return_value=mock_resp)

        with patch("gateway.platforms.base.cache_audio_from_bytes", return_value="/tmp/voice.ogg"), \
             patch("gateway.platforms.base.cache_image_from_bytes"), \
             patch("gateway.platforms.base.cache_document_from_bytes"):
            await self.adapter._handle_message(
                self._file_post({"_id": "f2", "name": "voice.ogg", "type": "audio/ogg"})
            )

        msg = self.adapter.handle_message.call_args[0][0]
        assert msg.media_types == ["audio/ogg"]

    @pytest.mark.asyncio
    async def test_document_media_type_is_full_mime(self):
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.content_type = "application/pdf"
        mock_resp.read = AsyncMock(return_value=b"PDF fake")
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)
        self.adapter._session = MagicMock()
        self.adapter._session.get = MagicMock(return_value=mock_resp)

        with patch("gateway.platforms.base.cache_document_from_bytes", return_value="/tmp/report.pdf"), \
             patch("gateway.platforms.base.cache_image_from_bytes"):
            await self.adapter._handle_message(
                self._file_post({"_id": "f3", "name": "report.pdf", "type": "application/pdf"})
            )

        msg = self.adapter.handle_message.call_args[0][0]
        assert msg.media_types == ["application/pdf"]
        assert not msg.media_types[0].startswith("image/")


# ---------------------------------------------------------------------------
# DDP framing: ping/pong, ready, stream-room-messages dispatch
# ---------------------------------------------------------------------------

class TestRocketchatDDPFraming:
    def setup_method(self):
        self.adapter = _make_adapter()
        self.adapter._bot_user_id = "bot_user_id"
        self.adapter._bot_username = "hermes-bot"
        self.adapter._room_type_cache = {"chan_456": "channel"}
        self.adapter.handle_message = AsyncMock()

        # Fake websocket: records frames sent via _ddp_send.
        self.sent = []
        ws = MagicMock()
        ws.closed = False

        async def _send_json(payload):
            self.sent.append(payload)
        ws.send_json = _send_json
        self.adapter._ws = ws

    @pytest.mark.asyncio
    async def test_ping_replies_with_pong(self):
        await self.adapter._handle_ddp_frame({"msg": "ping"})
        assert self.sent == [{"msg": "pong"}]

    @pytest.mark.asyncio
    async def test_ping_with_id_echoes_id(self):
        await self.adapter._handle_ddp_frame({"msg": "ping", "id": "pingid-1"})
        assert self.sent == [{"msg": "pong", "id": "pingid-1"}]

    @pytest.mark.asyncio
    async def test_ready_marks_sub_ready(self):
        self.adapter._ddp_subs["sub-1"] = False
        await self.adapter._handle_ddp_frame({"msg": "ready", "subs": ["sub-1"]})
        assert self.adapter._ddp_subs["sub-1"] is True

    @pytest.mark.asyncio
    async def test_changed_stream_room_messages_dispatches(self):
        frame = {
            "msg": "changed",
            "collection": "stream-room-messages",
            "fields": {
                "args": [{
                    "_id": "rc_msg_1",
                    "rid": "chan_456",
                    "msg": "@hermes-bot hi",
                    "u": {"_id": "user_123", "username": "alice"},
                    "mentions": [{"_id": "bot_user_id", "username": "hermes-bot"}],
                }],
            },
        }
        await self.adapter._handle_ddp_frame(frame)
        assert self.adapter.handle_message.called

    @pytest.mark.asyncio
    async def test_changed_other_collection_ignored(self):
        frame = {
            "msg": "changed",
            "collection": "meteor.loginServiceConfiguration",
            "fields": {"args": [{}]},
        }
        await self.adapter._handle_ddp_frame(frame)
        assert not self.adapter.handle_message.called
