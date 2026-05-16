from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from symphony.config import HermesConfig
from symphony.errors import SymphonyError
from symphony.runner import HermesRunner, RunnerStatus


@dataclass(frozen=True)
class Lease:
    path: Path
    evidence_dir: Path


class FakeCompletedProcess:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_subprocess_runner_invokes_hermes_safely_with_workspace_cwd_and_evidence_env(tmp_path):
    calls = []

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))
        return FakeCompletedProcess(returncode=0, stdout="done", stderr="")

    lease = Lease(path=tmp_path / "workspace", evidence_dir=tmp_path / "workspace" / ".symphony" / "evidence")
    lease.evidence_dir.mkdir(parents=True)
    prompt = "hello; rm -rf / && echo unsafe"

    result = HermesRunner(
        HermesConfig(mode="subprocess", command="custom-hermes"),
        subprocess_run=fake_run,
        base_env={"PATH": "/usr/bin", "SECRET_TOKEN": "do-not-copy"},
    ).run_turn(prompt, lease)

    assert result.status == RunnerStatus.TURN_COMPLETED
    assert result.stdout == "done"
    assert result.stderr == ""
    assert result.returncode == 0
    assert result.events == ["turn_started", "turn_completed"]
    assert result.evidence_dir == lease.evidence_dir
    assert result.evidence_path == lease.evidence_dir
    assert result.started_at <= result.ended_at

    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args == (["custom-hermes", "chat", "-q", prompt],)
    assert kwargs["cwd"] == lease.path
    assert kwargs["env"]["SYMPHONY_EVIDENCE_DIR"] == str(lease.evidence_dir)
    assert kwargs["env"]["PATH"] == "/usr/bin"
    assert "SECRET_TOKEN" not in kwargs["env"]
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True
    assert kwargs["check"] is False
    assert kwargs["shell"] is False


def test_subprocess_runner_uses_default_safe_hermes_command(tmp_path):
    calls = []

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))
        return FakeCompletedProcess(returncode=0)

    lease = Lease(path=tmp_path / "workspace", evidence_dir=tmp_path / "workspace" / "evidence")
    lease.evidence_dir.mkdir(parents=True)

    HermesRunner(HermesConfig(), subprocess_run=fake_run, base_env={}).run_turn("prompt", lease)

    args, kwargs = calls[0]
    assert args[0][:3] == ["hermes", "chat", "-q"]
    assert kwargs["shell"] is False


@pytest.mark.parametrize("returncode", [1, 2, 127])
def test_nonzero_exit_maps_to_turn_failed(tmp_path, returncode):
    def fake_run(*args, **kwargs):
        return FakeCompletedProcess(returncode=returncode, stdout="partial", stderr="bad")

    lease = Lease(path=tmp_path / "workspace", evidence_dir=tmp_path / "workspace" / "evidence")
    lease.evidence_dir.mkdir(parents=True)

    result = HermesRunner(HermesConfig(), subprocess_run=fake_run, base_env={}).run_turn("prompt", lease)

    assert result.status == RunnerStatus.TURN_FAILED
    assert result.returncode == returncode
    assert result.stdout == "partial"
    assert result.stderr == "bad"
    assert result.events == ["turn_started", "turn_failed"]


def test_timeout_maps_to_turn_timeout(tmp_path):
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs["timeout"], output="before", stderr="late")

    lease = Lease(path=tmp_path / "workspace", evidence_dir=tmp_path / "workspace" / "evidence")
    lease.evidence_dir.mkdir(parents=True)

    result = HermesRunner(HermesConfig(), subprocess_run=fake_run, base_env={}).run_turn("prompt", lease, timeout_seconds=3)

    assert result.status == RunnerStatus.TURN_TIMEOUT
    assert result.returncode is None
    assert result.stdout == "before"
    assert result.stderr == "late"
    assert result.events == ["turn_started", "turn_timeout"]


def test_in_process_mode_is_feature_gated(tmp_path):
    lease = Lease(path=tmp_path / "workspace", evidence_dir=tmp_path / "workspace" / "evidence")

    with pytest.raises(SymphonyError) as exc_info:
        HermesRunner(HermesConfig(mode="in_process"), subprocess_run=lambda *a, **k: None).run_turn("prompt", lease)

    assert exc_info.value.code == "unsupported_runner_mode"


def test_invalid_command_string_maps_to_runner_configuration_error(tmp_path):
    lease = Lease(path=tmp_path / "workspace", evidence_dir=tmp_path / "workspace" / "evidence")

    with pytest.raises(SymphonyError) as exc_info:
        HermesRunner(HermesConfig(command='"unterminated'), subprocess_run=lambda *a, **k: None).run_turn("prompt", lease)

    assert exc_info.value.code == "invalid_runner_command"


def test_subprocess_os_error_maps_to_turn_failed_result(tmp_path):
    def fake_run(*args, **kwargs):
        raise FileNotFoundError("no hermes")

    lease = Lease(path=tmp_path / "workspace", evidence_dir=tmp_path / "workspace" / "evidence")
    lease.evidence_dir.mkdir(parents=True)

    result = HermesRunner(HermesConfig(), subprocess_run=fake_run, base_env={}).run_turn("prompt", lease)

    assert result.status == RunnerStatus.TURN_FAILED
    assert result.returncode is None
    assert "no hermes" in result.stderr
