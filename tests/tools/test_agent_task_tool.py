import json
from types import SimpleNamespace

import tools.agent_task_tool as agent_task_tool
from tools.registry import registry
from toolsets import resolve_toolset


def test_agent_task_create_uses_runtime(monkeypatch):
    captured = {}

    def fake_start(**kwargs):
        captured.update(kwargs)
        return {"task_id": "task_1", "status": "pending", "goal": kwargs["goal"]}

    monkeypatch.setattr(agent_task_tool.task_runtime, "start_agent_task", fake_start)
    parent = SimpleNamespace(model="x")

    payload = json.loads(agent_task_tool.agent_task_create({"goal": "audit", "agent": "reviewer"}, parent_agent=parent))

    assert payload["ok"] is True
    assert payload["task"]["task_id"] == "task_1"
    assert captured["goal"] == "audit"
    assert captured["agent"] == "reviewer"
    assert captured["parent_agent"] is parent


def test_agent_task_status_missing_task_returns_error(monkeypatch):
    monkeypatch.setattr(agent_task_tool.task_runtime, "get_task", lambda task_id: None)

    payload = json.loads(agent_task_tool.agent_task_status({"task_id": "missing"}))

    assert "error" in payload


def test_agent_task_diagnostics_summarizes_meta_and_last_event(monkeypatch, tmp_path):
    events_path = tmp_path / "events.jsonl"
    output_path = tmp_path / "output.log"
    result_path = tmp_path / "result.json"
    events_path.write_text(
        '{"ts": 10.0, "event": "started", "data": {"agent": "reviewer"}}\n'
        '{"ts": 17.5, "event": "failed", "data": {"error": "boom"}}\n',
        encoding="utf-8",
    )
    task = {
        "task_id": "task_1",
        "status": "failed",
        "created_at": 9.0,
        "started_at": 10.0,
        "updated_at": 17.5,
        "ended_at": 17.5,
        "artifact_dir": str(tmp_path),
        "events_path": str(events_path),
        "output_path": str(output_path),
        "result_path": str(result_path),
        "runtime": "hermes_default",
        "agent": "reviewer",
        "error": "boom",
    }
    monkeypatch.setattr(agent_task_tool.task_runtime, "get_task", lambda task_id: task)

    payload = json.loads(agent_task_tool.agent_task_diagnostics({"task_id": "task_1"}))

    diagnostics = payload["diagnostics"]
    assert payload["ok"] is True
    assert diagnostics["status"] == "failed"
    assert diagnostics["elapsed_seconds"] == 7.5
    assert diagnostics["last_event"]["event"] == "failed"
    assert diagnostics["paths"]["output_path"] == str(output_path)
    assert diagnostics["paths"]["result_path"] == str(result_path)
    assert diagnostics["runtime"] == "hermes_default"
    assert diagnostics["agent"] == "reviewer"
    assert diagnostics["error"] == "boom"


def test_agent_task_tools_are_registered_and_exposed_by_toolset():
    expected = {
        "agent_task_create",
        "agent_task_status",
        "agent_task_diagnostics",
        "agent_task_output",
        "agent_task_stop",
        "agent_task_list",
    }

    definitions = registry.get_definitions(expected)
    names = {definition["function"]["name"] for definition in definitions}

    assert expected <= names
    assert expected <= set(resolve_toolset("agent_team"))
    assert expected <= set(resolve_toolset("hermes-cli"))



def test_run_agent_dispatch_agent_task_routes_to_tool(monkeypatch):
    from types import SimpleNamespace
    from run_agent import AIAgent

    captured = {}

    def fake_create(args, parent_agent=None):
        captured["args"] = args
        captured["parent_agent"] = parent_agent
        return '{"ok": true}'

    monkeypatch.setattr(agent_task_tool, "agent_task_create", fake_create)
    fake_agent = SimpleNamespace()

    result = AIAgent._dispatch_agent_task(fake_agent, "agent_task_create", {"goal": "audit"})

    assert json.loads(result)["ok"] is True
    assert captured["args"] == {"goal": "audit"}
    assert captured["parent_agent"] is fake_agent


def test_run_agent_dispatch_agent_task_routes_to_diagnostics(monkeypatch):
    from run_agent import AIAgent

    captured = {}

    def fake_diagnostics(args, **_):
        captured["args"] = args
        return '{"ok": true}'

    monkeypatch.setattr(agent_task_tool, "agent_task_diagnostics", fake_diagnostics)
    fake_agent = SimpleNamespace()

    result = AIAgent._dispatch_agent_task(fake_agent, "agent_task_diagnostics", {"task_id": "task_1"})

    assert json.loads(result)["ok"] is True
    assert captured["args"] == {"task_id": "task_1"}


def test_agent_task_create_respects_config_defaults(monkeypatch):
    captured = {}

    def fake_start(**kwargs):
        captured.update(kwargs)
        return {"task_id": "task_cfg", "status": "pending", "goal": kwargs["goal"], "metadata": kwargs.get("metadata")}

    monkeypatch.setattr(agent_task_tool, "_agent_team_config", lambda: {
        "enabled": True,
        "task_timeout_seconds": 123,
        "max_parallel_tasks": 2,
        "artifact_retention_days": 7,
    })
    monkeypatch.setattr(agent_task_tool.task_runtime, "start_agent_task", fake_start)
    parent = SimpleNamespace(session_id="s1", platform="cli")

    payload = json.loads(agent_task_tool.agent_task_create({"goal": "audit"}, parent_agent=parent))

    assert payload["ok"] is True
    assert captured["timeout_seconds"] == 123
    assert captured["max_parallel_tasks"] == 2
    assert captured["retention_days"] == 7
    assert captured["metadata"]["owner_session_id"] == "s1"
    assert captured["metadata"]["owner_platform"] == "cli"


def test_agent_task_create_can_be_disabled_by_config(monkeypatch):
    monkeypatch.setattr(agent_task_tool, "_agent_team_config", lambda: {"enabled": False})

    payload = json.loads(agent_task_tool.agent_task_create({"goal": "audit"}, parent_agent=SimpleNamespace(session_id="s1")))

    assert "error" in payload
    assert "disabled" in payload["error"]


def test_agent_task_status_rejects_other_session(monkeypatch):
    task = {"task_id": "task_1", "status": "completed", "metadata": {"owner_session_id": "owner"}}
    monkeypatch.setattr(agent_task_tool.task_runtime, "get_task", lambda task_id: task)

    payload = json.loads(agent_task_tool.agent_task_status({"task_id": "task_1"}, parent_agent=SimpleNamespace(session_id="other")))

    assert "error" in payload
    assert "not owned" in payload["error"]


def test_agent_task_list_filters_to_current_session(monkeypatch):
    tasks = [
        {"task_id": "owned", "metadata": {"owner_session_id": "s1"}},
        {"task_id": "other", "metadata": {"owner_session_id": "s2"}},
        {"task_id": "legacy", "metadata": {}},
    ]
    monkeypatch.setattr(agent_task_tool.task_runtime, "list_tasks", lambda status=None, limit=20: tasks)

    payload = json.loads(agent_task_tool.agent_task_list({}, parent_agent=SimpleNamespace(session_id="s1")))

    assert [task["task_id"] for task in payload["tasks"]] == ["owned", "legacy"]
