from gateway.config import Platform
from gateway.platforms.base import MessageEvent, MessageType
from gateway.session import SessionSource
from gateway.busy_input_policy import load_busy_input_rules, resolve_busy_input_mode


def _event(
    text="hello",
    *,
    platform=Platform.DISCORD,
    user_id="human-1",
    chat_id="deck-thread",
    is_bot=False,
    message_type=MessageType.TEXT,
):
    return MessageEvent(
        text=text,
        message_type=message_type,
        source=SessionSource(
            platform=platform,
            chat_id=chat_id,
            chat_type="thread",
            user_id=user_id,
            is_bot=is_bot,
        ),
    )


def test_no_rules_preserves_global_default_mode():
    assert resolve_busy_input_mode(_event(), "interrupt", []) == "interrupt"
    assert resolve_busy_input_mode(_event(), "queue", []) == "queue"
    assert resolve_busy_input_mode(_event(), "steer", []) == "steer"


def test_bot_rule_can_queue_discord_messages_without_queuing_humans():
    rules = load_busy_input_rules(
        {
            "display": {
                "busy_input_rules": [
                    {"platform": "discord", "is_bot": True, "mode": "queue"},
                ]
            }
        }
    )

    assert resolve_busy_input_mode(_event(is_bot=True, user_id="dispatch-bot"), "interrupt", rules) == "queue"
    assert resolve_busy_input_mode(_event(is_bot=False, user_id="operator"), "interrupt", rules) == "interrupt"


def test_rules_are_generic_and_ordered_for_user_and_prefix_matches():
    rules = load_busy_input_rules(
        {
            "display": {
                "busy_input_rules": [
                    {"platform": "discord", "user_ids": ["operator"], "mode": "steer"},
                    {"platform": "discord", "text_prefixes": ["✅", "📊 **Status"], "mode": "queue"},
                ]
            }
        }
    )

    assert resolve_busy_input_mode(_event("please redirect", user_id="operator"), "interrupt", rules) == "steer"
    assert resolve_busy_input_mode(_event("✅ worker complete", user_id="dispatch-bot"), "interrupt", rules) == "queue"
    assert resolve_busy_input_mode(_event("normal text", user_id="someone-else"), "interrupt", rules) == "interrupt"


def test_rule_filters_cover_chat_ids_message_types_and_invalid_modes_are_ignored():
    rules = load_busy_input_rules(
        {
            "display": {
                "busy_input_rules": [
                    {"platform": "discord", "chat_ids": ["other-thread"], "mode": "queue"},
                    {"platform": "discord", "message_types": ["photo"], "mode": "queue"},
                    {"platform": "discord", "is_bot": True, "mode": "bogus"},
                ]
            }
        }
    )

    assert resolve_busy_input_mode(_event(chat_id="other-thread"), "interrupt", rules) == "queue"
    assert resolve_busy_input_mode(_event(message_type=MessageType.PHOTO), "interrupt", rules) == "queue"
    assert resolve_busy_input_mode(_event(is_bot=True), "interrupt", rules) == "interrupt"


def test_default_mode_is_normalized_to_safe_interrupt():
    assert resolve_busy_input_mode(_event(), "bogus", []) == "interrupt"
