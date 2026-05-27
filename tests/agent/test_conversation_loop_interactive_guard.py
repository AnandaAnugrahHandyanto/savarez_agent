from agent.conversation_loop import _interactive_wall_clock_guard_message


def test_telegram_wall_clock_guard_message_preserves_background_state() -> None:
    message = _interactive_wall_clock_guard_message("telegram")

    assert "Telegram turn hit Hermes' 5-minute interactive safety guard" in message
    assert "Background jobs, if any, were not intentionally stopped" in message
    assert "verify the live state before continuing" in message


def test_non_telegram_wall_clock_guard_message_is_not_misbranded() -> None:
    message = _interactive_wall_clock_guard_message("slack")

    assert message.startswith("This interactive turn hit")
    assert "Telegram" not in message
