from gateway.run import _slim_gateway_history_for_model


def test_slims_historical_tool_output_without_mutating_transcript():
    long_output = "A" * 10_000
    history = [
        {"role": "user", "content": "fetch this"},
        {
            "role": "assistant",
            "content": "",
            "reasoning": "private reasoning",
            "codex_reasoning_items": [{"type": "reasoning", "encrypted_content": "secret"}],
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "web_extract", "arguments": "{}"},
                }
            ],
        },
        {
            "role": "tool",
            "name": "web_extract",
            "tool_call_id": "call_1",
            "content": long_output,
        },
    ]

    slimmed, stats = _slim_gateway_history_for_model(
        history,
        max_tool_output_chars=1000,
        strip_assistant_reasoning=True,
    )

    assert history[2]["content"] == long_output
    assert slimmed is not history
    assert slimmed[1]["tool_calls"] == history[1]["tool_calls"]
    assert "reasoning" not in slimmed[1]
    assert "codex_reasoning_items" not in slimmed[1]
    assert len(slimmed[2]["content"]) < len(long_output)
    assert "Gateway note: truncated" in slimmed[2]["content"]
    assert slimmed[2]["tool_call_id"] == "call_1"
    assert stats["tool_messages"] == 1
    assert stats["tool_chars_removed"] > 0
    assert stats["assistant_reasoning_fields_removed"] == 2


def test_keeps_short_history_object_when_no_slimming_needed():
    history = [{"role": "tool", "content": "short", "tool_call_id": "call_1"}]

    slimmed, stats = _slim_gateway_history_for_model(
        history,
        max_tool_output_chars=1000,
        strip_assistant_reasoning=False,
    )

    assert slimmed is history
    assert stats["tool_messages"] == 0
    assert stats["assistant_reasoning_fields_removed"] == 0
