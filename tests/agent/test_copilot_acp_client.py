import types

from agent.copilot_acp_client import (
    CopilotACPClient,
    _format_messages_as_prompt,
    _render_message_entry,
)


def test_render_message_entry_preserves_tool_metadata():
    rendered = _render_message_entry(
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "read_file", "arguments": '{"path":"/tmp/x"}'},
                }
            ],
        }
    )
    assert '<message role="assistant">' in rendered
    assert 'tool_calls:' in rendered
    assert 'read_file' in rendered
    assert 'call_1' in rendered

    tool_rendered = _render_message_entry(
        {
            "role": "tool",
            "tool_call_id": "call_1",
            "name": "read_file",
            "content": "file contents",
        }
    )
    assert 'tool_call_id: call_1' in tool_rendered
    assert 'name: read_file' in tool_rendered
    assert 'file contents' in tool_rendered


def test_format_messages_as_prompt_supports_incremental_header():
    prompt = _format_messages_as_prompt(
        [{"role": "user", "content": "novo pedido"}],
        model="claude-sonnet-4.6",
        reasoning_effort="high",
        incremental=True,
    )
    assert 'Hermes requested model hint: claude-sonnet-4.6' in prompt
    assert 'Hermes requested reasoning effort: high' in prompt
    assert 'New conversation items since your last turn:' in prompt
    assert 'Continue the existing ACP session using only the new messages above.' in prompt


def test_create_chat_completion_uses_incremental_prompt_after_prefix_match(monkeypatch):
    client = CopilotACPClient()
    prompts = []

    def fake_run_prompt(self, prompt_text, *, timeout_seconds, model=None, reasoning_effort=None):
        prompts.append(prompt_text)
        self._session_id = 'sess-1'
        self._session_model = model
        return 'ok', ''

    monkeypatch.setattr(CopilotACPClient, '_run_prompt', fake_run_prompt, raising=True)

    first_messages = [
        {"role": "system", "content": "system rules"},
        {"role": "user", "content": "pedido inicial"},
    ]
    second_messages = first_messages + [
        {"role": "assistant", "content": "resposta parcial"},
        {"role": "user", "content": "continua"},
    ]

    client._create_chat_completion(model='claude-sonnet-4.6', messages=first_messages)
    client._create_chat_completion(model='claude-sonnet-4.6', messages=second_messages)

    assert len(prompts) == 2
    assert 'Conversation transcript:' in prompts[0]
    assert 'pedido inicial' in prompts[0]
    assert 'New conversation items since your last turn:' in prompts[1]
    assert 'continua' in prompts[1]
    assert 'pedido inicial' not in prompts[1]


def test_switch_model_uses_acp_protocol_and_is_idempotent(monkeypatch):
    client = CopilotACPClient()
    calls = []

    monkeypatch.setattr(client, '_ensure_session_locked', lambda **kwargs: 'sess-42')

    def fake_request(method, params, *, timeout_seconds, text_parts=None, reasoning_parts=None):
        calls.append((method, params, timeout_seconds))
        return {"ok": True}

    monkeypatch.setattr(client, '_request_locked', fake_request)

    client._switch_model_locked(model='claude-sonnet-4.6', reasoning_effort='high', timeout_seconds=12)
    client._switch_model_locked(model='claude-sonnet-4.6', reasoning_effort='high', timeout_seconds=12)

    assert calls == [
        (
            'session.model.switchTo',
            {'sessionId': 'sess-42', 'modelId': 'claude-sonnet-4.6', 'reasoningEffort': 'high'},
            12,
        )
    ]
    assert client._session_model == 'claude-sonnet-4.6'


def test_create_chat_completion_same_history_is_not_treated_as_incremental(monkeypatch):
    client = CopilotACPClient()
    prompts = []

    def fake_run_prompt(self, prompt_text, *, timeout_seconds, model=None, reasoning_effort=None):
        prompts.append(prompt_text)
        self._session_id = 'sess-1'
        return 'ok', ''

    monkeypatch.setattr(CopilotACPClient, '_run_prompt', fake_run_prompt, raising=True)

    messages = [
        {"role": "system", "content": "system rules"},
        {"role": "user", "content": "pedido inicial"},
    ]

    client._create_chat_completion(model='claude-sonnet-4.6', messages=messages)
    client._create_chat_completion(model='claude-sonnet-4.6', messages=messages)

    assert len(prompts) == 2
    assert 'Conversation transcript:' in prompts[1]
    assert 'New conversation items since your last turn:' not in prompts[1]
