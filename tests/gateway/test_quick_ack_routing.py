from types import SimpleNamespace

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import BasePlatformAdapter
from gateway.run import _extend_history_with_visible_assistant_text, _should_send_quick_ack


class _NoEditAdapter(BasePlatformAdapter):
    async def connect(self):
        return True

    async def disconnect(self):
        return None

    async def send(self, chat_id: str, content: str, reply_to=None, metadata=None):
        return SimpleNamespace(success=True, message_id="msg")

    async def get_chat_info(self, chat_id: str):
        return {"name": chat_id, "type": "dm"}


class _EditAdapter(_NoEditAdapter):
    async def edit_message(self, chat_id: str, message_id: str, content: str):
        return SimpleNamespace(success=True, message_id=message_id)


ROUTING_CFG = {
    "enabled": True,
    "max_simple_chars": 160,
    "max_simple_words": 28,
    "cheap_model": {
        "provider": "openai-codex",
        "model": "gpt-5.4-mini",
    },
}


def test_non_editable_platform_skips_ack_for_fast_path():
    adapter = _NoEditAdapter(config=PlatformConfig(enabled=True), platform=Platform.BLUEBUBBLES)
    assert _should_send_quick_ack(adapter, "turn off the lights", ROUTING_CFG) is False


def test_non_editable_platform_keeps_ack_for_deeper_short_message():
    adapter = _NoEditAdapter(config=PlatformConfig(enabled=True), platform=Platform.BLUEBUBBLES)
    assert _should_send_quick_ack(adapter, "Should I text Mackenzie now?", ROUTING_CFG) is True


def test_editable_platform_never_uses_quick_ack():
    adapter = _EditAdapter(config=PlatformConfig(enabled=True), platform=Platform.TELEGRAM)
    assert _should_send_quick_ack(adapter, "turn off the lights", ROUTING_CFG) is False


def test_visible_assistant_text_is_appended_to_history():
    history = [{"role": "user", "content": "hello"}]
    extended = _extend_history_with_visible_assistant_text(history, "On it")
    assert extended[-1] == {"role": "assistant", "content": "On it"}
    assert history == [{"role": "user", "content": "hello"}]
