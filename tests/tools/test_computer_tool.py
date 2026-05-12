import json
from unittest.mock import MagicMock

import pytest


def test_computer_tool_starts_persistent_run(tmp_path, monkeypatch):
    from computer.runtime import ComputerStore
    import tools.computer_tool as tool

    store = ComputerStore(base_dir=tmp_path / "computer")
    monkeypatch.setattr(tool, "_get_store", lambda: store)
    starter = MagicMock(return_value=True)
    monkeypatch.setattr(tool, "start_computer_run", starter)

    result = json.loads(tool.computer(
        action="start",
        goal="Research Perplexity Computer and build a clone plan",
        features=["runtime", "parallel_research", "continuous_monitoring"],
        start_background=True,
    ))

    assert result["success"] is True
    assert result["run"]["status"] == "queued"
    assert result["run"]["goal"].startswith("Research Perplexity")
    starter.assert_called_once_with(result["run"]["id"], store=store)

    events = store.list_events(result["run"]["id"])
    assert events[0]["type"] == "computer.run.created"


def test_computer_tool_lists_gets_events_and_cancels(tmp_path, monkeypatch):
    from computer.runtime import ComputerStore
    import tools.computer_tool as tool

    store = ComputerStore(base_dir=tmp_path / "computer")
    monkeypatch.setattr(tool, "_get_store", lambda: store)
    run = store.create_run(goal="Organize Downloads", features=["runtime"])
    store.append_event(run["id"], "computer.note", {"message": "hello"})

    listing = json.loads(tool.computer(action="list"))
    assert listing["success"] is True
    assert listing["runs"][0]["id"] == run["id"]

    fetched = json.loads(tool.computer(action="get", run_id=run["id"]))
    assert fetched["run"]["goal"] == "Organize Downloads"

    events = json.loads(tool.computer(action="events", run_id=run["id"]))
    assert [event["type"] for event in events["events"]] == ["computer.run.created", "computer.note"]

    cancelled = json.loads(tool.computer(action="cancel", run_id=run["id"]))
    assert cancelled["success"] is True
    assert cancelled["run"]["status"] == "cancelled"


def test_computer_tool_schedules_monitoring_job(tmp_path, monkeypatch):
    from computer.runtime import ComputerStore
    import tools.computer_tool as tool

    store = ComputerStore(base_dir=tmp_path / "computer")
    monkeypatch.setattr(tool, "_get_store", lambda: store)

    fake_job = {"id": "job123", "name": "AI browser watch", "schedule_display": "0 9 * * *"}
    create_job = MagicMock(return_value=fake_job)
    monkeypatch.setattr(tool, "_cron_create_job", create_job)

    result = json.loads(tool.computer(
        action="schedule",
        goal="Monitor AI browser product updates",
        schedule="0 9 * * *",
        name="AI browser watch",
        deliver="origin",
    ))

    assert result["success"] is True
    assert result["cron_job"] == fake_job
    assert result["run"]["status"] == "scheduled"
    assert result["run"]["schedule_job_id"] == "job123"
    prompt = create_job.call_args.kwargs["prompt"]
    assert result["run"]["id"] in prompt
    assert "Do not recursively create cron jobs" in prompt
    assert create_job.call_args.kwargs["deliver"] == "origin"


def test_computer_tool_rejects_unknown_action(tmp_path, monkeypatch):
    import tools.computer_tool as tool

    result = json.loads(tool.computer(action="explode"))
    assert result["success"] is False
    assert "explode" in result["error"]


def test_computer_tool_start_requires_goal(tmp_path, monkeypatch):
    from computer.runtime import ComputerStore
    import tools.computer_tool as tool

    store = ComputerStore(base_dir=tmp_path / "computer")
    monkeypatch.setattr(tool, "_get_store", lambda: store)

    result = json.loads(tool.computer(action="start"))
    assert result["success"] is False
    assert "goal" in result["error"].lower()


def test_computer_tool_get_returns_error_for_unknown_run(tmp_path, monkeypatch):
    from computer.runtime import ComputerStore
    import tools.computer_tool as tool

    store = ComputerStore(base_dir=tmp_path / "computer")
    monkeypatch.setattr(tool, "_get_store", lambda: store)

    result = json.loads(tool.computer(action="get", run_id="computer_doesnotexist"))
    assert result["success"] is False
    assert "computer_doesnotexist" in result["error"]


class TestComputerToolWiring:
    """The `computer` tool must be reachable via the registry and toolset wiring."""

    def test_in_registry(self):
        from tools import computer_tool  # noqa: F401 — triggers registration
        from tools.registry import registry

        entry = registry.get_entry("computer")
        assert entry is not None
        assert entry.toolset == "computer"

    def test_in_computer_toolset(self):
        from toolsets import TOOLSETS

        assert "computer" in TOOLSETS
        assert "computer" in TOOLSETS["computer"]["tools"]

    def test_in_hermes_core_tools(self):
        from toolsets import _HERMES_CORE_TOOLS

        assert "computer" in _HERMES_CORE_TOOLS

    def test_in_api_server_toolset(self):
        from toolsets import TOOLSETS

        assert "computer" in TOOLSETS["hermes-api-server"]["tools"]

    def test_in_legacy_toolset_map(self):
        from model_tools import _LEGACY_TOOLSET_MAP

        assert _LEGACY_TOOLSET_MAP.get("computer_tools") == ["computer"]
