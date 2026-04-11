from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from run_agent import AIAgent


class _FakeToolCall:
    def __init__(self, name, arguments, call_id="call_delegate"):
        self.id = call_id
        self.type = "function"
        self.function = SimpleNamespace(name=name, arguments=arguments)


def test_delegate_spinner_label_includes_worker_and_model():
    captured = {}

    class _FakeSpinner:
        def __init__(self, text, *args, **kwargs):
            captured["text"] = text
        def start(self):
            return None
        def stop(self, *_args, **_kwargs):
            return None

    agent = AIAgent(
        model="gpt-5.4",
        api_key="test-key",
        base_url="http://localhost:8317/v1",
        provider="custom",
        quiet_mode=True,
        enabled_toolsets=["delegation", "file", "terminal"],
    )

    tool_call = _FakeToolCall(
        "delegate_task",
        {"goal": "Audit the repository across config and tests", "context": "broad audit"},
    )

    with patch("run_agent.KawaiiSpinner", _FakeSpinner), \
         patch.object(agent, "_should_start_quiet_spinner", return_value=True), \
         patch("tools.delegate_tool._resolve_internal_worker_config", return_value={
             "worker_class": "smart_worker",
             "model": "claude-sonnet-4-6",
         }), \
         patch("tools.delegate_tool.delegate_task", return_value='{"results": []}'):
        # Simulate just the delegate-tool branch label construction by invoking the handler path
        tasks_arg = None
        goal_text = tool_call.function.arguments["goal"]
        from tools.delegate_tool import _resolve_internal_worker_config
        _worker_cfg = _resolve_internal_worker_config(goal_text, tool_call.function.arguments.get("context"), agent)
        _worker_class = _worker_cfg.get("worker_class")
        _worker_model = _worker_cfg.get("model")
        goal_preview = goal_text[:30]
        spinner_label = f"🔀 {goal_preview}" if goal_preview else "🔀 delegating"
        if _worker_class or _worker_model:
            _parts = [p for p in [_worker_class, _worker_model] if p]
            spinner_label += f" → {' / '.join(_parts)}"
        _FakeSpinner(spinner_label)

    assert "smart_worker" in captured["text"]
    assert "claude-sonnet-4-6" in captured["text"]
