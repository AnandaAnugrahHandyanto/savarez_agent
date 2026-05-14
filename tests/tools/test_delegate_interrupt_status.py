import json
import threading
import time
from types import SimpleNamespace

from tools import delegate_tool


class _StubParent:
    def __init__(self, interrupted=False):
        self._interrupt_requested = interrupted
        self._delegate_depth = 0
        self._delegate_spinner = None
        self._memory_manager = None
        self.session_id = "parent-session"


class _StubChild:
    def __init__(self, result=None):
        self.result = result or {"completed": True, "final_response": "", "api_calls": 1}
        self.tool_progress_callback = None
        self._delegate_saved_tool_names = []
        self._delegate_role = "leaf"
        self._credential_pool = None
        self.subagent_id = "child-1"
        self.model = "test-model"
        self.session_prompt_tokens = 0
        self.session_completion_tokens = 0
        self.session_reasoning_tokens = 0
        self.session_estimated_cost_usd = 0.0
        self.interrupt_called = False
        self.interrupt_event = threading.Event()

    def run_conversation(self, user_message, task_id=None):
        return self.result

    def get_activity_summary(self):
        return {"api_call_count": self.result.get("api_calls", 0)}

    def interrupt(self):
        self.interrupt_called = True
        self.interrupt_event.set()

    def close(self):
        pass


def test_completed_child_with_empty_response_is_completed(monkeypatch):
    monkeypatch.setattr(delegate_tool, "_get_child_timeout", lambda: 5)
    child = _StubChild({"completed": True, "final_response": "", "api_calls": 1})

    result = delegate_tool._run_single_child(
        task_index=0,
        goal="empty but completed",
        child=child,
        parent_agent=_StubParent(),
    )

    assert result["status"] == "completed"
    assert result["exit_reason"] == "completed"
    assert result["summary"] == ""
    assert "error" not in result


def test_batch_parent_interrupt_signals_pending_children(monkeypatch):
    children = [_StubChild(), _StubChild()]

    monkeypatch.setattr(delegate_tool, "_load_config", lambda: {"max_iterations": 3})
    monkeypatch.setattr(delegate_tool, "_get_max_spawn_depth", lambda: 2)
    monkeypatch.setattr(delegate_tool, "_get_max_concurrent_children", lambda: 3)
    monkeypatch.setattr(
        delegate_tool,
        "_resolve_delegation_credentials",
        lambda cfg, parent: {
            "model": None,
            "provider": None,
            "base_url": None,
            "api_key": None,
            "api_mode": None,
            "command": None,
            "args": None,
        },
    )

    def fake_build_child_agent(task_index, **kwargs):
        return children[task_index]

    def fake_run_single_child(task_index, goal, child, parent_agent):
        child.interrupt_event.wait(timeout=1)
        return {
            "task_index": task_index,
            "status": "interrupted" if child.interrupt_called else "failed",
            "summary": None,
            "api_calls": 0,
            "duration_seconds": 0,
            "_child_role": "leaf",
        }

    monkeypatch.setattr(delegate_tool, "_build_child_agent", fake_build_child_agent)
    monkeypatch.setattr(delegate_tool, "_run_single_child", fake_run_single_child)

    payload = delegate_tool.delegate_task(
        tasks=[{"goal": "a"}, {"goal": "b"}],
        parent_agent=_StubParent(interrupted=True),
    )
    data = json.loads(payload)

    assert [child.interrupt_called for child in children] == [True, True]
    assert [entry["status"] for entry in data["results"]] == ["interrupted", "interrupted"]
