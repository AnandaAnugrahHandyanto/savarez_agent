import sys
import time

import pytest

from agent import task_runtime
from agent.task_runners import (
    CodexTaskRunner,
    CodexTaskRunnerUnavailable,
    DelegateTaskRunner,
    select_task_runner,
)


def test_select_task_runner_defaults_to_delegate():
    runner = select_task_runner({"runtime": "hermes_default", "agent": "researcher"})

    assert isinstance(runner, DelegateTaskRunner)


def test_select_task_runner_uses_codex_for_codex_app_server_runtime():
    runner = select_task_runner({"runtime": "codex_app_server", "agent": "researcher"})

    assert isinstance(runner, CodexTaskRunner)


def test_select_task_runner_uses_codex_for_coder_agent():
    runner = select_task_runner({"runtime": "hermes_default", "agent": "coder"})

    assert isinstance(runner, CodexTaskRunner)


def test_codex_runner_stub_does_not_call_delegate_or_parent_agent(tmp_path, monkeypatch):
    store = task_runtime.TaskStore(root=tmp_path / "tasks")
    meta = store.create_task(goal="edit code", agent="coder", runtime="codex_app_server")
    runner = CodexTaskRunner()

    class ParentAgent:
        def __getattribute__(self, name):
            if name.startswith("__"):
                return object.__getattribute__(self, name)
            raise AssertionError(f"Codex stub must not access parent_agent.{name}")

    monkeypatch.setitem(sys.modules, "tools.delegate_tool", None)

    with pytest.raises(CodexTaskRunnerUnavailable) as excinfo:
        runner(meta, task_runtime.threading.Event(), ParentAgent(), store)

    assert "not safely wired" in str(excinfo.value)
    assert "did not execute" in str(excinfo.value)
    assert "does not expose Hermes loop tools" in store.read_output(meta["task_id"])


def test_task_runtime_routes_codex_app_server_to_explicit_stub_failure(tmp_path):
    store = task_runtime.TaskStore(root=tmp_path / "tasks")
    meta = task_runtime.start_agent_task(goal="edit code", runtime="codex_app_server", store=store)
    deadline = time.time() + 2

    while time.time() < deadline:
        final = store.get_task(meta["task_id"])
        if final and final["status"] == "failed":
            break
        time.sleep(0.01)

    final = store.get_task(meta["task_id"])
    assert final["status"] == "failed"
    assert "Codex task runner selected" in final["error"]
    assert "not safely wired" in final["error"]
    assert "agent_task_create requires a parent agent" not in final["error"]


def test_delegate_runner_uses_parent_lock(monkeypatch, tmp_path):
    store = task_runtime.TaskStore(root=tmp_path / "tasks")
    meta = store.create_task(goal="delegate")
    calls = []

    def fake_locked(parent_agent, **kwargs):
        calls.append((parent_agent, kwargs))
        return '{"summary": "done"}'

    monkeypatch.setattr("agent.task_runners.run_delegate_task_with_parent_lock", fake_locked)
    parent = object()

    result = DelegateTaskRunner()(meta, task_runtime.threading.Event(), parent, store)

    assert result["delegate_task"]["summary"] == "done"
    assert calls[0][0] is parent
    assert calls[0][1]["goal"] == "delegate"
