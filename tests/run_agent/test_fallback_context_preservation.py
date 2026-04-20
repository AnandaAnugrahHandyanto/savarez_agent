import copy
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import run_agent


def _make_tool_defs(*names: str) -> list:
    return [
        {
            "type": "function",
            "function": {
                "name": n,
                "description": f"{n} tool",
                "parameters": {"type": "object", "properties": {}},
            },
        }
        for n in names
    ]


def _build_agent(*, fallback_model, model="gpt-5-codex", provider="openai-codex", api_mode="codex_responses", base_url="https://chatgpt.com/backend-api/codex", api_key="codex-token"):
    with (
        patch("run_agent.get_tool_definitions", return_value=_make_tool_defs("terminal")),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("run_agent.OpenAI"),
    ):
        agent = run_agent.AIAgent(
            model=model,
            provider=provider,
            api_mode=api_mode,
            base_url=base_url,
            api_key=api_key,
            fallback_model=fallback_model,
            quiet_mode=True,
            max_iterations=3,
            skip_context_files=True,
            skip_memory=True,
        )
        agent.client = MagicMock()
        agent._cleanup_task_resources = lambda task_id: None
        agent._persist_session = lambda messages, history=None: None
        agent._save_trajectory = lambda messages, user_message, completed: None
        agent._save_session_log = lambda messages: None
        return agent


def _chat_response(text: str):
    msg = SimpleNamespace(content=text, tool_calls=None)
    choice = SimpleNamespace(message=msg, finish_reason="stop")
    return SimpleNamespace(choices=[choice], model="fallback/model", usage=None)


def test_run_conversation_rebuilds_api_messages_after_fallback_switch():
    fallback_client = MagicMock()
    fallback_client.api_key = "fallback-key"
    fallback_client.base_url = "https://api.example.com/v1"

    agent = _build_agent(
        fallback_model={"provider": "custom", "model": "fallback-model", "base_url": "https://api.example.com/v1", "api_key": "fallback-key"}
    )

    requests = []

    def _fake_api_call(api_kwargs):
        requests.append(copy.deepcopy(api_kwargs))
        if len(requests) == 1:
            # Invalid Codex response -> triggers eager fallback path
            return SimpleNamespace(output=[], output_text="", model="gpt-5-codex", status="failed", incomplete_details=None)
        return _chat_response("fallback answer")

    history = [
        {"role": "user", "content": "run terminal"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_pair123|fc_pair123",
                    "call_id": "call_pair123",
                    "response_item_id": "fc_pair123",
                    "type": "function",
                    "function": {"name": "terminal", "arguments": "{}"},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_pair123|fc_pair123", "content": '{"ok":true}'},
    ]

    with patch(
        "agent.auxiliary_client.resolve_provider_client",
        return_value=(fallback_client, "fallback-model"),
    ):
        agent._interruptible_api_call = _fake_api_call
        result = agent.run_conversation("continue", conversation_history=history)

    assert result["final_response"] == "fallback answer"
    assert len(requests) == 2

    first_request = requests[0]
    second_request = requests[1]

    # First request is Codex Responses payload and should preserve Codex-specific IDs.
    function_call = next(item for item in first_request["input"] if item.get("type") == "function_call")
    assert function_call["call_id"] == "call_pair123"

    # Second request is chat-completions payload rebuilt for the fallback provider.
    assert "messages" in second_request
    assistant_with_tool_call = next(
        msg for msg in second_request["messages"]
        if msg.get("role") == "assistant" and msg.get("tool_calls")
    )
    tool_call = assistant_with_tool_call["tool_calls"][0]
    assert "call_id" not in tool_call
    assert "response_item_id" not in tool_call


def test_run_conversation_rebuilds_prompt_cached_messages_after_fallback_switch():
    fallback_client = MagicMock()
    fallback_client.api_key = "fallback-key"
    fallback_client.base_url = "https://api.example.com/v1"

    agent = _build_agent(
        model="anthropic/claude-sonnet-4",
        provider="openrouter",
        api_mode="chat_completions",
        base_url="https://openrouter.ai/api/v1",
        api_key="openrouter-key",
        fallback_model={"provider": "custom", "model": "fallback-model", "base_url": "https://api.example.com/v1", "api_key": "fallback-key"},
    )

    requests = []

    def _fake_api_call(api_kwargs):
        requests.append(copy.deepcopy(api_kwargs))
        if len(requests) == 1:
            return None  # invalid chat-completions response => eager fallback
        return _chat_response("fallback answer")

    with patch(
        "agent.auxiliary_client.resolve_provider_client",
        return_value=(fallback_client, "fallback-model"),
    ):
        agent._interruptible_api_call = _fake_api_call
        result = agent.run_conversation("hello world")

    assert result["final_response"] == "fallback answer"
    assert len(requests) == 2

    first_messages = requests[0]["messages"]
    second_messages = requests[1]["messages"]

    # Primary OpenRouter Claude request gets Anthropic cache-control wrappers.
    first_user = next(msg for msg in first_messages if msg.get("role") == "user")
    assert isinstance(first_user["content"], list)
    assert first_user["content"][-1].get("cache_control") == {"type": "ephemeral"}

    # Fallback request must be rebuilt from canonical messages, not reuse the
    # prompt-cached payload from the failed provider.
    second_user = next(msg for msg in second_messages if msg.get("role") == "user")
    assert second_user["content"] == "hello world"
