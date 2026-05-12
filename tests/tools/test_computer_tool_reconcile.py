"""Tool-level reconciliation: list / get / events must surface fresh state.

When a background hermes process has died but nothing flipped its run
record to ``failed``, the next time the agent reads the run via the
computer tool we should reconcile it before returning so the model never
sees a phantom ``running`` status.
"""

from __future__ import annotations

import json


def _seed_stale_running_run(tmp_path, monkeypatch):
    """Create a store + tool wired to a stale running run with a dead pid."""
    from computer.runtime import ComputerStore
    import computer.runtime as runtime_mod
    import tools.computer_tool as tool

    store = ComputerStore(base_dir=tmp_path / "computer")
    monkeypatch.setattr(tool, "_get_store", lambda: store)
    monkeypatch.setattr(runtime_mod, "_is_pid_alive", lambda pid: False)

    run = store.create_run(goal="stale-tool-read", features=["runtime"])
    store.update_run(
        run["id"],
        status="running",
        background={"pid": 4242424, "binary": "/fake/hermes"},
    )
    return store, run


def test_tool_list_reconciles_stale_running(tmp_path, monkeypatch):
    import tools.computer_tool as tool

    store, run = _seed_stale_running_run(tmp_path, monkeypatch)
    raw = tool.computer(action="list")
    result = json.loads(raw)

    assert result["success"] is True
    statuses = {r["id"]: r["status"] for r in result["runs"]}
    assert statuses[run["id"]] == "failed", result


def test_tool_get_reconciles_stale_running(tmp_path, monkeypatch):
    import tools.computer_tool as tool

    store, run = _seed_stale_running_run(tmp_path, monkeypatch)
    result = json.loads(tool.computer(action="get", run_id=run["id"]))

    assert result["success"] is True
    assert result["run"]["status"] == "failed"


def test_tool_events_reconciles_stale_running(tmp_path, monkeypatch):
    import tools.computer_tool as tool

    store, run = _seed_stale_running_run(tmp_path, monkeypatch)
    result = json.loads(tool.computer(action="events", run_id=run["id"]))

    assert result["success"] is True
    event_types = [event["type"] for event in result["events"]]
    assert "computer.background.reconciled_stale" in event_types

    # And the underlying run is now failed (so a follow-up get is consistent).
    reloaded = store.get_run(run["id"])
    assert reloaded["status"] == "failed"
