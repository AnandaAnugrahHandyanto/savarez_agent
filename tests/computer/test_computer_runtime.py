import json
from pathlib import Path


def test_store_creates_persistent_run_and_events(tmp_path):
    from computer.runtime import ComputerStore

    store = ComputerStore(base_dir=tmp_path / "computer")
    run = store.create_run(
        goal="Monitor competitor pricing every weekday",
        features=["runtime", "parallel_research", "continuous_monitoring"],
        source="unit-test",
    )

    assert run["id"].startswith("computer_")
    assert run["goal"] == "Monitor competitor pricing every weekday"
    assert run["status"] == "queued"
    assert run["features"] == ["runtime", "parallel_research", "continuous_monitoring"]
    assert Path(run["artifact_dir"]).name == run["id"]

    store.append_event(run["id"], "computer.plan.created", {"steps": 3})
    store.update_run(run["id"], status="running", plan={"steps": ["research", "synthesize"]})

    reloaded = ComputerStore(base_dir=tmp_path / "computer")
    loaded = reloaded.get_run(run["id"])
    assert loaded["status"] == "running"
    assert loaded["plan"]["steps"] == ["research", "synthesize"]
    assert reloaded.list_runs()[0]["id"] == run["id"]

    events = reloaded.list_events(run["id"])
    assert [event["type"] for event in events] == ["computer.run.created", "computer.plan.created", "computer.run.updated"]


def test_computer_prompt_enforces_requested_feature_ports(tmp_path):
    from computer.runtime import ComputerStore, build_computer_prompt

    store = ComputerStore(base_dir=tmp_path / "computer")
    run = store.create_run(
        goal="Research AI browser changes and produce a briefing",
        features=["runtime", "parallel_research", "continuous_monitoring"],
    )

    prompt = build_computer_prompt(run)

    assert "Perplexity Computer-style" in prompt
    assert "persistent Computer run" in prompt
    assert "delegate_task" in prompt
    assert "parallel" in prompt.lower()
    assert "browser" in prompt.lower()
    assert "continuous monitoring" in prompt.lower()
    assert run["artifact_dir"] in prompt


def test_schedule_prompt_is_self_contained_and_traceable(tmp_path):
    from computer.runtime import ComputerStore, build_scheduled_computer_prompt

    store = ComputerStore(base_dir=tmp_path / "computer")
    run = store.create_run(
        goal="Send me a morning briefing on AI browser products",
        features=["runtime", "parallel_research", "continuous_monitoring"],
    )

    prompt = build_scheduled_computer_prompt(run)

    assert run["id"] in prompt
    assert "fresh session" in prompt.lower()
    assert "continuous monitoring" in prompt.lower()
    assert "deliver" in prompt.lower()
    assert "Do not recursively create cron jobs" in prompt


def test_invalid_status_rejected(tmp_path):
    from computer.runtime import ComputerStore

    store = ComputerStore(base_dir=tmp_path / "computer")
    run = store.create_run(goal="x", features=["runtime"])

    import pytest

    with pytest.raises(ValueError):
        store.update_run(run["id"], status="not-a-real-status")


def test_start_computer_run_marks_failure_when_hermes_missing(tmp_path, monkeypatch):
    from computer.runtime import ComputerStore, start_computer_run

    store = ComputerStore(base_dir=tmp_path / "computer")
    run = store.create_run(goal="x", features=["runtime"])

    # Force shutil.which to return None so the launcher gives up rather than
    # actually spawning a subprocess in CI.
    import shutil

    monkeypatch.setattr(shutil, "which", lambda _name: None)
    launched = start_computer_run(run["id"], store=store, hermes_executable=None)
    assert launched is False

    reloaded = store.get_run(run["id"])
    assert reloaded["status"] == "failed"
    assert "hermes executable" in (reloaded.get("error") or "")
