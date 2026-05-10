"""Tests for LINE platform adapter media handling."""

from __future__ import annotations

import json
import time
from unittest.mock import AsyncMock

import pytest

from tests.gateway._plugin_adapter_loader import load_plugin_adapter

_line_mod = load_plugin_adapter("line")
LineAdapter = _line_mod.LineAdapter


class _FakeLineContentResponse:
    def __init__(self, *, status=200, body=b"", content_type="image/png", text=""):
        self.status = status
        self._body = body
        self._text = text
        self.headers = {"Content-Type": content_type, "Content-Length": str(len(body))}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def read(self):
        return self._body

    async def text(self):
        return self._text


class _FakeLineSession:
    def __init__(self, response):
        self.response = response
        self.get_calls = []

    def get(self, url, **kwargs):
        self.get_calls.append((url, kwargs))
        return self.response


class _FakeLineApiResponse:
    def __init__(self, *, status=200, text='{}'):
        self.status = status
        self._text = text

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def text(self):
        return self._text


class _FakeLinePostSession:
    def __init__(self, response):
        self.response = response
        self.post_calls = []

    def post(self, url, **kwargs):
        self.post_calls.append((url, kwargs))
        return self.response


@pytest.fixture
def line_adapter(monkeypatch, tmp_path):
    from gateway.config import PlatformConfig

    monkeypatch.delenv("LINE_ALLOWED_USERS", raising=False)
    monkeypatch.delenv("LINE_ALLOWED_CHATS", raising=False)
    monkeypatch.delenv("LINE_ALLOW_ALL_USERS", raising=False)
    monkeypatch.delenv("LINE_MEDIA_MAX_MB", raising=False)
    monkeypatch.delenv("LINE_MEDIA_MAX_BYTES", raising=False)
    monkeypatch.delenv("LINE_PENDING_APPROVALS_PATH", raising=False)
    monkeypatch.delenv("LINE_REQUIRE_MENTION_IN_GROUPS", raising=False)
    monkeypatch.delenv("LINE_RESPOND_IN_GROUPS_WHEN_RELEVANT", raising=False)
    monkeypatch.delenv("LINE_MENTION_NAMES", raising=False)
    monkeypatch.delenv("LINE_MENTION_PATTERNS", raising=False)
    monkeypatch.delenv("LINE_BOT_USER_ID", raising=False)
    monkeypatch.delenv("LINE_RECENT_CONTEXT_DB_PATH", raising=False)
    monkeypatch.delenv("LINE_RECENT_CONTEXT_ENABLED", raising=False)
    monkeypatch.delenv("LINE_RECENT_CONTEXT_OPERATOR_USERS", raising=False)

    adapter = LineAdapter(
        PlatformConfig(
            enabled=True,
            extra={
                "channel_secret": "unit-test-secret",
                "channel_access_token": "unit-test-token",
                "allowed_users": ["Uparent"],
                "allow_all_users": False,
                "media_max_mb": 1,
                "recent_context_db_path": str(tmp_path / "line_recent_context.sqlite"),
                "recent_context_ttl_seconds": 600,
                "recent_context_limit": 10,
                "recent_context_operator_users": ["Uparent"],
                "mention_names": ["Helper", "ผู้ช่วย"],
            },
        )
    )
    adapter.handle_message = AsyncMock()
    return adapter


def test_adapter_allows_dm_user_even_when_group_chat_allowlist_exists(line_adapter):
    line_adapter.allowed_users = {"Uparent"}
    line_adapter.allowed_chats = {"Cfamilygroup"}
    line_adapter.allow_all_users = False

    source = line_adapter._source_from_line({"type": "user", "userId": "Uparent"})

    assert source is not None
    assert source.chat_type == "dm"
    assert line_adapter._adapter_allows(source) is True


def test_adapter_group_allowlist_still_blocks_unlisted_group(line_adapter):
    line_adapter.allowed_users = {"Uparent"}
    line_adapter.allowed_chats = {"Cfamilygroup"}
    line_adapter.allow_all_users = False

    source = line_adapter._source_from_line({"type": "group", "groupId": "Cothergroup", "userId": "Ufamily"})

    assert source is not None
    assert source.chat_type == "group"
    assert line_adapter._adapter_allows(source) is False


def test_adapter_group_allowlist_authorizes_family_group_member(line_adapter):
    line_adapter.allowed_users = {"Uparent"}
    line_adapter.allowed_chats = {"Cfamilygroup"}
    line_adapter.allow_all_users = False

    source = line_adapter._source_from_line({"type": "group", "groupId": "Cfamilygroup", "userId": "Ufamily"})

    assert source is not None
    assert source.chat_type == "group"
    assert line_adapter._adapter_allows(source) is True

def _care_flex_buttons(message):
    buttons = []

    def walk(node):
        if isinstance(node, dict):
            if node.get("type") == "button" and isinstance(node.get("action"), dict):
                buttons.append(node)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    if message["type"] == "flex":
        walk(message["contents"])
    return buttons


def _flex_text_values(node):
    values = []
    if isinstance(node, dict):
        if node.get("type") == "text" and isinstance(node.get("text"), str):
            values.append(node["text"])
        for value in node.values():
            values.extend(_flex_text_values(value))
    elif isinstance(node, list):
        for item in node:
            values.extend(_flex_text_values(item))
    return values


def _actions_from_care_message(message):
    if message["type"] == "template":
        return message["template"]["actions"]
    if message["type"] == "flex":
        return [button["action"] for button in _care_flex_buttons(message)]
    raise AssertionError(f"unexpected LINE message type: {message['type']}")


def _flex_actions(node):
    actions = []
    if isinstance(node, dict):
        action = node.get("action")
        if isinstance(action, dict):
            actions.append(action)
        for value in node.values():
            actions.extend(_flex_actions(value))
    elif isinstance(node, list):
        for item in node:
            actions.extend(_flex_actions(item))
    return actions


@pytest.mark.asyncio
async def test_send_exec_approval_uses_line_postback_quick_replies(line_adapter):
    from gateway.platforms.base import SendResult

    line_adapter._push_message_objects = AsyncMock(return_value=SendResult(success=True, message_id="approval-msg"))

    result = await line_adapter.send_exec_approval(
        chat_id="Uparent",
        command="rm -rf /tmp/hermes-test",
        session_key="line:Uparent",
        description="dangerous deletion",
    )

    assert result.success is True
    line_adapter._push_message_objects.assert_awaited_once()
    chat_id, messages = line_adapter._push_message_objects.await_args.args
    assert chat_id == "Uparent"
    message = messages[0]
    assert message["type"] == "text"
    assert "rm -rf /tmp/hermes-test" in message["text"]
    actions = [item["action"] for item in message["quickReply"]["items"]]
    assert [action["label"] for action in actions] == ["Approve once", "This session", "Always", "Deny"]
    assert all(action["type"] == "postback" for action in actions)
    assert {line_adapter._parse_exec_approval_postback_data(action["data"])["choice"] for action in actions} == {
        "once",
        "session",
        "always",
        "deny",
    }
    assert len(line_adapter._exec_approvals) == 1


@pytest.mark.asyncio
async def test_exec_approval_postback_resolves_gateway_queue(line_adapter, monkeypatch):
    from gateway.platforms.base import SendResult

    approval_id = "a_unit_test"
    line_adapter._exec_approvals[approval_id] = {
        "session_key": "line:Uparent",
        "command": "rm -rf /tmp/hermes-test",
        "created_at": time.time(),
    }
    calls = []

    def fake_resolve(session_key, choice, resolve_all=False):
        calls.append((session_key, choice, resolve_all))
        return 1

    monkeypatch.setattr("tools.approval.resolve_gateway_approval", fake_resolve)
    line_adapter._reply_with_token = AsyncMock(return_value=SendResult(success=True))
    source = line_adapter._source_from_line({"type": "user", "userId": "Uparent"})

    await line_adapter._handle_postback_event(
        {
            "type": "postback",
            "replyToken": "reply-token-approval",
            "postback": {"data": line_adapter._exec_approval_postback_data(approval_id, "session")},
        },
        source,
    )

    assert calls == [("line:Uparent", "session", False)]
    assert approval_id not in line_adapter._exec_approvals
    line_adapter._reply_with_token.assert_awaited_once()
    assert "อนุมัติ" in line_adapter._reply_with_token.await_args.args[1][0]


@pytest.mark.asyncio
async def test_image_message_downloaded_and_forwarded_as_photo(line_adapter, monkeypatch):
    from gateway.platforms.base import MessageType

    png_bytes = b"\x89PNG\r\n\x1a\nunit-test-image"
    fake_session = _FakeLineSession(
        _FakeLineContentResponse(body=png_bytes, content_type="image/png")
    )
    line_adapter._client_session = fake_session

    cached = {}

    def fake_cache_image(data, ext):
        cached["data"] = data
        cached["ext"] = ext
        return f"/tmp/line-image{ext}"

    monkeypatch.setattr(_line_mod, "cache_image_from_bytes", fake_cache_image)

    await line_adapter._handle_line_event(
        {
            "type": "message",
            "replyToken": "reply-token-1",
            "message": {"type": "image", "id": "line-image-message-1"},
            "source": {"type": "user", "userId": "Uparent"},
        }
    )

    assert fake_session.get_calls
    content_calls = [(url, kwargs) for url, kwargs in fake_session.get_calls if url.endswith("/v2/bot/message/line-image-message-1/content")]
    assert content_calls
    url, kwargs = content_calls[0]
    assert kwargs["headers"]["Authorization"] == "Bearer unit-test-token"

    assert cached == {"data": png_bytes, "ext": ".png"}
    line_adapter.handle_message.assert_awaited_once()
    forwarded = line_adapter.handle_message.await_args.args[0]
    assert forwarded.text == ""
    assert forwarded.message_type is MessageType.PHOTO
    assert forwarded.media_urls == ["/tmp/line-image.png"]
    assert forwarded.media_types == ["image/png"]
    assert forwarded.message_id == "line-image-message-1"
    assert line_adapter._reply_tokens["line-image-message-1"][0] == "reply-token-1"


@pytest.mark.asyncio
async def test_image_download_failure_does_not_call_agent(line_adapter):
    from gateway.platforms.base import SendResult

    line_adapter._client_session = _FakeLineSession(
        _FakeLineContentResponse(status=404, body=b"not found", content_type="text/plain", text="gone")
    )
    line_adapter._reply_with_token = AsyncMock(return_value=SendResult(success=True))

    await line_adapter._handle_line_event(
        {
            "type": "message",
            "replyToken": "reply-token-2",
            "message": {"type": "image", "id": "missing-image"},
            "source": {"type": "user", "userId": "Uparent"},
        }
    )

    line_adapter.handle_message.assert_not_called()
    line_adapter._reply_with_token.assert_awaited_once()
    notice = line_adapter._reply_with_token.await_args.args[1][0]
    assert "เปิดรูป" in notice


@pytest.mark.asyncio
async def test_oversized_image_is_rejected_before_agent(line_adapter):
    from gateway.platforms.base import SendResult

    too_large = line_adapter.media_max_bytes + 1
    response = _FakeLineContentResponse(
        body=b"",
        content_type="image/png",
    )
    response.headers["Content-Length"] = str(too_large)
    line_adapter._client_session = _FakeLineSession(response)
    line_adapter._reply_with_token = AsyncMock(return_value=SendResult(success=True))

    await line_adapter._handle_line_event(
        {
            "type": "message",
            "replyToken": "reply-token-3",
            "message": {"type": "image", "id": "huge-image"},
            "source": {"type": "user", "userId": "Uparent"},
        }
    )

    line_adapter.handle_message.assert_not_called()
    line_adapter._reply_with_token.assert_awaited_once()

@pytest.mark.asyncio
async def test_unauthorized_source_is_recorded_for_owner_approval(line_adapter, tmp_path):
    pending_path = tmp_path / "line_pending_approvals.jsonl"
    line_adapter.pending_approvals_path = str(pending_path)

    await line_adapter._handle_line_event(
        {
            "type": "message",
            "webhookEventId": "webhook-new-user",
            "message": {"type": "text", "id": "msg-new-user", "text": "สวัสดีค่ะ"},
            "source": {"type": "user", "userId": "Unewparent"},
        }
    )

    line_adapter.handle_message.assert_not_called()
    records = [json.loads(line) for line in pending_path.read_text().splitlines()]
    assert len(records) == 1
    assert records[0]["userId"] == "Unewparent"
    assert records[0]["chatId"] == "Unewparent"
    assert records[0]["event_type"] == "message"
    assert records[0]["messageType"] == "text"
    assert records[0]["text_preview"] == "สวัสดีค่ะ"
    assert records[0]["userHash"]


@pytest.mark.asyncio
async def test_group_message_requires_visible_mention_when_enabled(line_adapter):
    line_adapter.allowed_chats = {"Gfamily"}
    line_adapter.allowed_users = set()
    line_adapter.require_mention_in_groups = True

    await line_adapter._handle_line_event(
        {
            "type": "message",
            "webhookEventId": "group-unmentioned",
            "message": {"type": "text", "id": "msg-group-1", "text": "วันนี้กินยาแล้ว"},
            "source": {"type": "group", "groupId": "Gfamily", "userId": "Ufamily"},
        }
    )

    line_adapter.handle_message.assert_not_called()
    assert "msg-group-1" not in line_adapter._reply_tokens

    await line_adapter._handle_line_event(
        {
            "type": "message",
            "webhookEventId": "group-mentioned-visible",
            "message": {"type": "text", "id": "msg-group-2", "text": "@Helper ช่วยทำ kanban card ให้หน่อย"},
            "source": {"type": "group", "groupId": "Gfamily", "userId": "Ufamily"},
        }
    )

    line_adapter.handle_message.assert_awaited_once()
    forwarded = line_adapter.handle_message.await_args.args[0]
    assert forwarded.source.chat_id == "Gfamily"
    assert forwarded.text.startswith("@Helper")


@pytest.mark.asyncio
async def test_group_message_allows_native_line_mention_object(line_adapter):
    line_adapter.allowed_chats = {"Gfamily"}
    line_adapter.allowed_users = set()
    line_adapter.require_mention_in_groups = True
    line_adapter.bot_user_id = "Ubot"

    await line_adapter._handle_line_event(
        {
            "type": "message",
            "webhookEventId": "group-mentioned-native",
            "message": {
                "type": "text",
                "id": "msg-group-native",
                "text": "@Someone ช่วยดูนี่ที",
                "mention": {"mentionees": [{"index": 0, "length": 8, "userId": "Ubot"}]},
            },
            "source": {"type": "group", "groupId": "Gfamily", "userId": "Ufamily"},
        }
    )

    line_adapter.handle_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_group_mention_gate_does_not_block_care_postback(line_adapter):
    line_adapter.allowed_chats = {"Gfamily"}
    line_adapter.allowed_users = set()
    line_adapter.require_mention_in_groups = True
    line_adapter._handle_postback_event = AsyncMock()

    await line_adapter._handle_line_event(
        {
            "type": "postback",
            "webhookEventId": "care-postback",
            "postback": {"data": "care:v1;rid=abc;status=done"},
            "source": {"type": "group", "groupId": "Gfamily", "userId": "Ufamily"},
        }
    )

    line_adapter._handle_postback_event.assert_awaited_once()
    line_adapter.handle_message.assert_not_called()


@pytest.mark.asyncio
async def test_unmentioned_approved_group_text_is_injected_into_later_group_mention(line_adapter):
    line_adapter.allowed_chats = {"Gfamily"}
    line_adapter.allowed_users = set()
    line_adapter.require_mention_in_groups = True

    async def fake_enrich(source, source_data):
        names = {"Udad": "คุณพ่อ", "Uoperator": "Operator"}
        source.user_name = names.get(source.user_id, "LINE user")

    line_adapter._enrich_source_profile = fake_enrich

    await line_adapter._handle_line_event(
        {
            "type": "message",
            "webhookEventId": "group-context-unmentioned-dad",
            "message": {"type": "text", "id": "dad-context-1", "text": "วันนี้กินยาแล้ว"},
            "source": {"type": "group", "groupId": "Gfamily", "userId": "Udad"},
        }
    )

    line_adapter.handle_message.assert_not_called()

    await line_adapter._handle_line_event(
        {
            "type": "message",
            "webhookEventId": "group-context-mentioned-operator",
            "message": {"type": "text", "id": "operator-mention-1", "text": "@Helper จดที่คุณพ่อส่งไว้หน่อย"},
            "source": {"type": "group", "groupId": "Gfamily", "userId": "Uoperator"},
        }
    )

    line_adapter.handle_message.assert_awaited_once()
    forwarded = line_adapter.handle_message.await_args.args[0]
    assert forwarded.text == "@Helper จดที่คุณพ่อส่งไว้หน่อย"
    assert forwarded.channel_prompt
    assert "Recent approved LINE group context" in forwarded.channel_prompt
    assert "คุณพ่อ: วันนี้กินยาแล้ว" in forwarded.channel_prompt
    assert "@Helper จดที่คุณพ่อ" not in forwarded.channel_prompt


@pytest.mark.asyncio
async def test_operator_dm_can_reference_recent_approved_group_text(line_adapter):
    line_adapter.allowed_chats = {"Gfamily"}
    line_adapter.allowed_users = {"Uparent"}
    line_adapter.require_mention_in_groups = True

    async def fake_enrich(source, source_data):
        names = {"Udad": "คุณพ่อ", "Uparent": "Operator"}
        source.user_name = names.get(source.user_id, "LINE user")

    line_adapter._enrich_source_profile = fake_enrich

    await line_adapter._handle_line_event(
        {
            "type": "message",
            "webhookEventId": "group-context-unmentioned-dm-bridge",
            "message": {"type": "text", "id": "dad-context-dm", "text": "พ่อส่งเลขบัญชีไว้ในไลน์กลุ่ม"},
            "source": {"type": "group", "groupId": "Gfamily", "userId": "Udad"},
        }
    )
    line_adapter.handle_message.assert_not_called()

    await line_adapter._handle_line_event(
        {
            "type": "message",
            "webhookEventId": "operator-dm-asks-group-context",
            "message": {"type": "text", "id": "operator-dm-1", "text": "ในกลุ่มคุณพ่อส่งอะไรไว้เมื่อกี้"},
            "source": {"type": "user", "userId": "Uparent"},
        }
    )

    line_adapter.handle_message.assert_awaited_once()
    forwarded = line_adapter.handle_message.await_args.args[0]
    assert forwarded.source.chat_type == "dm"
    assert forwarded.channel_prompt
    assert "พ่อส่งเลขบัญชีไว้ในไลน์กลุ่ม" in forwarded.channel_prompt


@pytest.mark.asyncio
async def test_allowed_non_operator_dm_does_not_receive_group_context(line_adapter):
    line_adapter.allowed_chats = {"Gfamily"}
    line_adapter.allowed_users = {"Uparent", "Uhelper"}
    line_adapter.recent_context_operator_users = {"Uparent"}
    line_adapter.require_mention_in_groups = True

    await line_adapter._handle_line_event(
        {
            "type": "message",
            "webhookEventId": "group-context-private",
            "message": {"type": "text", "id": "private-context", "text": "ข้อมูลครอบครัวในกลุ่ม"},
            "source": {"type": "group", "groupId": "Gfamily", "userId": "Udad"},
        }
    )
    line_adapter.handle_message.assert_not_called()

    await line_adapter._handle_line_event(
        {
            "type": "message",
            "webhookEventId": "non-operator-dm-asks-group-context",
            "message": {"type": "text", "id": "helper-dm-1", "text": "ในกลุ่มพูดอะไรเมื่อกี้"},
            "source": {"type": "user", "userId": "Uhelper"},
        }
    )

    line_adapter.handle_message.assert_awaited_once()
    forwarded = line_adapter.handle_message.await_args.args[0]
    assert forwarded.source.user_id == "Uhelper"
    assert forwarded.channel_prompt is None


@pytest.mark.asyncio
async def test_operator_dm_can_attach_recent_approved_group_image(line_adapter, monkeypatch):
    from gateway.platforms.base import MessageType

    line_adapter.allowed_chats = {"Gfamily"}
    line_adapter.allowed_users = {"Uparent"}
    line_adapter.require_mention_in_groups = True
    png_bytes = b"\x89PNG\r\n\x1a\nrecent-group-image-for-dm"
    fake_session = _FakeLineSession(
        _FakeLineContentResponse(body=png_bytes, content_type="image/png")
    )
    line_adapter._client_session = fake_session

    cached = {}

    def fake_cache_image(data, ext):
        cached["data"] = data
        cached["ext"] = ext
        return f"/tmp/operator-dm-group-image{ext}"

    monkeypatch.setattr(_line_mod, "cache_image_from_bytes", fake_cache_image)

    await line_adapter._handle_line_event(
        {
            "type": "message",
            "replyToken": "reply-token-group-image",
            "webhookEventId": "group-image-for-operator-dm",
            "message": {"type": "image", "id": "group-image-dm-bridge"},
            "source": {"type": "group", "groupId": "Gfamily", "userId": "Umum"},
        }
    )
    line_adapter.handle_message.assert_not_called()
    assert not any(url.endswith("/content") for url, _kwargs in fake_session.get_calls)

    await line_adapter._handle_line_event(
        {
            "type": "message",
            "replyToken": "reply-token-operator-dm-image",
            "webhookEventId": "operator-dm-asks-group-image",
            "message": {"type": "text", "id": "operator-dm-image", "text": "ลองดูรูปในกลุ่มที่คุณแม่ส่งมาเมื่อกี้"},
            "source": {"type": "user", "userId": "Uparent"},
        }
    )

    content_calls = [
        url for url, _kwargs in fake_session.get_calls
        if url.endswith("/v2/bot/message/group-image-dm-bridge/content")
    ]
    assert content_calls
    assert cached == {"data": png_bytes, "ext": ".png"}
    line_adapter.handle_message.assert_awaited_once()
    forwarded = line_adapter.handle_message.await_args.args[0]
    assert forwarded.message_type is MessageType.PHOTO
    assert forwarded.media_urls == ["/tmp/operator-dm-group-image.png"]
    assert forwarded.media_types == ["image/png"]
    assert forwarded.channel_prompt
    assert "sent an image" in forwarded.channel_prompt


@pytest.mark.asyncio
async def test_unmentioned_group_image_is_remembered_without_download(line_adapter):
    line_adapter.allowed_chats = {"Gfamily"}
    line_adapter.allowed_users = set()
    line_adapter.require_mention_in_groups = True
    fake_session = _FakeLineSession(
        _FakeLineContentResponse(body=b"image", content_type="image/png")
    )
    line_adapter._client_session = fake_session

    await line_adapter._handle_line_event(
        {
            "type": "message",
            "replyToken": "reply-token-image",
            "webhookEventId": "group-image-unmentioned",
            "message": {"type": "image", "id": "image-no-mention"},
            "source": {"type": "group", "groupId": "Gfamily", "userId": "Ufamily"},
        }
    )

    content_calls = [
        url for url, _kwargs in fake_session.get_calls
        if url.endswith("/v2/bot/message/image-no-mention/content")
    ]
    assert content_calls == []
    line_adapter.handle_message.assert_not_called()
    assert "image-no-mention" not in line_adapter._reply_tokens
    assert line_adapter._pending_group_media["Gfamily"][0]["message_id"] == "image-no-mention"


@pytest.mark.asyncio
async def test_mentioned_group_text_attaches_recent_unmentioned_image(line_adapter, monkeypatch):
    from gateway.platforms.base import MessageType

    line_adapter.allowed_chats = {"Gfamily"}
    line_adapter.allowed_users = set()
    line_adapter.require_mention_in_groups = True
    png_bytes = b"\x89PNG\r\n\x1a\nremembered-group-image"
    fake_session = _FakeLineSession(
        _FakeLineContentResponse(body=png_bytes, content_type="image/png")
    )
    line_adapter._client_session = fake_session

    cached = {}

    def fake_cache_image(data, ext):
        cached["data"] = data
        cached["ext"] = ext
        return f"/tmp/group-image{ext}"

    monkeypatch.setattr(_line_mod, "cache_image_from_bytes", fake_cache_image)

    await line_adapter._handle_line_event(
        {
            "type": "message",
            "replyToken": "reply-token-image",
            "webhookEventId": "group-image-unmentioned",
            "message": {"type": "image", "id": "image-no-mention"},
            "source": {"type": "group", "groupId": "Gfamily", "userId": "Ufamily"},
        }
    )
    line_adapter.handle_message.assert_not_called()

    await line_adapter._handle_line_event(
        {
            "type": "message",
            "replyToken": "reply-token-text",
            "webhookEventId": "group-mentioned-after-image",
            "message": {"type": "text", "id": "text-mentions-image", "text": "รูปข้างบน @Helper"},
            "source": {"type": "group", "groupId": "Gfamily", "userId": "Ufamily"},
        }
    )

    content_calls = [
        url for url, _kwargs in fake_session.get_calls
        if url.endswith("/v2/bot/message/image-no-mention/content")
    ]
    assert content_calls
    assert cached == {"data": png_bytes, "ext": ".png"}
    line_adapter.handle_message.assert_awaited_once()
    forwarded = line_adapter.handle_message.await_args.args[0]
    assert forwarded.message_type is MessageType.PHOTO
    assert forwarded.text == "รูปข้างบน @Helper"
    assert forwarded.message_id == "text-mentions-image"
    assert forwarded.media_urls == ["/tmp/group-image.png"]
    assert forwarded.media_types == ["image/png"]
    assert forwarded.raw_message["linked_line_media"] == [{"messageId": "image-no-mention", "type": "image"}]
    assert "Gfamily" not in line_adapter._pending_group_media


@pytest.mark.asyncio
async def test_mentioned_group_text_attaches_multiple_recent_unmentioned_images(line_adapter, monkeypatch):
    from gateway.platforms.base import MessageType

    line_adapter.allowed_chats = {"Gfamily"}
    line_adapter.allowed_users = set()
    line_adapter.require_mention_in_groups = True
    png_bytes = b"\x89PNG\r\n\x1a\nremembered-group-image"
    fake_session = _FakeLineSession(
        _FakeLineContentResponse(body=png_bytes, content_type="image/png")
    )
    line_adapter._client_session = fake_session

    cached = []

    def fake_cache_image(data, ext):
        cached.append((data, ext))
        return f"/tmp/group-image-{len(cached)}{ext}"

    monkeypatch.setattr(_line_mod, "cache_image_from_bytes", fake_cache_image)

    for idx in range(3):
        await line_adapter._handle_line_event(
            {
                "type": "message",
                "replyToken": f"reply-token-image-{idx}",
                "webhookEventId": f"group-image-unmentioned-{idx}",
                "message": {"type": "image", "id": f"image-no-mention-{idx}"},
                "source": {"type": "group", "groupId": "Gfamily", "userId": "Ufamily"},
            }
        )

    line_adapter.handle_message.assert_not_called()
    assert [entry["message_id"] for entry in line_adapter._pending_group_media["Gfamily"]] == [
        "image-no-mention-0",
        "image-no-mention-1",
        "image-no-mention-2",
    ]

    await line_adapter._handle_line_event(
        {
            "type": "message",
            "replyToken": "reply-token-text",
            "webhookEventId": "group-mentioned-after-images",
            "message": {"type": "text", "id": "text-mentions-images", "text": "@Helper ดูรูปพวกนี้หน่อย"},
            "source": {"type": "group", "groupId": "Gfamily", "userId": "Ufamily"},
        }
    )

    content_calls = [
        url for url, _kwargs in fake_session.get_calls
        if "/v2/bot/message/image-no-mention-" in url and url.endswith("/content")
    ]
    assert len(content_calls) == 3
    assert cached == [(png_bytes, ".png"), (png_bytes, ".png"), (png_bytes, ".png")]
    line_adapter.handle_message.assert_awaited_once()
    forwarded = line_adapter.handle_message.await_args.args[0]
    assert forwarded.message_type is MessageType.PHOTO
    assert forwarded.text == "@Helper ดูรูปพวกนี้หน่อย"
    assert forwarded.message_id == "text-mentions-images"
    assert forwarded.media_urls == [
        "/tmp/group-image-1.png",
        "/tmp/group-image-2.png",
        "/tmp/group-image-3.png",
    ]
    assert forwarded.media_types == ["image/png", "image/png", "image/png"]
    assert forwarded.raw_message["linked_line_media"] == [
        {"messageId": "image-no-mention-0", "type": "image"},
        {"messageId": "image-no-mention-1", "type": "image"},
        {"messageId": "image-no-mention-2", "type": "image"},
    ]
    assert "Gfamily" not in line_adapter._pending_group_media


@pytest.mark.asyncio
async def test_sticker_message_forwarded_as_sticker_without_unsupported_reply(line_adapter):
    from gateway.platforms.base import MessageType, SendResult

    line_adapter._reply_with_token = AsyncMock(return_value=SendResult(success=True))

    await line_adapter._handle_line_event(
        {
            "type": "message",
            "replyToken": "reply-token-sticker",
            "webhookEventId": "webhook-sticker",
            "message": {
                "type": "sticker",
                "id": "line-sticker-message-1",
                "packageId": "446",
                "stickerId": "1988",
                "stickerResourceType": "STATIC",
                "keywords": ["happy", "thumbs up"],
            },
            "source": {"type": "user", "userId": "Uparent"},
        }
    )

    line_adapter._reply_with_token.assert_not_called()
    line_adapter.handle_message.assert_awaited_once()
    forwarded = line_adapter.handle_message.await_args.args[0]
    assert forwarded.message_type is MessageType.STICKER
    assert forwarded.message_id == "line-sticker-message-1"
    assert forwarded.media_urls == []
    assert forwarded.media_types == []
    assert "LINE sticker" in forwarded.text
    assert "446" in forwarded.text
    assert "1988" in forwarded.text
    assert "happy" in forwarded.text
    assert "thumbs up" in forwarded.text
    assert line_adapter._reply_tokens["line-sticker-message-1"][0] == "reply-token-sticker"


@pytest.mark.asyncio
async def test_unmentioned_group_sticker_is_dropped_without_unsupported_reply(line_adapter):
    from gateway.platforms.base import SendResult

    line_adapter.allowed_chats = {"Gfamily"}
    line_adapter.allowed_users = set()
    line_adapter.require_mention_in_groups = True
    line_adapter._reply_with_token = AsyncMock(return_value=SendResult(success=True))

    await line_adapter._handle_line_event(
        {
            "type": "message",
            "replyToken": "reply-token-unmentioned-sticker",
            "webhookEventId": "group-sticker-unmentioned",
            "message": {"type": "sticker", "id": "sticker-no-mention", "packageId": "446", "stickerId": "1988"},
            "source": {"type": "group", "groupId": "Gfamily", "userId": "Ufamily"},
        }
    )

    line_adapter.handle_message.assert_not_called()
    line_adapter._reply_with_token.assert_not_called()
    assert "sticker-no-mention" not in line_adapter._reply_tokens


@pytest.mark.asyncio
async def test_unauthorized_audio_is_dropped_before_download(line_adapter, tmp_path):
    pending_path = tmp_path / "pending-audio.jsonl"
    line_adapter.pending_approvals_path = str(pending_path)
    line_adapter.allowed_users = {"Uparent"}
    fake_session = _FakeLineSession(
        _FakeLineContentResponse(body=b"\x00\x00\x00\x18ftypM4A unauthorized", content_type="audio/mp4")
    )
    line_adapter._client_session = fake_session

    await line_adapter._handle_line_event(
        {
            "type": "message",
            "replyToken": "reply-token-unauthorized-audio",
            "message": {"type": "audio", "id": "unauthorized-audio"},
            "source": {"type": "user", "userId": "Ustranger"},
        }
    )

    assert fake_session.get_calls == []
    line_adapter.handle_message.assert_not_called()
    records = [json.loads(line) for line in pending_path.read_text().splitlines()]
    assert records[0]["messageType"] == "audio"


@pytest.mark.asyncio
async def test_audio_message_downloaded_and_forwarded_as_voice(line_adapter, monkeypatch):
    from gateway.platforms.base import MessageType

    m4a_bytes = b"\x00\x00\x00\x18ftypM4A unit-test-audio"
    fake_session = _FakeLineSession(
        _FakeLineContentResponse(body=m4a_bytes, content_type="audio/mp4")
    )
    line_adapter._client_session = fake_session

    cached = {}

    def fake_cache_audio(data, ext):
        cached["data"] = data
        cached["ext"] = ext
        return f"/tmp/line-audio{ext}"

    monkeypatch.setattr(_line_mod, "cache_audio_from_bytes", fake_cache_audio)

    await line_adapter._handle_line_event(
        {
            "type": "message",
            "replyToken": "reply-token-audio",
            "message": {"type": "audio", "id": "line-audio-message-1", "duration": 1200},
            "source": {"type": "user", "userId": "Uparent"},
        }
    )

    assert fake_session.get_calls
    content_calls = [
        (url, kwargs) for url, kwargs in fake_session.get_calls
        if url.endswith("/v2/bot/message/line-audio-message-1/content")
    ]
    assert content_calls
    url, kwargs = content_calls[0]
    assert kwargs["headers"]["Authorization"] == "Bearer unit-test-token"

    assert cached == {"data": m4a_bytes, "ext": ".m4a"}
    line_adapter.handle_message.assert_awaited_once()
    forwarded = line_adapter.handle_message.await_args.args[0]
    assert forwarded.text == ""
    assert forwarded.message_type is MessageType.VOICE
    assert forwarded.media_urls == ["/tmp/line-audio.m4a"]
    assert forwarded.media_types == ["audio/mp4"]
    assert forwarded.message_id == "line-audio-message-1"
    assert line_adapter._reply_tokens["line-audio-message-1"][0] == "reply-token-audio"


@pytest.mark.asyncio
async def test_audio_download_failure_does_not_call_agent(line_adapter):
    from gateway.platforms.base import SendResult

    line_adapter._client_session = _FakeLineSession(
        _FakeLineContentResponse(status=404, body=b"not found", content_type="text/plain", text="gone")
    )
    line_adapter._reply_with_token = AsyncMock(return_value=SendResult(success=True))

    await line_adapter._handle_line_event(
        {
            "type": "message",
            "replyToken": "reply-token-audio-fail",
            "message": {"type": "audio", "id": "missing-audio"},
            "source": {"type": "user", "userId": "Uparent"},
        }
    )

    line_adapter.handle_message.assert_not_called()
    line_adapter._reply_with_token.assert_awaited_once()
    notice = line_adapter._reply_with_token.await_args.args[1][0]
    assert "ฟังเสียง" in notice


@pytest.mark.asyncio
async def test_oversized_audio_is_rejected_before_agent(line_adapter):
    from gateway.platforms.base import SendResult

    too_large = line_adapter.media_max_bytes + 1
    response = _FakeLineContentResponse(
        body=b"",
        content_type="audio/mp4",
    )
    response.headers["Content-Length"] = str(too_large)
    line_adapter._client_session = _FakeLineSession(response)
    line_adapter._reply_with_token = AsyncMock(return_value=SendResult(success=True))

    await line_adapter._handle_line_event(
        {
            "type": "message",
            "replyToken": "reply-token-huge-audio",
            "message": {"type": "audio", "id": "huge-audio"},
            "source": {"type": "user", "userId": "Uparent"},
        }
    )

    assert line_adapter._client_session.get_calls
    line_adapter.handle_message.assert_not_called()
    line_adapter._reply_with_token.assert_awaited_once()


@pytest.mark.asyncio
async def test_reply_token_text_reply_never_spills_overflow_into_push(line_adapter):
    from gateway.platforms.base import SendResult

    line_adapter._reply_tokens["line-message-1"] = ("reply-token-1", "Uparent", time.time())
    line_adapter._split_text = lambda text: [f"chunk-{idx}" for idx in range(7)]
    line_adapter._reply_with_token = AsyncMock(return_value=SendResult(success=True, message_id="line-reply-1"))
    line_adapter._push_message = AsyncMock(return_value=SendResult(success=True, message_id="line-push-1"))

    result = await line_adapter.send("Uparent", "ignored long model reply", reply_to="line-message-1")

    assert result.success
    line_adapter._reply_with_token.assert_awaited_once()
    reply_chunks = line_adapter._reply_with_token.await_args.args[1]
    assert len(reply_chunks) == 5
    assert any("truncated" in chunk.lower() or "ย่อ" in chunk for chunk in reply_chunks)
    line_adapter._push_message.assert_not_called()


@pytest.mark.asyncio
async def test_failed_line_reply_token_does_not_fallback_to_push_quota(line_adapter):
    from gateway.platforms.base import SendResult

    line_adapter._reply_tokens["line-message-2"] = ("reply-token-2", "Uparent", time.time())
    line_adapter._reply_with_token = AsyncMock(
        return_value=SendResult(success=False, error="LINE reply token expired", retryable=False)
    )
    line_adapter._push_message = AsyncMock(return_value=SendResult(success=True, message_id="line-push-2"))

    result = await line_adapter.send("Uparent", "normal reply", reply_to="line-message-2")

    assert not result.success
    assert "reply" in result.error.lower()
    assert result.retryable is False
    line_adapter._push_message.assert_not_called()


@pytest.mark.asyncio
async def test_proactive_text_without_reply_token_still_uses_push_for_reminders(line_adapter):
    from gateway.platforms.base import SendResult

    line_adapter._reply_with_token = AsyncMock(return_value=SendResult(success=True, message_id="line-reply"))
    line_adapter._push_message = AsyncMock(return_value=SendResult(success=True, message_id="line-push"))

    result = await line_adapter.send("Uparent", "reminder push")

    assert result.success
    line_adapter._reply_with_token.assert_not_called()
    line_adapter._push_message.assert_awaited_once_with("Uparent", "reminder push")


@pytest.mark.asyncio
async def test_line_push_quota_429_is_non_retryable(line_adapter):
    line_adapter._client_session = _FakeLinePostSession(
        _FakeLineApiResponse(status=429, text='{"message":"You have reached your monthly limit."}')
    )

    result = await line_adapter._push_message("Uparent", "quota test")

    assert not result.success
    assert result.retryable is False
    assert "quota" in result.error.lower()
    url, kwargs = line_adapter._client_session.post_calls[0]
    assert url.endswith("/v2/bot/message/push")
    assert kwargs["json"]["to"] == "Uparent"


@pytest.mark.asyncio
async def test_send_plain_text_sanitizes_markdown_for_line(line_adapter):
    from gateway.platforms.base import SendResult

    sent = []

    async def fake_post_json(url, payload, **kwargs):
        sent.append((url, payload, kwargs))
        return SendResult(success=True, message_id="sent-text", raw_response={"ok": True})

    line_adapter._post_json = fake_post_json

    result = await line_adapter.send(
        "Uparent",
        "ตอนนี้ตามที่ตั้งไว้: **ตอบเฉพาะเวลาโดน mention ในกลุ่มค่ะ** ✅\n\n"
        "• เช่น `@Helper` / `@ผู้ช่วย` หรือ LINE native mention\n"
        "• ข้อความคุยกันทั่วไปในกลุ่ม → ผู้ช่วยควรเงียบ\n"
        "แง operatorจับได้เลย 😅\n\nผู้ช่วยพูดไม่แม่นค่ะ — ควรบอกว่าให้ใช้ข้อความธรรมดา",
    )

    assert result.success
    text = sent[0][1]["messages"][0]["text"]
    assert "**" not in text
    assert "`" not in text
    assert "•" not in text
    assert "→" not in text
    assert "—" not in text
    assert "ตอบเฉพาะเวลาโดน mention ในกลุ่มค่ะ" in text
    assert "@Helper" in text


@pytest.mark.asyncio
async def test_send_confirm_rich_payload_pushes_template_message(line_adapter):
    from gateway.platforms.base import SendResult

    sent = []

    async def fake_post_json(url, payload, **kwargs):
        sent.append((url, payload, kwargs))
        return SendResult(success=True, message_id="sent-rich", raw_response={"ok": True})

    line_adapter._post_json = fake_post_json

    result = await line_adapter.send(
        "Uparent",
        'LINE_RICH:{"type":"confirm","altText":"เตือนยืดหลัง","text":"คุณพ่อยืดหลังแล้วหรือยังคะ?","actions":[{"label":"ทำแล้ว ✅","text":"พ่อทำแล้ว"},{"label":"ยังค่ะ","text":"พ่อยังก่อน"}]}',
    )

    assert result.success
    assert sent
    url, payload, _ = sent[0]
    assert url.endswith("/v2/bot/message/push")
    assert payload["to"] == "Uparent"
    assert payload["messages"] == [
        {
            "type": "template",
            "altText": "เตือนยืดหลัง",
            "template": {
                "type": "confirm",
                "text": "คุณพ่อยืดหลังแล้วหรือยังคะ?",
                "actions": [
                    {"type": "message", "label": "ทำแล้ว ✅", "text": "พ่อทำแล้ว"},
                    {"type": "message", "label": "ยังค่ะ", "text": "พ่อยังก่อน"},
                ],
            },
        }
    ]
    assert "LINE_RICH" not in json.dumps(payload, ensure_ascii=False)


@pytest.mark.asyncio
async def test_send_confirm_rich_payload_can_be_embedded_in_cron_wrapper(line_adapter):
    from gateway.platforms.base import SendResult

    sent = []

    async def fake_post_json(url, payload, **kwargs):
        sent.append((url, payload, kwargs))
        return SendResult(success=True, message_id="sent-rich", raw_response={"ok": True})

    line_adapter._post_json = fake_post_json

    wrapped = """Cronjob Response: Dad stretch
(job_id: test)
-------------

LINE_RICH:{"type":"confirm","altText":"เช็กยา","text":"คุณแม่กินยาตอนเช้าแล้วหรือยังคะ?","actions":[{"label":"กินแล้ว","text":"แม่กินยาเช้าแล้ว"},{"label":"ยัง","text":"แม่ยังไม่ได้กินยาเช้า"}]}

To stop or manage this job, send me a new message.
"""

    result = await line_adapter.send("Uparent", wrapped)

    assert result.success
    assert sent[0][1]["messages"][0]["template"]["text"] == "คุณแม่กินยาตอนเช้าแล้วหรือยังคะ?"
    assert "Cronjob Response" not in json.dumps(sent[0][1], ensure_ascii=False)


@pytest.mark.asyncio
async def test_send_bare_confirm_json_from_cron_response_pushes_template_message(line_adapter):
    from gateway.platforms.base import SendResult

    sent = []

    async def fake_post_json(url, payload, **kwargs):
        sent.append((url, payload, kwargs))
        return SendResult(success=True, message_id="sent-rich", raw_response={"ok": True})

    line_adapter._post_json = fake_post_json

    result = await line_adapter.send(
        "Uparent",
        '{"type":"confirm","altText":"เช็กยา","text":"คุณแม่กินยาก่อนนอนแล้วหรือยังคะ?","actions":[{"label":"กินแล้ว","text":"แม่กินยาแล้ว"},{"label":"ยัง","text":"แม่ยังไม่ได้กินยา"}]}',
    )

    assert result.success
    assert sent
    assert sent[0][1]["messages"][0]["type"] == "template"
    assert sent[0][1]["messages"][0]["template"]["text"] == "คุณแม่กินยาก่อนนอนแล้วหรือยังคะ?"
    assert sent[0][1]["messages"][0]["template"]["actions"][0]["label"] == "กินแล้ว"
    assert "LINE_RICH" not in json.dumps(sent[0][1], ensure_ascii=False)


@pytest.mark.asyncio
async def test_send_arbitrary_bare_json_stays_plain_text(line_adapter):
    from gateway.platforms.base import SendResult

    sent = []

    async def fake_post_json(url, payload, **kwargs):
        sent.append((url, payload, kwargs))
        return SendResult(success=True, message_id="sent-text", raw_response={"ok": True})

    line_adapter._post_json = fake_post_json

    result = await line_adapter.send("Uparent", '{"not":"a LINE rich card"}')

    assert result.success
    assert sent[0][1]["messages"] == [{"type": "text", "text": '{"not":"a LINE rich card"}'}]


@pytest.mark.asyncio
async def test_care_rich_payload_logs_separate_mum_and_dad_reminders(line_adapter, tmp_path):
    from gateway.platforms.base import SendResult

    line_adapter.care_store = _line_mod.LineCareEventStore(
        db_path=str(tmp_path / "care_events.sqlite"),
        audit_path=str(tmp_path / "care_events.jsonl"),
    )
    sent = []

    async def fake_post_json(url, payload, **kwargs):
        sent.append((url, payload, kwargs))
        return SendResult(success=True, message_id=f"line-message-{len(sent)}", raw_response={"ok": True})

    line_adapter._post_json = fake_post_json

    mum_result = await line_adapter.send(
        "Uparent",
        'LINE_RICH:{"type":"confirm","altText":"เช็กยาคุณแม่","text":"คุณแม่กินยาตอนเช้าแล้วหรือยังคะ?","care":{"subject":"mum","routine_id":"mum_morning_meds","routine_type":"medication","slot":"morning"},"actions":[{"label":"กินแล้ว ✅","status":"done"},{"label":"ยังค่ะ","status":"not_yet"}]}',
    )
    dad_result = await line_adapter.send(
        "Uparent",
        'LINE_RICH:{"type":"confirm","altText":"เช็กยืดหลังคุณพ่อ","text":"คุณพ่อยืดหลังตอนเช้าแล้วหรือยังคะ?","care":{"subject":"dad","routine_id":"dad_back_stretch_morning","routine_type":"stretch","slot":"morning"},"actions":[{"label":"ทำแล้ว ✅","status":"done"},{"label":"ยังค่ะ","status":"not_yet"}]}',
    )

    assert mum_result.success
    assert dad_result.success
    assert len(sent) == 2

    mum_message = sent[0][1]["messages"][0]
    dad_message = sent[1][1]["messages"][0]
    assert mum_message["type"] == "flex"
    assert dad_message["type"] == "flex"

    mum_bubble = mum_message["contents"]
    dad_bubble = dad_message["contents"]
    assert mum_bubble["size"] == "mega"
    assert dad_bubble["size"] == "mega"
    assert mum_bubble["header"]["backgroundColor"] == "#FFF7ED"
    assert dad_bubble["header"]["backgroundColor"] == "#EFF6FF"
    assert mum_bubble["header"]["paddingAll"] == "10px"
    assert dad_bubble["body"]["paddingAll"] == "10px"
    assert mum_bubble["footer"]["paddingAll"] == "10px"
    assert dad_bubble["footer"]["paddingAll"] == "10px"
    assert mum_bubble["footer"]["layout"] == "horizontal"
    assert dad_bubble["footer"]["layout"] == "horizontal"
    assert len(mum_bubble["footer"]["contents"]) == 2
    assert len(dad_bubble["footer"]["contents"]) == 2

    mum_texts = _flex_text_values(mum_bubble)
    dad_texts = _flex_text_values(dad_bubble)
    assert "เช็กยาคุณแม่" not in mum_texts
    assert "ยืดหลังคุณพ่อ" not in dad_texts
    assert mum_texts.count("ตอบสั้น ๆ ได้เลยค่ะ") == 0
    assert dad_texts.count("ตอบสั้น ๆ ได้เลยค่ะ") == 0
    assert "รายการวันนี้" in mum_texts
    assert "เช็กยา คุณแม่" in mum_texts
    assert "กายภาพเบา ๆ" in dad_texts
    assert "ยืดหลัง คุณพ่อ" in dad_texts

    mum_buttons = _care_flex_buttons(mum_message)
    dad_buttons = _care_flex_buttons(dad_message)
    assert len(mum_buttons) == 2
    assert len(dad_buttons) == 2
    assert mum_buttons[0]["style"] == "primary"
    assert dad_buttons[0]["style"] == "primary"
    assert mum_buttons[0]["height"] == "sm"
    assert dad_buttons[0]["height"] == "sm"
    assert mum_buttons[0]["color"] == "#EA580C"
    assert dad_buttons[0]["color"] == "#2563EB"

    mum_actions = _actions_from_care_message(mum_message)
    dad_actions = _actions_from_care_message(dad_message)
    assert {action["type"] for action in mum_actions + dad_actions} == {"postback"}
    assert all(action["data"].startswith("care:v1;rid=") for action in mum_actions + dad_actions)
    assert all(action.get("displayText") for action in mum_actions + dad_actions)

    mum_rid = mum_actions[0]["data"].split(";", 2)[1].removeprefix("rid=")
    dad_rid = dad_actions[0]["data"].split(";", 2)[1].removeprefix("rid=")
    assert mum_rid != dad_rid

    reminders = {row["reminder_id"]: row for row in line_adapter.care_store.list_reminders()}
    assert reminders[mum_rid]["subject"] == "mum"
    assert reminders[mum_rid]["routine_id"] == "mum_morning_meds"
    assert reminders[dad_rid]["subject"] == "dad"
    assert reminders[dad_rid]["routine_id"] == "dad_back_stretch_morning"

    sent_events = [event for event in line_adapter.care_store.list_events() if event["event_type"] == "reminder_sent"]
    assert {(event["subject"], event["routine_id"]) for event in sent_events} == {
        ("mum", "mum_morning_meds"),
        ("dad", "dad_back_stretch_morning"),
    }


@pytest.mark.asyncio
async def test_care_postback_logs_response_for_original_subject_without_calling_agent(line_adapter, tmp_path):
    from gateway.platforms.base import SendResult

    line_adapter.care_store = _line_mod.LineCareEventStore(
        db_path=str(tmp_path / "care_events.sqlite"),
        audit_path=str(tmp_path / "care_events.jsonl"),
    )
    sent = []

    async def fake_post_json(url, payload, **kwargs):
        sent.append(payload)
        return SendResult(success=True, message_id="line-message-mum", raw_response={"ok": True})

    line_adapter._post_json = fake_post_json
    line_adapter._reply_with_token = AsyncMock(return_value=SendResult(success=True))

    await line_adapter.send(
        "Uparent",
        'LINE_RICH:{"type":"confirm","altText":"เช็กยาคุณแม่","text":"คุณแม่กินยาตอนเช้าแล้วหรือยังคะ?","care":{"subject":"mum","routine_id":"mum_morning_meds","routine_type":"medication","slot":"morning"},"actions":[{"label":"กินแล้ว ✅","status":"done"},{"label":"ยังค่ะ","status":"not_yet"}]}',
    )
    rid = _actions_from_care_message(sent[0]["messages"][0])[0]["data"].split(";", 2)[1].removeprefix("rid=")

    await line_adapter._handle_line_event(
        {
            "type": "postback",
            "webhookEventId": "webhook-mum-done-1",
            "replyToken": "reply-token-postback",
            "postback": {"data": f"care:v1;rid={rid};status=done"},
            "source": {"type": "user", "userId": "Uparent"},
        }
    )

    line_adapter.handle_message.assert_not_called()
    responses = [event for event in line_adapter.care_store.list_events() if event["event_type"] == "response"]
    assert len(responses) == 1
    assert responses[0]["subject"] == "mum"
    assert responses[0]["routine_id"] == "mum_morning_meds"
    assert responses[0]["status"] == "done"
    assert responses[0]["actor_hash"]
    assert responses[0]["chat_hash"]
    assert "Uparent" not in json.dumps(responses, ensure_ascii=False)
    line_adapter._reply_with_token.assert_awaited_once()
    confirmation = line_adapter._reply_with_token.await_args.args[1][0]
    assert "คุณแม่" in confirmation


@pytest.mark.asyncio
async def test_care_postback_duplicate_and_unauthorized_events_do_not_create_extra_responses(line_adapter, tmp_path):
    from gateway.platforms.base import SendResult

    line_adapter.care_store = _line_mod.LineCareEventStore(
        db_path=str(tmp_path / "care_events.sqlite"),
        audit_path=str(tmp_path / "care_events.jsonl"),
    )
    pending_path = tmp_path / "pending.jsonl"
    line_adapter.pending_approvals_path = str(pending_path)
    sent = []

    async def fake_post_json(url, payload, **kwargs):
        sent.append(payload)
        return SendResult(success=True, message_id="line-message-dad", raw_response={"ok": True})

    line_adapter._post_json = fake_post_json
    line_adapter._reply_with_token = AsyncMock(return_value=SendResult(success=True))

    await line_adapter.send(
        "Uparent",
        'LINE_RICH:{"type":"confirm","altText":"เช็กยืดหลังคุณพ่อ","text":"คุณพ่อยืดหลังตอนเช้าแล้วหรือยังคะ?","care":{"subject":"dad","routine_id":"dad_back_stretch_morning","routine_type":"stretch","slot":"morning"},"actions":[{"label":"ทำแล้ว ✅","status":"done"},{"label":"ยังค่ะ","status":"not_yet"}]}',
    )
    rid = _actions_from_care_message(sent[0]["messages"][0])[0]["data"].split(";", 2)[1].removeprefix("rid=")

    duplicate_event = {
        "type": "postback",
        "webhookEventId": "webhook-dad-done-1",
        "replyToken": "reply-token-dad-1",
        "postback": {"data": f"care:v1;rid={rid};status=done"},
        "source": {"type": "user", "userId": "Uparent"},
    }
    await line_adapter._handle_line_event(duplicate_event)
    await line_adapter._handle_line_event(duplicate_event)

    unauthorized_event = {
        "type": "postback",
        "webhookEventId": "webhook-dad-stranger-1",
        "replyToken": "reply-token-stranger",
        "postback": {"data": f"care:v1;rid={rid};status=not_yet"},
        "source": {"type": "user", "userId": "Ustranger"},
    }
    await line_adapter._handle_line_event(unauthorized_event)

    responses = [event for event in line_adapter.care_store.list_events() if event["event_type"] == "response"]
    assert len(responses) == 1
    assert responses[0]["subject"] == "dad"
    assert responses[0]["status"] == "done"
    assert line_adapter._reply_with_token.await_count == 1
    pending_records = [json.loads(line) for line in pending_path.read_text().splitlines()]
    assert pending_records[0]["event_type"] == "postback"
    assert "Ustranger" not in json.dumps(line_adapter.care_store.list_events(), ensure_ascii=False)


@pytest.mark.asyncio
async def test_symptom_scale_rich_payload_renders_right_arm_pain_metric_buttons(line_adapter, tmp_path):
    from gateway.platforms.base import SendResult

    line_adapter.care_store = _line_mod.LineCareEventStore(
        db_path=str(tmp_path / "care_events.sqlite"),
        audit_path=str(tmp_path / "care_events.jsonl"),
    )
    sent = []

    async def fake_post_json(url, payload, **kwargs):
        sent.append(payload)
        return SendResult(success=True, message_id="line-message-pain", raw_response={"ok": True})

    line_adapter._post_json = fake_post_json

    result = await line_adapter.send(
        "Uparent",
        'LINE_RICH:{"type":"symptom_scale","altText":"เช็กระดับความปวดแขนขวาคุณแม่ 0–10","title":"🩷 เช็กระดับความปวดแขนขวาคุณแม่","subtitle":"แตะตัวเลขที่ใกล้เคียงที่สุดนะคะ","care":{"subject":"mum","routine_id":"mum_right_arm_pain_morning","routine_type":"symptom_check","slot":"morning","metric":"pain"}}',
    )

    assert result.success
    message = sent[0]["messages"][0]
    assert message["type"] == "flex"
    texts = _flex_text_values(message["contents"])
    assert "🩷 เช็กระดับความปวดแขนขวาคุณแม่" in texts
    assert "🟢 ปวดเล็กน้อย" in texts
    assert "ยังพอทำกิจวัตรได้" in texts
    assert "🚨 ปวดที่สุด" in texts
    assert "ทนไม่ไหว หรือรู้สึกรุนแรงมาก" in texts

    actions = [action for action in _flex_actions(message["contents"]) if action.get("type") == "postback"]
    assert len(actions) == 11
    assert {action.get("label") for action in actions} == {str(i) for i in range(11)}
    assert all("metric=pain" in action["data"] for action in actions)
    assert any("value=0" in action["data"] for action in actions)
    assert any("value=10" in action["data"] for action in actions)
    assert all(action.get("displayText", "").startswith("คุณแม่ปวดแขนขวา ") for action in actions)

    rid = actions[0]["data"].split(";", 2)[1].removeprefix("rid=")
    reminder = line_adapter.care_store.get_reminder(rid)
    assert reminder["subject"] == "mum"
    assert reminder["routine_id"] == "mum_right_arm_pain_morning"
    assert reminder["routine_type"] == "symptom_check"
    metadata = json.loads(reminder["metadata_json"])
    assert metadata["care"]["metric"] == "pain"
    assert metadata["care"]["body_part"] == "right_arm"


@pytest.mark.asyncio
async def test_symptom_scale_metric_postback_logs_value_without_calling_agent(line_adapter, tmp_path):
    from gateway.platforms.base import SendResult

    line_adapter.care_store = _line_mod.LineCareEventStore(
        db_path=str(tmp_path / "care_events.sqlite"),
        audit_path=str(tmp_path / "care_events.jsonl"),
    )
    sent = []

    async def fake_post_json(url, payload, **kwargs):
        sent.append(payload)
        return SendResult(success=True, message_id="line-message-zing", raw_response={"ok": True})

    line_adapter._post_json = fake_post_json
    line_adapter._reply_with_token = AsyncMock(return_value=SendResult(success=True))

    await line_adapter.send(
        "Uparent",
        'LINE_RICH:{"type":"symptom_scale","altText":"เช็กอาการเสียวแปลบแขนขวาคุณแม่ 0–10","title":"⚡ เช็กอาการเสียวแปลบที่แขนขวาคุณแม่","care":{"subject":"mum","routine_id":"mum_right_arm_zing_morning","routine_type":"symptom_check","slot":"morning","metric":"right_arm_zing"}}',
    )
    actions = [action for action in _flex_actions(sent[0]["messages"][0]["contents"]) if action.get("type") == "postback"]
    score_6 = next(action for action in actions if action["label"] == "6")

    await line_adapter._handle_line_event(
        {
            "type": "postback",
            "webhookEventId": "webhook-zing-6",
            "replyToken": "reply-token-zing",
            "postback": {"data": score_6["data"]},
            "source": {"type": "user", "userId": "Uparent"},
        }
    )

    line_adapter.handle_message.assert_not_called()
    responses = [event for event in line_adapter.care_store.list_events() if event["event_type"] == "response"]
    assert len(responses) == 1
    assert responses[0]["subject"] == "mum"
    assert responses[0]["routine_id"] == "mum_right_arm_zing_morning"
    assert responses[0]["status"] == "recorded"
    assert responses[0]["metric"] == "right_arm_zing"
    assert responses[0]["value"] == 6
    assert "Uparent" not in json.dumps(responses, ensure_ascii=False)
    confirmation = line_adapter._reply_with_token.await_args.args[1][0]
    assert "เสียวแปลบ" in confirmation
    assert "6/10" in confirmation


@pytest.mark.asyncio
async def test_symptom_score_enables_next_text_note_capture_without_calling_agent(line_adapter, tmp_path):
    from gateway.platforms.base import SendResult

    line_adapter.care_store = _line_mod.LineCareEventStore(
        db_path=str(tmp_path / "care_events.sqlite"),
        audit_path=str(tmp_path / "care_events.jsonl"),
    )
    sent = []

    async def fake_post_json(url, payload, **kwargs):
        sent.append(payload)
        return SendResult(success=True, message_id="line-message-pain", raw_response={"ok": True})

    line_adapter._post_json = fake_post_json
    line_adapter._reply_with_token = AsyncMock(return_value=SendResult(success=True))

    await line_adapter.send(
        "Uparent",
        'LINE_RICH:{"type":"symptom_scale","altText":"เช็กระดับความปวดแขนขวาคุณแม่ 0–10","title":"🩷 เช็กระดับความปวดแขนขวาคุณแม่","care":{"subject":"mum","routine_id":"mum_right_arm_pain_morning","routine_type":"symptom_check","slot":"morning","metric":"pain"}}',
    )
    actions = [action for action in _flex_actions(sent[0]["messages"][0]["contents"]) if action.get("type") == "postback"]
    score_4 = next(action for action in actions if action["label"] == "4")
    rid = score_4["data"].split(";", 2)[1].removeprefix("rid=")

    await line_adapter._handle_line_event(
        {
            "type": "postback",
            "webhookEventId": "webhook-pain-4",
            "replyToken": "reply-token-pain",
            "postback": {"data": score_4["data"]},
            "source": {"type": "user", "userId": "Uparent"},
        }
    )
    first_confirmation = line_adapter._reply_with_token.await_args.args[1][0]
    assert "พิมพ์" in first_confirmation

    await line_adapter._handle_line_event(
        {
            "type": "message",
            "webhookEventId": "webhook-pain-note",
            "replyToken": "reply-token-note",
            "message": {"type": "text", "id": "msg-pain-note", "text": "ปวดตรงหัวไหล่ตอนยกแขนค่ะ"},
            "source": {"type": "user", "userId": "Uparent"},
        }
    )

    line_adapter.handle_message.assert_not_called()
    note_events = [event for event in line_adapter.care_store.list_events() if event["event_type"] == "manual_note"]
    assert len(note_events) == 1
    note = note_events[0]
    assert note["reminder_id"] == rid
    assert note["subject"] == "mum"
    assert note["routine_id"] == "mum_right_arm_symptom_check_morning"
    assert note["note"] == "ปวดตรงหัวไหล่ตอนยกแขนค่ะ"
    raw = json.loads(note["raw_json"])
    assert raw["kind"] == "line_symptom_note"
    assert raw["linked_metric"] == "pain"
    assert raw["slot"] == "morning"
    assert "Uparent" not in json.dumps(note_events, ensure_ascii=False)
    final_reply = line_adapter._reply_with_token.await_args.args[1][0]
    assert "จดเพิ่ม" in final_reply


@pytest.mark.asyncio
async def test_symptom_score_without_reply_token_still_enables_next_text_note_capture(line_adapter, tmp_path):
    from gateway.platforms.base import SendResult

    line_adapter.care_store = _line_mod.LineCareEventStore(
        db_path=str(tmp_path / "care_events.sqlite"),
        audit_path=str(tmp_path / "care_events.jsonl"),
    )
    sent = []

    async def fake_post_json(url, payload, **kwargs):
        sent.append(payload)
        return SendResult(success=True, message_id="line-message-pain-no-reply", raw_response={"ok": True})

    line_adapter._post_json = fake_post_json
    line_adapter._reply_with_token = AsyncMock(return_value=SendResult(success=True))

    await line_adapter.send(
        "Uparent",
        'LINE_RICH:{"type":"symptom_scale","altText":"เช็กระดับความปวดแขนขวาคุณแม่ 0–10","care":{"subject":"mum","routine_id":"mum_right_arm_pain_morning","routine_type":"symptom_check","slot":"morning","metric":"pain"}}',
    )
    actions = [action for action in _flex_actions(sent[0]["messages"][0]["contents"]) if action.get("type") == "postback"]
    score_6 = next(action for action in actions if action["label"] == "6")

    await line_adapter._handle_line_event(
        {
            "type": "postback",
            "webhookEventId": "webhook-pain-6-no-reply",
            "postback": {"data": score_6["data"]},
            "source": {"type": "user", "userId": "Uparent"},
        }
    )
    line_adapter._reply_with_token.assert_not_called()

    await line_adapter._handle_line_event(
        {
            "type": "message",
            "webhookEventId": "webhook-pain-no-reply-note",
            "replyToken": "reply-token-no-reply-note",
            "message": {"type": "text", "id": "msg-pain-no-reply-note", "text": "ปวดมากขึ้นหลังล้างจานค่ะ"},
            "source": {"type": "user", "userId": "Uparent"},
        }
    )

    line_adapter.handle_message.assert_not_called()
    note_events = [event for event in line_adapter.care_store.list_events() if event["event_type"] == "manual_note"]
    assert len(note_events) == 1
    assert note_events[0]["note"] == "ปวดมากขึ้นหลังล้างจานค่ะ"
    assert json.loads(note_events[0]["raw_json"])["linked_value"] == 6


@pytest.mark.asyncio
async def test_symptom_note_cancel_clears_pending_state_without_note_or_agent(line_adapter, tmp_path):
    from gateway.platforms.base import SendResult

    line_adapter.care_store = _line_mod.LineCareEventStore(
        db_path=str(tmp_path / "care_events.sqlite"),
        audit_path=str(tmp_path / "care_events.jsonl"),
    )
    sent = []

    async def fake_post_json(url, payload, **kwargs):
        sent.append(payload)
        return SendResult(success=True, message_id="line-message-zing", raw_response={"ok": True})

    line_adapter._post_json = fake_post_json
    line_adapter._reply_with_token = AsyncMock(return_value=SendResult(success=True))

    await line_adapter.send(
        "Uparent",
        'LINE_RICH:{"type":"symptom_scale","altText":"เช็กอาการเสียวแปลบแขนขวาคุณแม่ 0–10","care":{"subject":"mum","routine_id":"mum_right_arm_zing_night","routine_type":"symptom_check","slot":"night","metric":"right_arm_zing"}}',
    )
    actions = [action for action in _flex_actions(sent[0]["messages"][0]["contents"]) if action.get("type") == "postback"]
    score_2 = next(action for action in actions if action["label"] == "2")

    await line_adapter._handle_line_event(
        {
            "type": "postback",
            "webhookEventId": "webhook-zing-2",
            "replyToken": "reply-token-zing-2",
            "postback": {"data": score_2["data"]},
            "source": {"type": "user", "userId": "Uparent"},
        }
    )
    await line_adapter._handle_line_event(
        {
            "type": "message",
            "webhookEventId": "webhook-note-cancel",
            "replyToken": "reply-token-cancel",
            "message": {"type": "text", "id": "msg-note-cancel", "text": "ไม่ต้องจด"},
            "source": {"type": "user", "userId": "Uparent"},
        }
    )

    line_adapter.handle_message.assert_not_called()
    events = line_adapter.care_store.list_events()
    assert [event for event in events if event["event_type"] == "manual_note"] == []
    cancellations = [event for event in events if event["event_type"] == "correction"]
    assert len(cancellations) == 1
    assert cancellations[0]["status"] == "skipped"
    assert cancellations[0]["routine_id"] == "mum_right_arm_symptom_check_night"
    cancel_reply = line_adapter._reply_with_token.await_args.args[1][0]
    assert "ไม่จด" in cancel_reply

    await line_adapter._handle_line_event(
        {
            "type": "message",
            "webhookEventId": "webhook-normal-after-cancel",
            "replyToken": "reply-token-normal-after-cancel",
            "message": {"type": "text", "id": "msg-normal-after-cancel", "text": "คุยกับผู้ช่วยตามปกติ"},
            "source": {"type": "user", "userId": "Uparent"},
        }
    )
    line_adapter.handle_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_expired_symptom_note_state_preserves_normal_chat(line_adapter, tmp_path):
    from gateway.platforms.base import SendResult

    line_adapter.care_store = _line_mod.LineCareEventStore(
        db_path=str(tmp_path / "care_events.sqlite"),
        audit_path=str(tmp_path / "care_events.jsonl"),
    )
    sent = []

    async def fake_post_json(url, payload, **kwargs):
        sent.append(payload)
        return SendResult(success=True, message_id="line-message-pain-night", raw_response={"ok": True})

    line_adapter._post_json = fake_post_json
    line_adapter._reply_with_token = AsyncMock(return_value=SendResult(success=True))
    line_adapter.symptom_note_timeout_seconds = 1

    await line_adapter.send(
        "Uparent",
        'LINE_RICH:{"type":"symptom_scale","altText":"เช็กระดับความปวดแขนขวาคุณแม่ 0–10","care":{"subject":"mum","routine_id":"mum_right_arm_pain_night","routine_type":"symptom_check","slot":"night","metric":"pain"}}',
    )
    actions = [action for action in _flex_actions(sent[0]["messages"][0]["contents"]) if action.get("type") == "postback"]
    score_5 = next(action for action in actions if action["label"] == "5")

    await line_adapter._handle_line_event(
        {
            "type": "postback",
            "webhookEventId": "webhook-pain-5-expiring",
            "replyToken": "reply-token-pain-5",
            "postback": {"data": score_5["data"]},
            "source": {"type": "user", "userId": "Uparent"},
        }
    )
    for state in line_adapter._symptom_note_states.values():
        state["expires_at"] = time.time() - 1

    await line_adapter._handle_line_event(
        {
            "type": "message",
            "webhookEventId": "webhook-expired-note-chat",
            "replyToken": "reply-token-expired-note-chat",
            "message": {"type": "text", "id": "msg-expired-note-chat", "text": "ข้อความนี้ควรเข้าแชตปกติ"},
            "source": {"type": "user", "userId": "Uparent"},
        }
    )

    line_adapter.handle_message.assert_awaited_once()
    forwarded = line_adapter.handle_message.await_args.args[0]
    assert forwarded.text == "ข้อความนี้ควรเข้าแชตปกติ"
    assert [event for event in line_adapter.care_store.list_events() if event["event_type"] == "manual_note"] == []


@pytest.mark.asyncio
async def test_text_without_symptom_note_state_preserves_normal_chat(line_adapter, tmp_path):
    line_adapter.care_store = _line_mod.LineCareEventStore(
        db_path=str(tmp_path / "care_events.sqlite"),
        audit_path=str(tmp_path / "care_events.jsonl"),
    )
    line_adapter._reply_with_token = AsyncMock()

    await line_adapter._handle_line_event(
        {
            "type": "message",
            "webhookEventId": "webhook-normal-chat",
            "replyToken": "reply-token-normal-chat",
            "message": {"type": "text", "id": "msg-normal-chat", "text": "วันนี้คุยเรื่องอื่นค่ะ"},
            "source": {"type": "user", "userId": "Uparent"},
        }
    )

    line_adapter.handle_message.assert_awaited_once()
    forwarded = line_adapter.handle_message.await_args.args[0]
    assert forwarded.text == "วันนี้คุยเรื่องอื่นค่ะ"
    line_adapter._reply_with_token.assert_not_called()
    assert line_adapter.care_store.list_events() == []


@pytest.mark.asyncio
async def test_care_not_yet_postback_schedules_one_hour_followup(line_adapter, tmp_path, monkeypatch):
    from gateway.platforms.base import SendResult

    line_adapter.care_store = _line_mod.LineCareEventStore(
        db_path=str(tmp_path / "care_events.sqlite"),
        audit_path=str(tmp_path / "care_events.jsonl"),
    )
    sent = []
    created_jobs = []

    async def fake_post_json(url, payload, **kwargs):
        sent.append(payload)
        return SendResult(success=True, message_id="line-message-mum", raw_response={"ok": True})

    def fake_create_job(**kwargs):
        created_jobs.append(kwargs)
        return {"id": "followup-1", **kwargs}

    import cron.jobs as cron_jobs

    monkeypatch.setattr(cron_jobs, "create_job", fake_create_job)
    line_adapter._post_json = fake_post_json
    line_adapter._reply_with_token = AsyncMock(return_value=SendResult(success=True))

    await line_adapter.send(
        "Uparent",
        'LINE_RICH:{"type":"confirm","altText":"เช็กยาคุณแม่","text":"คุณแม่กินยาตอนเช้าแล้วหรือยังคะ?\\n• หลังอาหารเช้า: Effexor XR 37.5 mg + Lyrica 75 mg","care":{"subject":"mum","routine_id":"mum_morning_meds","routine_type":"medication","slot":"morning"},"actions":[{"label":"กินยาแล้ว","status":"done"},{"label":"เตือนอีกที","status":"not_yet"}]}',
    )
    actions = _actions_from_care_message(sent[0]["messages"][0])
    rid = actions[1]["data"].split(";", 2)[1].removeprefix("rid=")

    await line_adapter._handle_line_event(
        {
            "type": "postback",
            "webhookEventId": "webhook-mum-later-1",
            "replyToken": "reply-token-later",
            "postback": {"data": f"care:v1;rid={rid};status=not_yet"},
            "source": {"type": "user", "userId": "Uparent"},
        }
    )

    assert len(created_jobs) == 1
    job = created_jobs[0]
    assert job["repeat"] == 1
    assert job["deliver"] == "line:Uparent"
    assert job["enabled_toolsets"] == []
    assert job["name"] == "line-care-followup-mum_morning_meds"
    assert "LINE_RICH:" in job["prompt"]
    assert "เตือนอีกที" in job["prompt"]
    assert "LINE_RICH" not in json.dumps(line_adapter.care_store.list_events(), ensure_ascii=False)
    confirmation = line_adapter._reply_with_token.await_args.args[1][0]
    assert "1 ชั่วโมง" in confirmation
    assert "เวลา" in confirmation

