"""Tests for dynamic workflow orchestration."""

from __future__ import annotations

import json
from types import SimpleNamespace


def test_workflow_run_executes_phases_and_carries_previous_results(monkeypatch, tmp_path):
    from tools import workflow_tool

    calls = []

    def fake_delegate_task(*, tasks, parent_agent=None, **kwargs):
        calls.append({"tasks": tasks, "parent_agent": parent_agent, "kwargs": kwargs})
        return json.dumps(
            {
                "results": [
                    {
                        "task_index": i,
                        "status": "success",
                        "summary": f"summary for {task['goal']}",
                    }
                    for i, task in enumerate(tasks)
                ]
            }
        )

    monkeypatch.setattr(workflow_tool, "delegate_task", fake_delegate_task)
    monkeypatch.setattr(workflow_tool, "get_hermes_home", lambda: tmp_path)

    result = json.loads(
        workflow_tool.workflow_run(
            name="audit",
            context="root context",
            phases=[
                {"name": "first", "context": "phase one context", "tasks": [{"goal": "collect evidence"}]},
                {"name": "second", "tasks": [{"goal": "verify evidence"}]},
            ],
            max_concurrency=2,
            parent_agent=object(),
        )
    )

    assert result["success"] is True
    assert [phase["name"] for phase in result["phases"]] == ["first", "second"]
    assert len(calls) == 2
    assert "root context" in calls[0]["tasks"][0]["context"]
    assert "phase one context" in calls[0]["tasks"][0]["context"]
    assert "summary for collect evidence" in calls[1]["tasks"][0]["context"]
    assert (tmp_path / "workflows" / "runs" / f"{result['run_id']}.json").exists()


def test_workflow_run_chunks_phase_tasks_by_effective_concurrency(monkeypatch, tmp_path):
    from tools import workflow_tool

    batch_sizes = []

    def fake_delegate_task(*, tasks, parent_agent=None, **kwargs):
        batch_sizes.append(len(tasks))
        return json.dumps(
            {
                "results": [
                    {"task_index": i, "status": "success", "summary": task["goal"]}
                    for i, task in enumerate(tasks)
                ]
            }
        )

    monkeypatch.setattr(workflow_tool, "delegate_task", fake_delegate_task)
    monkeypatch.setattr(workflow_tool, "get_hermes_home", lambda: tmp_path)

    result = json.loads(
        workflow_tool.workflow_run(
            name="chunked",
            phases=[{"name": "fanout", "tasks": [{"goal": f"task {i}"} for i in range(5)]}],
            max_concurrency=2,
            parent_agent=object(),
        )
    )

    assert result["success"] is True
    assert batch_sizes == [2, 2, 1]


def test_workflow_run_rejects_too_many_agents(monkeypatch, tmp_path):
    from tools import workflow_tool

    monkeypatch.setattr(workflow_tool, "get_hermes_home", lambda: tmp_path)
    result = json.loads(
        workflow_tool.workflow_run(
            name="too-big",
            phases=[{"name": "fanout", "tasks": [{"goal": str(i)} for i in range(3)]}],
            max_agents_per_run=2,
            parent_agent=object(),
        )
    )

    assert "error" in result
    assert "max_agents_per_run" in result["error"]


def test_workflow_run_rejects_direct_runtime_actions(monkeypatch, tmp_path):
    from tools import workflow_tool

    monkeypatch.setattr(workflow_tool, "get_hermes_home", lambda: tmp_path)
    result = json.loads(
        workflow_tool.workflow_run(
            name="bad",
            phases=[{"name": "bad", "tasks": [{"goal": "x", "shell": "rm -rf /"}]}],
            parent_agent=object(),
        )
    )

    assert "error" in result
    assert "direct runtime action" in result["error"]


def test_agent_runtime_passes_parent_agent_to_workflow_run(monkeypatch):
    from agent.agent_runtime_helpers import invoke_tool
    from tools import workflow_tool

    sentinel_agent = SimpleNamespace(_memory_manager=None, session_id="s", valid_tool_names=set())
    seen = {}

    def fake_workflow_run(**kwargs):
        seen.update(kwargs)
        return json.dumps({"success": True})

    monkeypatch.setattr(workflow_tool, "workflow_run", fake_workflow_run)
    result = json.loads(
        invoke_tool(
            sentinel_agent,
            "workflow_run",
            {
                "name": "audit",
                "phases": [{"name": "p", "tasks": [{"goal": "g"}]}],
                "context": "ctx",
                "max_concurrency": 2,
                "max_agents_per_run": 9,
            },
            "task-id",
        )
    )

    assert result == {"success": True}
    assert seen["parent_agent"] is sentinel_agent
    assert seen["name"] == "audit"


def test_workflow_toolset_is_opt_in():
    import toolsets
    from hermes_cli.tools_config import _DEFAULT_OFF_TOOLSETS
    from model_tools import get_tool_definitions

    assert "workflow_run" in toolsets.TOOLSETS["workflow"]["tools"]
    assert "workflow_run" not in toolsets._HERMES_CORE_TOOLS
    assert "workflow" in _DEFAULT_OFF_TOOLSETS

    core_names = {
        t["function"]["name"]
        for t in get_tool_definitions(enabled_toolsets=["hermes-cli"], quiet_mode=True)
    }
    workflow_names = {
        t["function"]["name"]
        for t in get_tool_definitions(enabled_toolsets=["workflow"], quiet_mode=True)
    }

    assert "workflow_run" not in core_names
    assert workflow_names == {"workflow_run"}
