from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tools import claude_code_tool as cct


@pytest.fixture
def hermes_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes-home"))
    return tmp_path / "hermes-home"


@pytest.fixture
def fake_claude(monkeypatch):
    monkeypatch.setattr(cct, "_find_claude_binary", lambda: "/usr/bin/claude")


REQUIRED_RESULT_KEYS = {
    "success",
    "exit_code",
    "elapsed_seconds",
    "stdout_tail",
    "stderr_tail",
    "stdout_path",
    "stderr_path",
    "metadata_path",
    "expected_artifact_exists",
    "error",
}


def _load(result: str) -> dict:
    return json.loads(result)


def _assert_full_failure_schema(result: dict) -> None:
    assert REQUIRED_RESULT_KEYS <= result.keys()
    assert result["success"] is False
    assert isinstance(result["elapsed_seconds"], (int, float))
    assert isinstance(result["stdout_tail"], str)
    assert isinstance(result["stderr_tail"], str)
    assert result["error"]
    assert Path(result["stdout_path"]).exists()
    assert Path(result["stderr_path"]).exists()
    assert Path(result["metadata_path"]).exists()


def test_constructs_expected_command_and_writes_proof_artifacts(tmp_path, hermes_home, fake_claude, monkeypatch):
    workdir = tmp_path / "repo"
    workdir.mkdir()
    run = Mock(return_value=SimpleNamespace(returncode=0, stdout="hello from claude", stderr=""))
    monkeypatch.setattr(cct.subprocess, "run", run)

    result = _load(cct.ask_claude_code("do work", workdir=str(workdir), timeout=10, max_turns=3))

    assert result["success"] is True
    assert result["exit_code"] == 0
    assert result["stdout_tail"] == "hello from claude"
    run.assert_called_once()
    kwargs = run.call_args.kwargs
    assert kwargs["shell"] is False
    assert kwargs["cwd"] == str(workdir.resolve())
    assert kwargs["timeout"] == 10
    assert run.call_args.args[0] == [
        "/usr/bin/claude",
        "-p",
        "do work",
        "--max-turns",
        "3",
        "--output-format",
        "text",
        "--permission-mode",
        "default",
    ]

    stdout_path = Path(result["stdout_path"])
    stderr_path = Path(result["stderr_path"])
    metadata_path = Path(result["metadata_path"])
    assert stdout_path.read_text() == "hello from claude"
    assert stderr_path.read_text() == ""
    assert hermes_home in metadata_path.parents
    metadata = json.loads(metadata_path.read_text())
    assert metadata["tool"] == "ask_claude_code"
    assert metadata["workdir"] == str(workdir.resolve())
    assert metadata["timeout"] == 10
    assert metadata["max_turns"] == 3
    assert metadata["permission_mode"] == "default"
    assert metadata["stdout_path"] == str(stdout_path)
    assert metadata["stderr_path"] == str(stderr_path)


@pytest.mark.parametrize("permission_mode", ["danger", "accept-edits", ""])
def test_rejects_invalid_permission_mode(permission_mode, hermes_home, fake_claude):
    result = _load(cct.ask_claude_code("work", permission_mode=permission_mode))

    _assert_full_failure_schema(result)
    assert result["exit_code"] is None
    assert "invalid permission_mode" in result["error"]


def test_missing_prompt_returns_full_failure_schema(hermes_home):
    result = _load(cct.ask_claude_code(""))

    _assert_full_failure_schema(result)
    assert result["exit_code"] is None
    assert result["error"] == "prompt is required"


def test_missing_claude_cli_returns_full_failure_schema(hermes_home, monkeypatch):
    monkeypatch.setattr(cct, "_find_claude_binary", lambda: None)

    result = _load(cct.ask_claude_code("work"))

    _assert_full_failure_schema(result)
    assert result["exit_code"] is None
    assert "claude CLI not found" in result["error"]


def test_invalid_workdir_returns_full_failure_schema(tmp_path, hermes_home, fake_claude):
    missing = tmp_path / "missing"

    result = _load(cct.ask_claude_code("work", workdir=str(missing)))

    _assert_full_failure_schema(result)
    assert result["exit_code"] is None
    assert "workdir does not exist" in result["error"]


def test_caps_timeout_and_max_turns(tmp_path, fake_claude, monkeypatch):
    workdir = tmp_path / "repo"
    workdir.mkdir()
    run = Mock(return_value=SimpleNamespace(returncode=0, stdout="ok", stderr=""))
    monkeypatch.setattr(cct.subprocess, "run", run)

    result = _load(cct.ask_claude_code("work", workdir=str(workdir), timeout=9999, max_turns=999))

    assert result["success"] is True
    assert run.call_args.kwargs["timeout"] == cct.MAX_TIMEOUT_SECONDS
    assert "--max-turns" in run.call_args.args[0]
    assert run.call_args.args[0][run.call_args.args[0].index("--max-turns") + 1] == str(cct.MAX_MAX_TURNS)
    metadata = json.loads(Path(result["metadata_path"]).read_text())
    assert metadata["timeout"] == cct.MAX_TIMEOUT_SECONDS
    assert metadata["max_turns"] == cct.MAX_MAX_TURNS


def test_plan_mode_uses_safe_prompt_prefix_and_permission_flag(tmp_path, fake_claude, monkeypatch):
    workdir = tmp_path / "repo"
    workdir.mkdir()
    run = Mock(return_value=SimpleNamespace(returncode=0, stdout="plan", stderr=""))
    monkeypatch.setattr(cct.subprocess, "run", run)

    result = _load(cct.ask_claude_code("change files", workdir=str(workdir), permission_mode="plan"))

    assert result["success"] is True
    command = run.call_args.args[0]
    assert command[2].startswith("Plan only; do not edit files.\n\nchange files")
    assert "--dangerously-skip-permissions" not in command
    assert "--permission-mode" in command
    assert command[command.index("--permission-mode") + 1] == "plan"
    metadata = json.loads(Path(result["metadata_path"]).read_text())
    assert metadata["permission_mode"] == "plan"


def test_accept_edits_passes_documented_permission_mode(tmp_path, fake_claude, monkeypatch):
    workdir = tmp_path / "repo"
    workdir.mkdir()
    run = Mock(return_value=SimpleNamespace(returncode=0, stdout="edited", stderr=""))
    monkeypatch.setattr(cct.subprocess, "run", run)

    result = _load(cct.ask_claude_code("change files", workdir=str(workdir), permission_mode="acceptEdits"))

    assert result["success"] is True
    command = run.call_args.args[0]
    assert "--dangerously-skip-permissions" not in command
    assert command[command.index("--permission-mode") + 1] == "acceptEdits"


def test_expected_artifact_success_and_failure(tmp_path, fake_claude, monkeypatch):
    workdir = tmp_path / "repo"
    workdir.mkdir()
    (workdir / "built.txt").write_text("done")
    run = Mock(return_value=SimpleNamespace(returncode=0, stdout="ok", stderr=""))
    monkeypatch.setattr(cct.subprocess, "run", run)

    success = _load(cct.ask_claude_code("work", workdir=str(workdir), expected_artifact="built.txt"))
    failure = _load(cct.ask_claude_code("work", workdir=str(workdir), expected_artifact="missing.txt"))

    assert success["success"] is True
    assert success["expected_artifact_exists"] is True
    success_metadata = json.loads(Path(success["metadata_path"]).read_text())
    assert success_metadata["expected_artifact"].endswith("built.txt")
    assert success_metadata["expected_artifact_exists"] is True

    assert failure["success"] is False
    _assert_full_failure_schema(failure)
    assert failure["expected_artifact_exists"] is False
    assert "expected_artifact was not found" in failure["error"]


def test_timeout_returns_full_failure_schema(tmp_path, hermes_home, fake_claude, monkeypatch):
    workdir = tmp_path / "repo"
    workdir.mkdir()

    def timeout_run(*args, **kwargs):
        raise cct.subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs["timeout"], output="partial out", stderr="partial err")

    monkeypatch.setattr(cct.subprocess, "run", timeout_run)

    result = _load(cct.ask_claude_code("work", workdir=str(workdir), timeout=1))

    _assert_full_failure_schema(result)
    assert result["exit_code"] is None
    assert result["stdout_tail"] == "partial out"
    assert result["stderr_tail"] == "partial err"
    assert "timed out" in result["error"]


def test_nonzero_exit_returns_full_failure_schema(tmp_path, hermes_home, fake_claude, monkeypatch):
    workdir = tmp_path / "repo"
    workdir.mkdir()
    run = Mock(return_value=SimpleNamespace(returncode=2, stdout="out", stderr="err"))
    monkeypatch.setattr(cct.subprocess, "run", run)

    result = _load(cct.ask_claude_code("work", workdir=str(workdir)))

    _assert_full_failure_schema(result)
    assert result["exit_code"] == 2
    assert result["stdout_tail"] == "out"
    assert result["stderr_tail"] == "err"
    assert "exited with code 2" in result["error"]


def test_check_fn_uses_which_then_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(cct.shutil, "which", lambda name: "/bin/claude")
    assert cct.check_claude_code_requirements() is True

    monkeypatch.setattr(cct.shutil, "which", lambda name: None)
    fallback = tmp_path / "claude"
    fallback.write_text("#!/bin/sh\n")
    monkeypatch.setattr(cct, "CLAUDE_FALLBACK_PATH", fallback)
    assert cct.check_claude_code_requirements() is True

    fallback.unlink()
    assert cct.check_claude_code_requirements() is False
