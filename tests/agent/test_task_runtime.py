import time

import pytest

from agent import task_runtime


def test_task_runtime_completes_and_persists_output(tmp_path):
    store = task_runtime.TaskStore(root=tmp_path / "tasks")

    def runner(meta, stop_event, parent_agent, store):
        store.append_output(meta["task_id"], "hello from child")
        return {"ok": True, "task_id": meta["task_id"]}

    meta = task_runtime.start_agent_task(goal="do work", agent="researcher", store=store, runner=runner)
    final = task_runtime.wait_for_task(meta["task_id"], timeout_seconds=2, store=store)

    assert final["status"] == "completed"
    payload = task_runtime.read_task_output(meta["task_id"], store=store)
    assert "hello from child" in payload["output"]
    assert payload["result"]["ok"] is True


def test_task_runtime_stop_marks_active_task(tmp_path):
    store = task_runtime.TaskStore(root=tmp_path / "tasks")

    def runner(meta, stop_event, parent_agent, store):
        deadline = time.time() + 2
        while time.time() < deadline and not stop_event.is_set():
            time.sleep(0.01)
        return {"stopped": stop_event.is_set()}

    meta = task_runtime.start_agent_task(goal="wait", store=store, runner=runner)
    stopped = task_runtime.stop_task(meta["task_id"], store=store)
    final = task_runtime.wait_for_task(meta["task_id"], timeout_seconds=2, store=store)

    assert stopped["status"] == "stopping"
    assert final["status"] == "stopped"
    assert store.read_result(meta["task_id"])["stopped"] is True



def test_task_runtime_times_out_and_marks_task(tmp_path):
    store = task_runtime.TaskStore(root=tmp_path / "tasks")

    def runner(meta, stop_event, parent_agent, store):
        deadline = time.time() + 1
        while time.time() < deadline and not stop_event.is_set():
            time.sleep(0.01)
        return {"late": True}

    meta = task_runtime.start_agent_task(goal="timeout", timeout_seconds=0.05, store=store, runner=runner)
    final = task_runtime.wait_for_task(meta["task_id"], timeout_seconds=1, store=store)

    assert final["status"] == "timeout"
    assert "timed out" in final["error"]


def test_task_stop_does_not_interrupt_parent_agent(tmp_path):
    store = task_runtime.TaskStore(root=tmp_path / "tasks")
    calls = []

    class Parent:
        def interrupt(self, reason):
            calls.append(reason)

    def runner(meta, stop_event, parent_agent, store):
        while not stop_event.is_set():
            time.sleep(0.01)
        return {"stopped": True}

    meta = task_runtime.start_agent_task(goal="wait", parent_agent=Parent(), store=store, runner=runner)
    task_runtime.stop_task(meta["task_id"], store=store)
    final = task_runtime.wait_for_task(meta["task_id"], timeout_seconds=1, store=store)

    assert final["status"] == "stopped"
    assert calls == []


def test_stale_recovery_marks_orphaned_running_task_failed(tmp_path):
    store = task_runtime.TaskStore(root=tmp_path / "tasks")
    meta = store.create_task(goal="orphaned")
    store.update_task(
        meta["task_id"],
        status="running",
        started_at=time.time() - 60,
        runtime_pid=-1,
        runtime_instance_id="dead-runtime",
    )

    recovered = task_runtime.recover_stale_tasks(store=store)
    final = store.get_task(meta["task_id"])

    assert [item["task_id"] for item in recovered] == [meta["task_id"]]
    assert final["status"] == "failed"
    assert "stale" in final["error"]
    assert final["ended_at"] is not None


def test_max_parallel_tasks_rejects_new_task_when_limit_reached(tmp_path):
    store = task_runtime.TaskStore(root=tmp_path / "tasks")

    def runner(meta, stop_event, parent_agent, store):
        while not stop_event.is_set():
            time.sleep(0.01)
        return {"stopped": True}

    meta = task_runtime.start_agent_task(goal="first", store=store, runner=runner, max_parallel_tasks=1)
    try:
        with pytest.raises(RuntimeError, match="max_parallel_tasks"):
            task_runtime.start_agent_task(goal="second", store=store, runner=runner, max_parallel_tasks=1)
    finally:
        task_runtime.stop_task(meta["task_id"], store=store)
        task_runtime.wait_for_task(meta["task_id"], timeout_seconds=1, store=store)

    assert len(store.list_tasks(limit=None)) == 1


def test_cleanup_artifacts_removes_only_expired_terminal_tasks(tmp_path):
    store = task_runtime.TaskStore(root=tmp_path / "tasks")
    old = store.create_task(goal="old")
    fresh = store.create_task(goal="fresh")
    pending = store.create_task(goal="pending")
    now = time.time()

    store.update_task(old["task_id"], status="completed", ended_at=now - 100)
    store.update_task(fresh["task_id"], status="completed", ended_at=now)
    store.update_task(pending["task_id"], created_at=now - 100, updated_at=now - 100)

    report = task_runtime.cleanup_task_artifacts(retention_seconds=1, now=now, store=store)

    assert report["deleted"] == [old["task_id"]]
    assert store.get_task(old["task_id"]) is None
    assert store.get_task(fresh["task_id"]) is not None
    assert store.get_task(pending["task_id"]) is not None


def test_task_runtime_diagnostics_reports_counts_and_stale_candidates(tmp_path):
    store = task_runtime.TaskStore(root=tmp_path / "tasks")
    stale = store.create_task(goal="stale")
    done = store.create_task(goal="done")
    store.update_task(stale["task_id"], status="running", runtime_pid=-1, runtime_instance_id="dead-runtime")
    store.update_task(done["task_id"], status="completed", ended_at=time.time())

    diagnostics = task_runtime.task_runtime_diagnostics(store=store)

    assert diagnostics["task_count"] == 2
    assert diagnostics["status_counts"]["running"] == 1
    assert diagnostics["status_counts"]["completed"] == 1
    assert diagnostics["stale_task_ids"] == [stale["task_id"]]
    assert diagnostics["active_count"] == 0
