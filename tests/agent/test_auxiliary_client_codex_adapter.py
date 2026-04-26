from types import SimpleNamespace

from agent.auxiliary_client import _CodexCompletionsAdapter


class _FakeResponsesStream:
    def __init__(self, final_response):
        self._final_response = final_response

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def __iter__(self):
        return iter(())

    def get_final_response(self):
        return self._final_response


def _final_message_response(text: str = "memory flush ok"):
    return SimpleNamespace(
        output=[
            SimpleNamespace(
                type="message",
                content=[SimpleNamespace(type="output_text", text=text)],
            )
        ],
        usage=SimpleNamespace(input_tokens=5, output_tokens=3, total_tokens=8),
    )


def test_codex_auxiliary_adapter_converts_tool_history_for_responses_input():
    captured = {}

    class _ResponsesAPI:
        def stream(self, **kwargs):
            captured.update(kwargs)
            return _FakeResponsesStream(_final_message_response())

    client = SimpleNamespace(responses=_ResponsesAPI())
    adapter = _CodexCompletionsAdapter(client, "gpt-5.2-codex")

    response = adapter.create(
        model="gpt-5.2-codex",
        messages=[
            {"role": "system", "content": "You are a memory flusher."},
            {"role": "user", "content": "Summarize what happened."},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_search_1",
                        "call_id": "call_search_1",
                        "type": "function",
                        "function": {
                            "name": "web_search",
                            "arguments": '{"query":"hermes auxiliary memory flush"}',
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_search_1",
                "content": "Found the relevant transcript entries.",
            },
            {"role": "user", "content": "Now flush the memory."},
        ],
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "store_memory",
                    "description": "Persist a memory entry.",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ],
    )

    assert response.choices[0].message.content == "memory flush ok"
    assert captured["instructions"] == "You are a memory flusher."
    assert captured["tools"] == [
        {
            "type": "function",
            "name": "store_memory",
            "description": "Persist a memory entry.",
            "parameters": {"type": "object", "properties": {}},
        }
    ]

    input_items = captured["input"]
    assert any(
        item.get("type") == "function_call"
        and item.get("call_id") == "call_search_1"
        and item.get("name") == "web_search"
        for item in input_items
    )
    assert any(
        item.get("type") == "function_call_output"
        and item.get("call_id") == "call_search_1"
        and item.get("output") == "Found the relevant transcript entries."
        for item in input_items
    )
    assert not any(item.get("role") == "tool" for item in input_items)
