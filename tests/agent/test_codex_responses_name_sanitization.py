from agent.codex_responses_adapter import (
    _chat_messages_to_responses_input,
    _preflight_codex_api_kwargs,
)


def test_replayed_function_call_names_are_sanitized_for_codex_responses():
    messages = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_abc123",
                    "function": {
                        "name": "multi_tool_use.parallel",
                        "arguments": "{}",
                    },
                }
            ],
        }
    ]

    items = _chat_messages_to_responses_input(messages)

    assert items == [
        {
            "type": "function_call",
            "call_id": "call_abc123",
            "name": "multi_tool_use_parallel",
            "arguments": "{}",
        }
    ]


def test_preflight_sanitizes_historical_function_call_names():
    kwargs = {
        "model": "gpt-5.5",
        "instructions": "You are helpful.",
        "input": [
            {
                "type": "function_call",
                "call_id": "call_abc123",
                "name": "multi_tool_use.parallel",
                "arguments": "{}",
            }
        ],
    }

    normalized = _preflight_codex_api_kwargs(kwargs)

    assert normalized["input"][0]["name"] == "multi_tool_use_parallel"
