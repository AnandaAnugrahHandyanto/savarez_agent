from gateway.run import (
    _action_stall_attempt,
    _build_action_stall_continuation,
    _looks_like_action_stall,
    _messages_have_tool_activity,
)


def test_detects_direct_turn_action_promise_without_tool_activity():
    response = (
        "I’ll now use the Gmail API to check the inbox for the sent email. "
        "Updating the skill and running it now…"
    )

    assert _looks_like_action_stall(
        "Verify if the email was sent",
        response,
        [{"role": "user", "content": "Verify if the email was sent"}, {"role": "assistant", "content": response}],
    )


def test_does_not_flag_when_tool_activity_exists():
    response = "I’ll now use the Gmail API to check the inbox."

    assert _messages_have_tool_activity([
        {"role": "assistant", "tool_calls": [{"id": "call_1", "function": {"name": "gmail_search"}}]},
    ])
    assert not _looks_like_action_stall(
        "Verify if the email was sent",
        response,
        [{"role": "assistant", "tool_calls": [{"id": "call_1"}]}],
    )


def test_does_not_flag_when_response_contains_concrete_evidence():
    response = "Verified via Gmail API response: status=200, message_id=abc123."

    assert not _looks_like_action_stall(
        "Verify if the email was sent",
        response,
        [{"role": "assistant", "content": response}],
    )


def test_does_not_flag_ordinary_final_answer():
    assert not _looks_like_action_stall(
        "What model are you on currently?",
        "I’m currently on grok-4.3 via xAI.",
        [{"role": "assistant", "content": "I’m currently on grok-4.3 via xAI."}],
    )


def test_corrective_continuation_is_bounded_and_preserves_context():
    continuation = _build_action_stall_continuation(
        user_message="Send them to me via email",
        assistant_response="Sending now…",
        attempt=1,
        max_attempts=2,
    )

    assert _action_stall_attempt(continuation) == 1
    assert "zero tool calls/tool results" in continuation
    assert "Original user message:" in continuation
    assert "Send them to me via email" in continuation
    assert "Previous assistant response:" in continuation
    assert "Sending now" in continuation


def test_corrective_continuation_uses_forward_direction_not_retrospective_scold():
    """The corrective text must direct the model forward (call a tool now)
    rather than re-litigate the prior turn ("Your previous response promised…",
    "Do not claim sent/executed/verified/done…").  Retrospective scolds prime
    defensive prose; tool_choice=required + a forward instruction is the
    mechanically-enforced path.
    """
    continuation = _build_action_stall_continuation(
        user_message="Send them to me via email",
        assistant_response="Sending now…",
        attempt=1,
        max_attempts=2,
    )

    # Retrospective scolds that primed more prose on retry — must be gone.
    assert "Your previous response promised" not in continuation
    assert "Do not claim sent/executed/verified/done" not in continuation
    assert "Do not answer with another status update" not in continuation

    # Forward direction must be present.
    assert "Continue the task" in continuation
