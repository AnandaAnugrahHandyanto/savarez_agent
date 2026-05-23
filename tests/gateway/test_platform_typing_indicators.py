import asyncio

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import BasePlatformAdapter, MessageEvent, SendResult
from gateway.session import SessionSource, build_session_key


class CountingTypingAdapter(BasePlatformAdapter):
    def __init__(self, config: PlatformConfig):
        super().__init__(config, Platform.TELEGRAM)
        self.typing_calls = 0
        self.sent_messages = []

    async def connect(self):
        return True

    async def disconnect(self):
        pass

    async def send(self, chat_id, content, reply_to=None, metadata=None):
        self.sent_messages.append((chat_id, content, reply_to, metadata))
        return SendResult(success=True, message_id="sent-1")

    async def send_typing(self, chat_id, metadata=None):
        self.typing_calls += 1

    async def get_chat_info(self, chat_id):
        return {"id": chat_id}


def _run_typing_scenario(extra):
    async def run_scenario():
        adapter = CountingTypingAdapter(PlatformConfig(enabled=True, token="test", extra=extra))

        async def handler(event):
            await asyncio.sleep(0.05)
            return "done"

        adapter.set_message_handler(handler)
        source = SessionSource(platform=Platform.TELEGRAM, chat_id="12345", chat_type="dm")
        event = MessageEvent(text="hello", source=source, message_id="m1")

        await adapter._process_message_background(event, build_session_key(source))

        assert adapter.sent_messages
        return adapter.typing_calls

    return asyncio.run(run_scenario())


def test_platform_extra_can_disable_typing_indicator_loop():
    assert _run_typing_scenario({"typing_indicators": False}) == 0


def test_platform_extra_string_false_can_disable_typing_indicator_loop():
    assert _run_typing_scenario({"typing_indicators": "false"}) == 0
