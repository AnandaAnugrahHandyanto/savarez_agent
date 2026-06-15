from gateway.config import GatewayConfig, Platform
from gateway.platforms.base import MessageEvent, MessageType
from gateway.run import GatewayRunner
from gateway.runtime_footer import apply_runtime_prefix, build_prefix_line
from gateway.session import SessionSource


def _event() -> MessageEvent:
    return MessageEvent(
        text="hello",
        message_type=MessageType.TEXT,
        source=SessionSource(
            platform=Platform.DISCORD,
            chat_id="channel-1",
            user_id="user-1",
        ),
    )


def test_runtime_prefix_does_not_make_gateway_errors_voice_eligible():
    runner = GatewayRunner(GatewayConfig())
    event = _event()
    runner._voice_mode[runner._voice_key(Platform.DISCORD, "channel-1")] = "all"

    assert runner._should_send_voice_reply(event, "Error: provider unavailable", []) is False
    custom_prefix = build_prefix_line(
        user_config={
            "display": {
                "runtime_prefix": {
                    "enabled": True,
                    "labels": {"gpt-5.5": "gpt5.5:"},
                }
            }
        },
        platform_key="discord",
        model="openai/gpt-5.5",
    )
    assert custom_prefix == "[gpt5.5:]"
    assert (
        runner._should_send_voice_reply(
            event,
            apply_runtime_prefix("Error: provider unavailable", custom_prefix),
            [],
        )
        is False
    )
    assert runner._should_send_voice_reply(event, "[gpt5.5] normal reply", []) is True
