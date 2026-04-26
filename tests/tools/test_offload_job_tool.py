import json
import time

from tools.registry import registry
from tools import offload_job_tool as offload


def _decode(raw):
    return json.loads(raw)


def _wait_for_terminal_status(job_id, wanted, timeout=5):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = _decode(offload.offload_job_tool("status", job_id=job_id))
        if last["job"]["status"] in wanted:
            return last
        time.sleep(0.05)
    return last


def test_offload_job_fallback_runs_command_and_tails_log(tmp_path, monkeypatch):
    monkeypatch.setattr(offload, "_systemd_run_available", lambda: False)

    result = _decode(
        offload.offload_job_tool(
            "start",
            command="echo hello-offload",
            workdir=str(tmp_path),
            label="unit",
        )
    )

    assert result["success"] is True
    job = result["job"]
    assert job["runner"] == "subprocess"
    assert job["status"] == "running"
    assert job["workdir"] == str(tmp_path)

    status = _wait_for_terminal_status(job["job_id"], {"succeeded", "failed", "unknown"})
    assert status["job"]["status"] == "succeeded"
    assert status["job"]["exit_code"] == 0

    tail = _decode(offload.offload_job_tool("tail", job_id=job["job_id"], tail_lines=20))
    assert tail["success"] is True
    assert "hello-offload" in tail["tail"]


def test_offload_job_list_returns_newest_first(tmp_path, monkeypatch):
    monkeypatch.setattr(offload, "_systemd_run_available", lambda: False)
    first = _decode(offload.offload_job_tool("start", command="echo first", workdir=str(tmp_path), label="first"))["job"]
    second = _decode(offload.offload_job_tool("start", command="echo second", workdir=str(tmp_path), label="second"))["job"]

    _wait_for_terminal_status(first["job_id"], {"succeeded", "failed", "unknown"})
    _wait_for_terminal_status(second["job_id"], {"succeeded", "failed", "unknown"})

    listed = _decode(offload.offload_job_tool("list", limit=10))
    ids = [job["job_id"] for job in listed["jobs"]]
    assert ids.index(second["job_id"]) < ids.index(first["job_id"])


def test_offload_job_cancel_unknown_job_returns_structured_error():
    result = _decode(offload.offload_job_tool("cancel", job_id="missing-job"))
    assert result["success"] is False
    assert "Unknown offload job" in result["error"]


def test_offload_job_cancel_running_fallback_job(tmp_path, monkeypatch):
    monkeypatch.setattr(offload, "_systemd_run_available", lambda: False)

    result = _decode(
        offload.offload_job_tool(
            "start",
            command="sleep 30",
            workdir=str(tmp_path),
            label="cancel",
        )
    )
    assert result["success"] is True

    cancelled = _decode(offload.offload_job_tool("cancel", job_id=result["job"]["job_id"]))
    assert cancelled["success"] is True
    assert cancelled["job"]["status"] == "cancelled"

    status = _decode(offload.offload_job_tool("status", job_id=result["job"]["job_id"]))
    assert status["job"]["status"] == "cancelled"


def test_offload_job_uses_systemd_when_available(tmp_path, monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)

        class Result:
            returncode = 0
            stdout = "Running as unit hermes-offload-demo.service"
            stderr = ""

        return Result()

    monkeypatch.setattr(offload, "_systemd_run_available", lambda: True)
    monkeypatch.setattr(offload.subprocess, "run", fake_run)

    result = _decode(
        offload.offload_job_tool(
            "start",
            command="echo systemd",
            workdir=str(tmp_path),
            memory_max="32G",
            cpu_quota="800%",
            label="systemd",
        )
    )

    assert result["success"] is True
    job = result["job"]
    assert job["runner"] == "systemd"
    assert job["unit_name"].startswith("hermes-offload-")
    flat = " ".join(calls[0])
    assert "MemoryMax=32G" in flat
    assert "CPUQuota=800%" in flat
    assert f"WorkingDirectory={tmp_path}" in flat


def test_offload_job_registered_in_terminal_toolset():
    import toolsets

    entry = registry.get_entry("offload_job")
    assert entry is not None
    assert entry.toolset == "terminal"
    assert "offload" in entry.schema["name"]
    assert "offload_job" in toolsets.resolve_toolset("terminal")
    assert "offload_job" in toolsets.resolve_toolset("hermes-gateway")
