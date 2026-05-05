"""Tests for verifier-gated finish tool integration."""

from __future__ import annotations

import uuid
import json
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


@pytest.fixture()
def finish_agent():
    with (
        patch(
            "run_agent.get_tool_definitions",
            return_value=_make_tool_defs("finish", "web_search"),
        ),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("run_agent.OpenAI"),
    ):
        agent = AIAgent(
            api_key="test-key-1234567890",
            base_url="https://openrouter.ai/api/v1",
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
            require_finish_tool=True,
            max_verifier_rejects=2,
        )
        agent.client = MagicMock()
        agent._cached_system_prompt = "You are helpful."
        agent._use_prompt_caching = False
        agent.tool_delay = 0
        agent.compression_enabled = False
        agent.save_trajectories = False
        return agent


def _mock_tool_call(name: str = "finish", arguments: str = "{}", call_id: str | None = None):
    return SimpleNamespace(
        id=call_id or f"call_{uuid.uuid4().hex[:8]}",
        type="function",
        function=SimpleNamespace(name=name, arguments=arguments),
    )


def _mock_response(content: str = "", finish_reason: str = "stop", tool_calls=None):
    msg = SimpleNamespace(content=content, tool_calls=tool_calls or [])
    choice = SimpleNamespace(message=msg, finish_reason=finish_reason)
    return SimpleNamespace(choices=[choice], model="test/model", usage=None)


def _finish_response(
    *,
    status: str = "done",
    summary: str = "Task completed",
    evidence: list[str] | None = None,
    call_id: str = "finish_1",
):
    evidence = evidence if evidence is not None else ["proof"]
    return _mock_response(
        finish_reason="tool_calls",
        tool_calls=[
            _mock_tool_call(
                arguments=json.dumps(
                    {"status": status, "summary": summary, "evidence": evidence}
                ),
                call_id=call_id,
            )
        ],
    )


def test_init_does_not_reference_missing_kwargs(finish_agent):
    assert finish_agent._max_verifier_rejects == 2
    assert finish_agent._pending_finish_payload is None


def test_finish_tool_triggers_verifier_and_completes(finish_agent):
    finish_agent._interruptible_api_call = lambda api_kwargs: _finish_response(
        summary="Task completed",
        evidence=["tests passed"],
    )
    verifier_result = {
        "status": "done",
        "reason": "Evidence sufficient",
        "missing": [],
        "next_prompt": "",
    }

    with (
        patch.object(finish_agent, "_run_verifier", return_value=verifier_result) as verifier,
        patch.object(finish_agent, "_persist_session"),
        patch.object(finish_agent, "_save_trajectory"),
        patch.object(finish_agent, "_cleanup_task_resources"),
    ):
        result = finish_agent.run_conversation("do something")

    assert result["completed"] is True
    assert result["final_response"] == "Task completed"
    verifier.assert_called_once()


def test_verifier_retries_without_json_mode_when_provider_rejects_it(finish_agent):
    finish_agent._interruptible_api_call = lambda api_kwargs: _finish_response(
        summary="Task completed",
        evidence=["tests passed"],
    )
    finish_agent.client.chat.completions.create.side_effect = [
        RuntimeError("response_format unsupported"),
        _mock_response(
            content=json.dumps(
                {
                    "status": "done",
                    "reason": "Evidence sufficient",
                    "missing": [],
                    "next_prompt": "",
                }
            )
        ),
    ]

    with (
        patch.object(finish_agent, "_persist_session"),
        patch.object(finish_agent, "_save_trajectory"),
        patch.object(finish_agent, "_cleanup_task_resources"),
    ):
        result = finish_agent.run_conversation("do something")

    assert result["completed"] is True
    assert result["final_response"] == "Task completed"
    assert finish_agent.client.chat.completions.create.call_count == 2
    first_kwargs = finish_agent.client.chat.completions.create.call_args_list[0].kwargs
    second_kwargs = finish_agent.client.chat.completions.create.call_args_list[1].kwargs
    assert first_kwargs["response_format"] == {"type": "json_object"}
    assert "response_format" not in second_kwargs


def test_verifier_infrastructure_failure_accepts_finish_payload(finish_agent):
    finish_agent._interruptible_api_call = lambda api_kwargs: _finish_response(
        summary="Task completed despite verifier outage",
        evidence=["tests passed"],
    )
    finish_agent.client.chat.completions.create.side_effect = RuntimeError(
        "verifier provider unavailable"
    )

    with (
        patch.object(finish_agent, "_persist_session"),
        patch.object(finish_agent, "_save_trajectory"),
        patch.object(finish_agent, "_cleanup_task_resources"),
    ):
        result = finish_agent.run_conversation("do something")

    assert result["completed"] is True
    assert result["final_response"] == "Task completed despite verifier outage"


def test_verifier_bad_json_accepts_finish_payload(finish_agent):
    finish_agent._interruptible_api_call = lambda api_kwargs: _finish_response(
        summary="Task completed with malformed verifier response",
        evidence=["tests passed"],
    )
    finish_agent.client.chat.completions.create.return_value = _mock_response(
        content="not json"
    )

    with (
        patch.object(finish_agent, "_persist_session"),
        patch.object(finish_agent, "_save_trajectory"),
        patch.object(finish_agent, "_cleanup_task_resources"),
    ):
        result = finish_agent.run_conversation("do something")

    assert result["completed"] is True
    assert result["final_response"] == "Task completed with malformed verifier response"


def test_verifier_reject_continues_loop_until_finish_approved(finish_agent):
    responses = iter(
        [
            _finish_response(summary="Done", evidence=[], call_id="finish_1"),
            _finish_response(summary="Really done", evidence=["proof"], call_id="finish_2"),
        ]
    )
    finish_agent._interruptible_api_call = lambda api_kwargs: next(responses)
    verifier_results = [
        {
            "status": "continue",
            "reason": "Missing evidence",
            "missing": ["proof of completion"],
            "next_prompt": "Provide evidence",
        },
        {
            "status": "done",
            "reason": "Evidence sufficient",
            "missing": [],
            "next_prompt": "",
        },
    ]

    with (
        patch.object(finish_agent, "_run_verifier", side_effect=verifier_results) as verifier,
        patch.object(finish_agent, "_persist_session"),
        patch.object(finish_agent, "_save_trajectory"),
        patch.object(finish_agent, "_cleanup_task_resources"),
    ):
        result = finish_agent.run_conversation("do something")

    assert result["completed"] is True
    assert result["final_response"] == "Really done"
    assert verifier.call_count == 2


def test_verifier_reject_budget_exhaustion_blocks(finish_agent):
    responses = iter(
        [
            _finish_response(summary="Done", evidence=[], call_id="finish_1"),
            _finish_response(summary="Done again", evidence=[], call_id="finish_2"),
        ]
    )
    finish_agent._interruptible_api_call = lambda api_kwargs: next(responses)
    verifier_result = {
        "status": "continue",
        "reason": "Missing evidence",
        "missing": ["proof"],
        "next_prompt": "Provide evidence",
    }

    with (
        patch.object(finish_agent, "_run_verifier", return_value=verifier_result),
        patch.object(finish_agent, "_persist_session"),
        patch.object(finish_agent, "_save_trajectory"),
        patch.object(finish_agent, "_cleanup_task_resources"),
    ):
        result = finish_agent.run_conversation("do something")

    assert result["completed"] is True
    assert "verifier reject budget exhausted" in result["final_response"]


def test_content_only_response_requires_finish_when_enabled(finish_agent):
    responses = iter(
        [
            _mock_response(content="I think the answer is 42.", finish_reason="stop"),
            _finish_response(summary="Answer is 42", evidence=["calculated"]),
        ]
    )
    finish_agent._interruptible_api_call = lambda api_kwargs: next(responses)
    verifier_result = {
        "status": "done",
        "reason": "Evidence sufficient",
        "missing": [],
        "next_prompt": "",
    }

    with (
        patch.object(finish_agent, "_run_verifier", return_value=verifier_result),
        patch.object(finish_agent, "_persist_session"),
        patch.object(finish_agent, "_save_trajectory"),
        patch.object(finish_agent, "_cleanup_task_resources"),
    ):
        result = finish_agent.run_conversation("what is the answer")

    assert result["completed"] is True
    assert result["api_calls"] == 2
    assert result["final_response"] == "Answer is 42"


def test_finish_tool_blocked_status_terminates_when_verified(finish_agent):
    finish_agent._interruptible_api_call = lambda api_kwargs: _finish_response(
        status="blocked",
        summary="Need user input",
        evidence=["missing credential"],
    )
    verifier_result = {
        "status": "blocked",
        "reason": "Need user input",
        "missing": [],
        "next_prompt": "",
    }

    with (
        patch.object(finish_agent, "_run_verifier", return_value=verifier_result),
        patch.object(finish_agent, "_persist_session"),
        patch.object(finish_agent, "_save_trajectory"),
        patch.object(finish_agent, "_cleanup_task_resources"),
    ):
        result = finish_agent.run_conversation("do something")

    assert result["completed"] is True
    assert result["final_response"] == "Task blocked: Need user input"
