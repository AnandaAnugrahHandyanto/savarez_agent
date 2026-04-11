import json
from types import SimpleNamespace
from unittest.mock import patch

from run_agent import AIAgent


class _FakeToolCall:
    def __init__(self, name, arguments, call_id="call_delegate"):
        self.id = call_id
        self.type = "function"
        self.function = SimpleNamespace(name=name, arguments=json.dumps(arguments))


class _FakeResponse:
    def __init__(self, message, finish_reason="tool_calls"):
        self.choices = [SimpleNamespace(message=message, finish_reason=finish_reason)]
        self.usage = None


def _assistant_with_tool_call():
    tool_call = _FakeToolCall(
        "delegate_task",
        {"goal": "Rename this button label", "context": "single direct task"},
    )
    message = SimpleNamespace(content=None, tool_calls=[tool_call], reasoning_content=None, reasoning=None)
    return _FakeResponse(message, finish_reason="tool_calls")


def _assistant_final(text):
    message = SimpleNamespace(content=text, tool_calls=None, reasoning_content=None, reasoning=None)
    return _FakeResponse(message, finish_reason="stop")


def test_declined_delegate_is_rewritten_to_continue_directly():
    agent = AIAgent(
        model="gpt-5.4",
        api_key="test-key",
        base_url="http://localhost:8317/v1",
        provider="custom",
        quiet_mode=True,
        enabled_toolsets=["delegation", "file", "terminal"],
    )

    responses = [_assistant_with_tool_call(), _assistant_final("Handled directly after delegation decline.")]

    def fake_api_call(api_kwargs, **_kwargs):
        return responses.pop(0)

    declined_payload = json.dumps({
        "results": [{
            "task_index": 0,
            "status": "declined",
            "summary": None,
            "compact_summary": {
                "status": "declined",
                "answer": "Delegation declined for this task because direct execution is likely cheaper and clearer.",
                "evidence": "None",
                "changed_paths_or_artifacts": "None",
                "risks_unresolved": "None",
                "recommended_next_step": "Use direct tools",
            },
            "worker_class": "fast_worker",
            "resolved_lane": {"model": "gemini-3-flash-preview", "provider": "custom"},
            "delegation_score": 0,
            "delegation_reasons": ["small_direct_task"],
            "delegation_decision": "declined_low_leverage",
            "api_calls": 0,
            "duration_seconds": 0,
        }],
        "total_duration_seconds": 0,
    })

    with patch.object(agent, "_interruptible_api_call", side_effect=fake_api_call), \
         patch.object(agent, "_interruptible_streaming_api_call", side_effect=fake_api_call), \
         patch("tools.delegate_tool.delegate_task", return_value=declined_payload), \
         patch.object(agent, "_save_session_log", lambda messages: None):
        result = agent.run_conversation("Rename this button label")

    assert result["final_response"] == "Handled directly after delegation decline."
    tool_msgs = [m for m in result["messages"] if isinstance(m, dict) and m.get("role") == "tool"]
    assert tool_msgs, "expected tool messages in transcript"
    rewritten = json.loads(tool_msgs[0]["content"])
    assert rewritten["delegation_decision"] == "declined_low_leverage"
    assert rewritten["next_action"] == "continue_directly"
    assert rewritten["status"] == "info"
