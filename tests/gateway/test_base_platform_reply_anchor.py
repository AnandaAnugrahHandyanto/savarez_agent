from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import BasePlatformAdapter, MessageEvent, SendResult, _reply_anchor_for_event
from gateway.session import SessionSource


class _StubAdapter(BasePlatformAdapter):
    async def connect(self) -> bool:
        return True

    async def disconnect(self) -> None:
        self._mark_disconnected()

    async def send(self, chat_id, content, reply_to=None, metadata=None):
        return SendResult(success=True, message_id="m1")

    async def get_chat_info(self, chat_id: str):
        return {}


def _make_event(*, platform: Platform, message_id: str, thread_id: str | None = None, reply_to_message_id: str | None = None) -> MessageEvent:
    return MessageEvent(
        text="hello",
        source=SessionSource(
            platform=platform,
            chat_id="chat-1",
            user_id="user-1",
            thread_id=thread_id,
        ),
        message_id=message_id,
        reply_to_message_id=reply_to_message_id,
    )


def test_reply_anchor_uses_mattermost_thread_root():
    event = _make_event(
        platform=Platform.MATTERMOST,
        message_id="post-123",
        thread_id="root-456",
    )

    assert _reply_anchor_for_event(event) == "root-456"


def test_reply_anchor_preserves_feishu_reply_to_message_id():
    event = _make_event(
        platform=Platform.FEISHU,
        message_id="msg-123",
        thread_id="thread-456",
        reply_to_message_id="reply-789",
    )

    assert _reply_anchor_for_event(event) == "reply-789"


def test_reply_anchor_falls_back_to_message_id_for_other_platforms():
    event = _make_event(
        platform=Platform.TELEGRAM,
        message_id="msg-123",
        thread_id="topic-456",
    )

    assert _reply_anchor_for_event(event) == "msg-123"
