"""Observer-grade middleware contract tests.

These tests deliberately use a fake observer instead of a real backend. The
goal is to prove a plugin can reconstruct a Hermes turn graph from generic hook
payloads alone, without depending on any specific telemetry backend or private
agent state.
"""

from __future__ import annotations

from collections import defaultdict
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from run_agent import AIAgent


def _make_tool_defs(*names: str) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": f"{name} tool",
                "parameters": {"type": "object", "properties": {}},
            },
        }
        for name in names
    ]


def _mock_tool_call(name: str, arguments: str, call_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=call_id,
        type="function",
        function=SimpleNamespace(name=name, arguments=arguments),
    )


def _mock_response(
    *,
    content: str,
    finish_reason: str,
    tool_calls: list[SimpleNamespace] | None = None,
    usage: dict | None = None,
) -> SimpleNamespace:
    message = SimpleNamespace(content=content, tool_calls=tool_calls or [])
    choice = SimpleNamespace(message=message, finish_reason=finish_reason)
    response = SimpleNamespace(choices=[choice], model="test/model")
    response.usage = SimpleNamespace(**usage) if usage else None
    return response


@pytest.fixture
def agent() -> AIAgent:
    with (
        patch("run_agent.get_tool_definitions", return_value=_make_tool_defs("web_search")),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("run_agent.OpenAI"),
    ):
        test_agent = AIAgent(
            api_key="test-key",
            base_url="https://example.invalid/v1",
            model="test/model",
            provider="test-provider",
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
        )
    test_agent.client = MagicMock()
    test_agent._use_prompt_caching = False
    test_agent.tool_delay = 0
    test_agent.compression_enabled = False
    test_agent.save_trajectories = False
    return test_agent


def test_fake_observer_reconstructs_turn_api_and_tool_graph(agent: AIAgent):
    tool_call = _mock_tool_call("web_search", '{"q":"hermes"}', "call-search-1")
    agent.client.chat.completions.create.side_effect = [
        _mock_response(
            content="",
            finish_reason="tool_calls",
            tool_calls=[tool_call],
            usage={"prompt_tokens": 10, "completion_tokens": 3},
        ),
        _mock_response(
            content="Done",
            finish_reason="stop",
            usage={"prompt_tokens": 12, "completion_tokens": 4},
        ),
    ]

    events: list[tuple[str, dict]] = []

    def record_hook(name: str, **kwargs):
        events.append((name, kwargs))
        return []

    with (
        patch("model_tools.registry.dispatch", return_value='{"results":["ok"]}'),
        patch("hermes_cli.plugins.invoke_hook", side_effect=record_hook),
        patch.object(agent, "_persist_session"),
        patch.object(agent, "_save_trajectory"),
        patch.object(agent, "_cleanup_task_resources"),
    ):
        result = agent.run_conversation("search for hermes")

    assert result["final_response"] == "Done"

    by_name: dict[str, list[dict]] = defaultdict(list)
    for name, payload in events:
        by_name[name].append(payload)

    assert len(by_name["pre_api_request"]) == 2
    assert len(by_name["post_api_request"]) == 2
    assert len(by_name["pre_tool_call"]) == 1
    assert len(by_name["post_tool_call"]) == 1

    turn_id = by_name["pre_api_request"][0]["turn_id"]
    assert turn_id
    observer_payloads = (
        by_name["on_session_start"]
        + by_name["pre_llm_call"]
        + by_name["pre_api_request"]
        + by_name["post_api_request"]
        + by_name["pre_tool_call"]
        + by_name["post_tool_call"]
        + by_name["post_llm_call"]
        + by_name["on_session_end"]
    )
    assert all(
        payload["telemetry_schema_version"] == "hermes.observer.v1"
        for payload in observer_payloads
    )

    api_pairs = {
        pre["api_request_id"]: {
            "pre": pre,
            "post": next(
                post
                for post in by_name["post_api_request"]
                if post["api_request_id"] == pre["api_request_id"]
            ),
        }
        for pre in by_name["pre_api_request"]
    }
    assert len(api_pairs) == 2
    assert all(pair["pre"]["turn_id"] == turn_id for pair in api_pairs.values())
    assert all(pair["post"]["turn_id"] == turn_id for pair in api_pairs.values())
    assert all(pair["pre"]["started_at"] <= pair["post"]["ended_at"] for pair in api_pairs.values())
    assert all("messages" in pair["pre"]["request"]["body"] for pair in api_pairs.values())
    assert all("assistant_message" in pair["post"]["response"] for pair in api_pairs.values())

    tool_event = by_name["post_tool_call"][0]
    first_api_request_id = by_name["pre_api_request"][0]["api_request_id"]
    assert tool_event["turn_id"] == turn_id
    assert tool_event["api_request_id"] == first_api_request_id
    assert tool_event["tool_call_id"] == "call-search-1"
    assert tool_event["status"] == "ok"
    assert tool_event["duration_ms"] >= 0

    reconstructed = {
        "turn_id": turn_id,
        "api_request_ids": list(api_pairs),
        "tool_call_id": tool_event["tool_call_id"],
        "final_response": by_name["post_llm_call"][0]["assistant_response"],
    }
    assert reconstructed == {
        "turn_id": turn_id,
        "api_request_ids": [
            by_name["pre_api_request"][0]["api_request_id"],
            by_name["pre_api_request"][1]["api_request_id"],
        ],
        "tool_call_id": "call-search-1",
        "final_response": "Done",
    }


def test_api_request_error_payload_is_span_grade(agent: AIAgent):
    captured = []

    def record_hook(name: str, **kwargs):
        captured.append((name, kwargs))
        return []

    with (
        patch("hermes_cli.plugins.invoke_hook", side_effect=record_hook),
        patch("run_agent.time.time", return_value=101.25),
    ):
        agent._invoke_api_request_error_hook(
            task_id="task-1",
            turn_id="turn-1",
            api_request_id="turn-1:api:1",
            api_call_count=1,
            api_start_time=100.0,
            api_kwargs={
                "messages": [{"role": "user", "content": "hello"}],
                "api_key": "secret",
            },
            error_type="RateLimitError",
            error_message="rate limited",
            status_code=429,
            retry_count=1,
            max_retries=3,
            retryable=True,
            reason="rate_limit",
        )

    assert len(captured) == 1
    name, payload = captured[0]
    assert name == "api_request_error"
    assert payload["telemetry_schema_version"] == "hermes.observer.v1"
    assert payload["started_at"] == 100.0
    assert payload["ended_at"] == 101.25
    assert payload["api_duration"] == 1.25
    assert payload["api_request_id"] == "turn-1:api:1"
    assert payload["error"] == {"type": "RateLimitError", "message": "rate limited"}
    assert payload["request"]["body"]["api_key"] == "<redacted>"
