import json
import sys
import time
from pathlib import Path

from hermes_constants import get_hermes_home
from tools import async_delegate_tool as ad
from tools import delegate_tool  # noqa: F401 - import registers delegate_task
from tools.registry import registry
from toolsets import TOOLSETS


def _parse(payload: str):
    data = json.loads(payload)
    assert "error" not in data, data
    return data


def _wait_status(job_id: str, target: str, timeout: float = 5.0):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = _parse(ad.async_delegate_status(job_id))
        if last["status"] == target:
            return last
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not reach {target}; last={last}")


def test_async_delegate_tools_registered_in_delegation_toolset():
    names = {d["function"]["name"] for d in registry.get_definitions(set(TOOLSETS["delegation"]["tools"]))}
    assert "delegate_task" in names
    assert "async_delegate_create" in names
    assert "async_delegate_status" in names
    assert "async_delegate_log" in names
    assert "async_delegate_result" in names
    assert "async_delegate_cancel" in names
    assert "async_delegate_list" in names


def test_create_returns_before_child_completes_and_result_is_durable(monkeypatch):
    def fake_cmd(**kwargs):
        return [
            sys.executable,
            "-c",
            "import time; print('child-start', flush=True); time.sleep(0.5); print('child-end', flush=True)",
        ]

    monkeypatch.setattr(ad, "_hermes_command", fake_cmd)

    started = time.time()
    created = _parse(ad.async_delegate_create("fake prompt", name="sleep-test"))
    elapsed = time.time() - started

    assert elapsed < 0.35
    assert created["status"] == "running"
    job_id = created["job_id"]

    running = _parse(ad.async_delegate_status(job_id))
    assert running["status"] in {"running", "completed"}

    done = _wait_status(job_id, "completed")
    assert done["exit_code"] == 0

    result = _parse(ad.async_delegate_result(job_id))
    assert result["status"] == "completed"
    assert "child-start" in result["stdout_tail"]
    assert "child-end" in result["stdout_tail"]

    # Prove state is durable on disk under profile-safe Hermes home.
    assert Path(done["log_path"]).is_relative_to(get_hermes_home())
    assert (get_hermes_home() / "async_delegations.db").exists()


def test_log_is_retrievable_while_job_runs(monkeypatch):
    def fake_cmd(**kwargs):
        return [
            sys.executable,
            "-c",
            "import time; print('visible-now', flush=True); time.sleep(1.0); print('done', flush=True)",
        ]

    monkeypatch.setattr(ad, "_hermes_command", fake_cmd)
    job_id = _parse(ad.async_delegate_create("fake prompt"))["job_id"]

    deadline = time.time() + 3
    log = None
    while time.time() < deadline:
        log = _parse(ad.async_delegate_log(job_id))
        if "visible-now" in log["stdout"]:
            break
        time.sleep(0.05)
    assert log and "visible-now" in log["stdout"]
    _wait_status(job_id, "completed")


def test_cancel_running_child(monkeypatch):
    def fake_cmd(**kwargs):
        return [sys.executable, "-c", "import time; print('sleeping', flush=True); time.sleep(2)"]

    terminated = []
    monkeypatch.setattr(ad, "_hermes_command", fake_cmd)
    monkeypatch.setattr(ad, "_terminate_process_group", lambda pid: terminated.append(pid))
    job_id = _parse(ad.async_delegate_create("fake prompt"))["job_id"]

    cancelled = _parse(ad.async_delegate_cancel(job_id))
    assert cancelled["cancelled"] is True
    assert cancelled["status"] == "cancelled"
    assert terminated

    status = _parse(ad.async_delegate_status(job_id))
    assert status["status"] == "cancelled"
    assert status["exit_code"] == -15


def test_storage_is_hermes_home_scoped(monkeypatch):
    def fake_cmd(**kwargs):
        return [sys.executable, "-c", "print('ok')"]

    monkeypatch.setattr(ad, "_hermes_command", fake_cmd)
    job_id = _parse(ad.async_delegate_create("fake prompt"))["job_id"]
    done = _wait_status(job_id, "completed")

    home = get_hermes_home().resolve()
    assert (home / "async_delegations.db").exists()
    assert Path(done["log_path"]).resolve().is_relative_to(home)
    assert Path(done["stderr_path"]).resolve().is_relative_to(home)
    assert Path(done["result_path"]).resolve().is_relative_to(home)
