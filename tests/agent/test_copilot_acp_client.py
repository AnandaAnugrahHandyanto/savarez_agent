import httpx

from agent.copilot_acp_client import CopilotACPClient, _coerce_timeout_seconds


def test_coerce_timeout_seconds_prefers_read_timeout():
    timeout = httpx.Timeout(connect=5.0, read=42.0, write=9.0, pool=3.0)

    assert _coerce_timeout_seconds(timeout) == 42.0


def test_chat_completions_stream_returns_chunk_sequence(monkeypatch):
    client = CopilotACPClient(acp_command="copilot", acp_args=["--acp", "--stdio"])

    monkeypatch.setattr(
        client,
        "_run_prompt",
        lambda prompt_text, timeout_seconds: ("OK from stream", None),
    )

    stream = client.chat.completions.create(
        model="gpt-4.1",
        messages=[{"role": "user", "content": "say ok"}],
        stream=True,
        timeout=httpx.Timeout(connect=1.0, read=12.0, write=1.0, pool=1.0),
    )
    chunks = list(stream)

    assert len(chunks) == 2
    assert chunks[0].choices[0].delta.content == "OK from stream"
    assert chunks[0].choices[0].finish_reason == "stop"
    assert chunks[1].choices == []
    assert chunks[1].usage.prompt_tokens == 0


def test_chat_completions_stream_with_tool_calls(monkeypatch):
    client = CopilotACPClient(acp_command="copilot", acp_args=["--acp", "--stdio"])
    tool_response = (
        "I will use the tool. "
        '<tool_call>{"id": "call_1", "type": "function", '
        '"function": {"name": "read_file", '
        '"arguments": "{\\"path\\": \\"/tmp/test.txt\\"}"}}</tool_call>'
    )

    monkeypatch.setattr(
        client,
        "_run_prompt",
        lambda prompt_text, timeout_seconds: (tool_response, None),
    )

    stream = client.chat.completions.create(
        model="gpt-4.1",
        messages=[{"role": "user", "content": "read file"}],
        stream=True,
        timeout=10.0,
    )
    chunks = list(stream)

    assert len(chunks) == 2
    assert chunks[0].choices[0].delta.content == "I will use the tool."
    assert chunks[0].choices[0].finish_reason == "tool_calls"
    assert chunks[0].choices[0].delta.tool_calls is not None
    assert len(chunks[0].choices[0].delta.tool_calls) == 1
    assert chunks[0].choices[0].delta.tool_calls[0].index == 0
    assert chunks[0].choices[0].delta.tool_calls[0].id == "call_1"
    assert chunks[0].choices[0].delta.tool_calls[0].type == "function"
    assert chunks[0].choices[0].delta.tool_calls[0].function.name == "read_file"
    assert chunks[0].choices[0].delta.tool_calls[0].function.arguments == '{"path": "/tmp/test.txt"}'
    assert chunks[1].usage.prompt_tokens == 0