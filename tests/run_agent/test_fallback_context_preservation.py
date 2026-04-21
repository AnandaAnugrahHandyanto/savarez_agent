import copy
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import run_agent
from run_agent import AIAgent


@pytest.fixture(autouse=True)
def _no_retry_wait(monkeypatch):
    import time as _time

    monkeypatch.setattr(_time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(run_agent, "jittered_backoff", lambda *a, **k: 0.0)


def _patch_agent_bootstrap():
    return patch("run_agent.get_tool_definitions", return_value=[]), patch(
        "run_agent.check_toolset_requirements", return_value={}
    ), patch("run_agent.OpenAI")


def _final_chat_response(text: str = "ok"):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=text, tool_calls=None),
                finish_reason="stop",
            )
        ],
        usage=SimpleNamespace(input_tokens=5, output_tokens=3, total_tokens=8),
        model="fallback-model",
    )


def _invalid_codex_response():
    return SimpleNamespace(
        output=[],
        output_text="",
        usage=SimpleNamespace(input_tokens=1, output_tokens=0, total_tokens=1),
        status="failed",
        incomplete_details=None,
        model="gpt-5-codex",
    )


def _invalid_chat_response():
    return SimpleNamespace(
        choices=[],
        usage=SimpleNamespace(input_tokens=1, output_tokens=0, total_tokens=1),
        model="primary-model",
    )


def _build_codex_agent():
    with _patch_agent_bootstrap()[0], _patch_agent_bootstrap()[1], _patch_agent_bootstrap()[2]:
        agent = AIAgent(
            model="gpt-5-codex",
            provider="openai-codex",
            base_url="https://chatgpt.com/backend-api/codex",
            api_key="codex-token",
            quiet_mode=True,
            max_iterations=4,
            skip_context_files=True,
            skip_memory=True,
            fallback_model={"provider": "openrouter", "model": "openai/gpt-4.1"},
        )
    agent.client = MagicMock()
    agent._cleanup_task_resources = lambda task_id: None
    agent._persist_session = lambda messages, history=None: None
    agent._save_trajectory = lambda messages, user_message, completed: None
    agent._save_session_log = lambda messages: None
    agent._preflight_codex_api_kwargs = lambda kwargs, allow_stream=False: kwargs
    return agent


def _build_claude_agent():
    with _patch_agent_bootstrap()[0], _patch_agent_bootstrap()[1], _patch_agent_bootstrap()[2]:
        agent = AIAgent(
            model="anthropic/claude-sonnet-4",
            provider="openrouter",
            base_url="https://openrouter.ai/api/v1",
            api_key="or-key",
            quiet_mode=True,
            max_iterations=4,
            skip_context_files=True,
            skip_memory=True,
            fallback_model={"provider": "openrouter", "model": "google/gemini-2.5-flash"},
        )
    agent.client = MagicMock()
    agent._cleanup_task_resources = lambda task_id: None
    agent._persist_session = lambda messages, history=None: None
    agent._save_trajectory = lambda messages, user_message, completed: None
    agent._save_session_log = lambda messages: None
    return agent


def test_codex_fallback_rebuilds_api_messages_and_strips_responses_fields(monkeypatch):
    agent = _build_codex_agent()
    recorded_api_messages = []
    responses = [_invalid_codex_response(), _final_chat_response("fallback ok")]

    def fake_build(api_messages):
        recorded_api_messages.append(copy.deepcopy(api_messages))
        return {"messages": copy.deepcopy(api_messages)}

    monkeypatch.setattr(agent, "_build_api_kwargs", fake_build)
    monkeypatch.setattr(agent, "_interruptible_api_call", lambda api_kwargs: responses.pop(0))
    monkeypatch.setattr(agent, "_has_stream_consumers", lambda: False)
    monkeypatch.setattr(
        "agent.auxiliary_client.resolve_provider_client",
        lambda *a, **k: (MagicMock(), "openai/gpt-4.1"),
    )

    history = [
        {"role": "user", "content": "List files in the project."},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_1",
                    "call_id": "call_1",
                    "response_item_id": "fc_1",
                    "type": "function",
                    "function": {"name": "terminal", "arguments": "{}"},
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_1",
            "name": "terminal",
            "content": '{"ok": true}',
        },
    ]

    result = agent.run_conversation("What happened?", conversation_history=history)

    assert result["final_response"] == "fallback ok"
    assert len(recorded_api_messages) == 2

    first_assistant = next(msg for msg in recorded_api_messages[0] if msg.get("role") == "assistant")
    second_assistant = next(msg for msg in recorded_api_messages[1] if msg.get("role") == "assistant")

    assert first_assistant["tool_calls"][0]["call_id"] == "call_1"
    assert first_assistant["tool_calls"][0]["response_item_id"] == "fc_1"
    assert "call_id" not in second_assistant["tool_calls"][0]
    assert "response_item_id" not in second_assistant["tool_calls"][0]
    assert agent.api_mode == "chat_completions"


def test_claude_prompt_cache_wrappers_do_not_leak_into_fallback_requests(monkeypatch):
    agent = _build_claude_agent()
    recorded_api_messages = []
    responses = [_invalid_chat_response(), _final_chat_response("fallback ok")]

    def fake_build(api_messages):
        recorded_api_messages.append(copy.deepcopy(api_messages))
        return {"messages": copy.deepcopy(api_messages)}

    monkeypatch.setattr(agent, "_build_api_kwargs", fake_build)
    monkeypatch.setattr(agent, "_interruptible_api_call", lambda api_kwargs: responses.pop(0))
    monkeypatch.setattr(agent, "_has_stream_consumers", lambda: False)
    monkeypatch.setattr(
        "agent.auxiliary_client.resolve_provider_client",
        lambda *a, **k: (MagicMock(), "google/gemini-2.5-flash"),
    )

    history = [
        {"role": "user", "content": "We are preparing a healthcare landing page."},
        {"role": "assistant", "content": "Understood."},
        {"role": "user", "content": "The tone should feel trustworthy and warm."},
        {"role": "assistant", "content": "Got it."},
    ]

    result = agent.run_conversation("Give me the final copy.", conversation_history=history)

    assert result["final_response"] == "fallback ok"
    assert len(recorded_api_messages) == 2

    first_user_contents = [msg.get("content") for msg in recorded_api_messages[0] if msg.get("role") == "user"]
    second_user_contents = [msg.get("content") for msg in recorded_api_messages[1] if msg.get("role") == "user"]

    assert any(
        isinstance(content, list)
        and content
        and isinstance(content[-1], dict)
        and "cache_control" in content[-1]
        for content in first_user_contents
    )
    assert all(isinstance(content, str) for content in second_user_contents)
    assert agent._use_prompt_caching is False
