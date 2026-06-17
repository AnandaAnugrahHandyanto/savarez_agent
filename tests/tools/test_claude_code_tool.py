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
    monkeypatch.setattr(
        cct,
        "_collect_claude_metadata",
        lambda claude_bin: {
            "claude_path": claude_bin,
            "claude_version": "claude test-version",
            "claude_version_error": None,
        },
    )


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
    "expected_artifact_existed_before",
    "success_basis",
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
    assert set(kwargs["env"]) <= getattr(cct, "ENV_ALLOWLIST")
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
    assert metadata["success_basis"] == "process_exit_zero_unverified"
    assert metadata["process_success"] is True
    assert metadata["task_success"] is True
    assert metadata["claude_path"] == "/usr/bin/claude"
    assert metadata["claude_version"] == "claude test-version"
    assert metadata["full_output_artifacts"] is True
    assert metadata["capture_memory_bound"] is True
    assert metadata["artifact_persistence_bound"] is True
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
    assert "relies on Claude Code --permission-mode plan" in metadata["plan_mode_boundary"]


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

    def run_and_modify(*args, **kwargs):
        (Path(kwargs["cwd"]) / "built.txt").write_text("done now")
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    run = Mock(side_effect=run_and_modify)
    monkeypatch.setattr(cct.subprocess, "run", run)

    success = _load(cct.ask_claude_code("work", workdir=str(workdir), expected_artifact="built.txt"))
    failure = _load(cct.ask_claude_code("work", workdir=str(workdir), expected_artifact="missing.txt"))

    assert success["success"] is True
    assert success["expected_artifact_exists"] is True
    assert success["expected_artifact_existed_before"] is True
    assert success["success_basis"] == "expected_artifact_modified"
    success_metadata = json.loads(Path(success["metadata_path"]).read_text())
    assert success_metadata["expected_artifact"].endswith("built.txt")
    assert success_metadata["expected_artifact_exists"] is True
    assert success_metadata["expected_artifact_existed_before"] is True

    assert failure["success"] is False
    _assert_full_failure_schema(failure)
    assert failure["expected_artifact_exists"] is False
    assert failure["expected_artifact_existed_before"] is False
    assert failure["success_basis"] == "expected_artifact_missing"
    assert "expected_artifact was not found" in failure["error"]


def test_expected_artifact_rejects_paths_outside_workdir(tmp_path, hermes_home, fake_claude, monkeypatch):
    workdir = tmp_path / "repo"
    workdir.mkdir()
    run = Mock(return_value=SimpleNamespace(returncode=0, stdout="ok", stderr=""))
    monkeypatch.setattr(cct.subprocess, "run", run)

    result = _load(cct.ask_claude_code("work", workdir=str(workdir), expected_artifact=str(tmp_path / "outside.txt")))

    _assert_full_failure_schema(result)
    assert result["success_basis"] == "preflight_failed"
    assert "expected_artifact must be inside workdir" in result["error"]
    run.assert_not_called()


def test_expected_artifact_rejects_outside_paths_before_signature_stat(tmp_path, hermes_home, fake_claude, monkeypatch):
    workdir = tmp_path / "repo"
    workdir.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("outside")
    signature = Mock(side_effect=AssertionError("should not stat outside-workdir expected_artifact"))
    monkeypatch.setattr(cct, "_artifact_signature", signature)

    result = _load(cct.ask_claude_code("work", workdir=str(workdir), expected_artifact=str(outside)))

    _assert_full_failure_schema(result)
    assert "expected_artifact must be inside workdir" in result["error"]
    signature.assert_not_called()


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


def test_preexisting_expected_artifact_unchanged_is_not_success(tmp_path, fake_claude, monkeypatch):
    workdir = tmp_path / "repo"
    workdir.mkdir()
    artifact = workdir / "built.txt"
    artifact.write_text("stale")
    run = Mock(return_value=SimpleNamespace(returncode=0, stdout="ok", stderr=""))
    monkeypatch.setattr(cct.subprocess, "run", run)

    result = _load(cct.ask_claude_code("work", workdir=str(workdir), expected_artifact="built.txt"))

    assert result["success"] is False
    assert result["success_basis"] == "expected_artifact_preexisting_unchanged"
    assert "unchanged" in result["error"]
    metadata = json.loads(Path(result["metadata_path"]).read_text())
    assert metadata["process_success"] is True
    assert metadata["task_success"] is False
    assert metadata["expected_artifact_changed"] is False
    assert metadata["expected_artifact_signature_before"] == metadata["expected_artifact_signature_after"]


def test_created_expected_artifact_is_success(tmp_path, fake_claude, monkeypatch):
    workdir = tmp_path / "repo"
    workdir.mkdir()

    def run_and_create(*args, **kwargs):
        (Path(kwargs["cwd"]) / "created.txt").write_text("created")
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(cct.subprocess, "run", Mock(side_effect=run_and_create))

    result = _load(cct.ask_claude_code("work", workdir=str(workdir), expected_artifact="created.txt"))

    assert result["success"] is True
    assert result["success_basis"] == "expected_artifact_created"
    metadata = json.loads(Path(result["metadata_path"]).read_text())
    assert metadata["expected_artifact_existed_before"] is False
    assert metadata["expected_artifact_changed"] is True


def test_output_artifacts_are_bounded_and_keep_tails(tmp_path, fake_claude, monkeypatch):
    workdir = tmp_path / "repo"
    workdir.mkdir()
    stdout = "α" * (cct.MAX_OUTPUT_CHARS + 20) + "STDOUT_TAIL"
    stderr = "β" * (cct.MAX_OUTPUT_CHARS + 20) + "STDERR_TAIL"
    monkeypatch.setattr(cct.subprocess, "run", Mock(return_value=SimpleNamespace(returncode=0, stdout=stdout, stderr=stderr)))

    result = _load(cct.ask_claude_code("work", workdir=str(workdir)))

    assert result["stdout_tail"].endswith("STDOUT_TAIL")
    assert result["stderr_tail"].endswith("STDERR_TAIL")
    persisted_stdout = Path(result["stdout_path"]).read_text()
    persisted_stderr = Path(result["stderr_path"]).read_text()
    assert len(persisted_stdout) <= cct.MAX_OUTPUT_CHARS
    assert len(persisted_stderr) <= cct.MAX_OUTPUT_CHARS
    assert persisted_stdout.endswith("STDOUT_TAIL")
    assert persisted_stderr.endswith("STDERR_TAIL")
    metadata = json.loads(Path(result["metadata_path"]).read_text())
    assert metadata["stdout_truncated"] is True
    assert metadata["stderr_truncated"] is True
    assert metadata["full_output_artifacts"] is False
    assert metadata["stdout_chars"] == len(stdout)
    assert metadata["stderr_chars"] == len(stderr)


def test_popen_capture_is_memory_and_artifact_bounded(tmp_path, hermes_home, monkeypatch):
    workdir = tmp_path / "repo"
    workdir.mkdir()
    claude = tmp_path / "claude"
    claude.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "sys.stdout.write('x' * 60000 + 'POUT_TAIL')\n"
        "sys.stderr.write('y' * 60000 + 'PERR_TAIL')\n",
        encoding="utf-8",
    )
    claude.chmod(0o755)
    monkeypatch.setattr(cct, "_find_claude_binary", lambda: str(claude))
    monkeypatch.setattr(
        cct,
        "_collect_claude_metadata",
        lambda claude_bin: {"claude_path": claude_bin, "claude_version": None, "claude_version_error": None},
    )

    result = _load(cct.ask_claude_code("work", workdir=str(workdir)))

    assert result["success"] is True
    assert result["stdout_tail"].endswith("POUT_TAIL")
    assert result["stderr_tail"].endswith("PERR_TAIL")
    persisted_stdout = Path(result["stdout_path"]).read_text(encoding="utf-8")
    persisted_stderr = Path(result["stderr_path"]).read_text(encoding="utf-8")
    assert len(persisted_stdout) <= cct.MAX_OUTPUT_CHARS
    assert len(persisted_stderr) <= cct.MAX_OUTPUT_CHARS
    assert persisted_stdout.endswith("POUT_TAIL")
    assert persisted_stderr.endswith("PERR_TAIL")
    metadata = json.loads(Path(result["metadata_path"]).read_text(encoding="utf-8"))
    assert metadata["stdout_truncated"] is True
    assert metadata["stderr_truncated"] is True
    assert metadata["stdout_chars"] == 60000 + len("POUT_TAIL")
    assert metadata["stderr_chars"] == 60000 + len("PERR_TAIL")
    assert metadata["capture_memory_bound"] is True
    assert metadata["artifact_persistence_bound"] is True


def test_popen_capture_replaces_invalid_utf8_stdout_and_stderr(tmp_path, hermes_home, monkeypatch):
    workdir = tmp_path / "repo"
    workdir.mkdir()
    claude = tmp_path / "claude"
    claude.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "sys.stdout.buffer.write(b'out-\\xff-tail')\n"
        "sys.stderr.buffer.write(b'err-\\xfe-tail')\n",
        encoding="utf-8",
    )
    claude.chmod(0o755)

    def run_should_not_be_used(*args, **kwargs):
        raise AssertionError("subprocess.run path should not be used in this Popen regression test")

    run_should_not_be_used.__module__ = "subprocess"
    monkeypatch.setattr(cct.subprocess, "run", run_should_not_be_used)
    monkeypatch.setattr(cct, "_find_claude_binary", lambda: str(claude))
    monkeypatch.setattr(
        cct,
        "_collect_claude_metadata",
        lambda claude_bin: {"claude_path": claude_bin, "claude_version": None, "claude_version_error": None},
    )

    result = _load(cct.ask_claude_code("work", workdir=str(workdir)))

    assert result["success"] is True, result
    assert result["stdout_tail"] == "out-�-tail"
    assert result["stderr_tail"] == "err-�-tail"
    assert Path(result["stdout_path"]).read_text(encoding="utf-8") == "out-�-tail"
    assert Path(result["stderr_path"]).read_text(encoding="utf-8") == "err-�-tail"
    metadata = json.loads(Path(result["metadata_path"]).read_text(encoding="utf-8"))
    assert metadata["stdout_chars"] == len("out-�-tail")
    assert metadata["stderr_chars"] == len("err-�-tail")


def test_env_policy_excludes_hermes_home_and_secrets(tmp_path, fake_claude, monkeypatch):
    workdir = tmp_path / "repo"
    workdir.mkdir()
    blocked_hermes_home = tmp_path / "blocked-hermes-home"
    monkeypatch.setenv("HERMES_HOME", str(blocked_hermes_home))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret")
    monkeypatch.setenv("CUSTOM_TOKEN", "secret")
    monkeypatch.setenv("PASSWORD", "secret")
    monkeypatch.setenv("PASS", "secret")
    monkeypatch.setenv("CREDENTIAL", "secret")
    monkeypatch.setenv("AUTH", "secret")
    monkeypatch.setenv("COOKIE", "secret")
    monkeypatch.setenv("SESSION", "secret")
    monkeypatch.setattr(
        cct,
        "ENV_ALLOWLIST",
        cct.ENV_ALLOWLIST | {"PASSWORD", "PASS", "CREDENTIAL", "AUTH", "COOKIE", "SESSION"},
    )
    run = Mock(return_value=SimpleNamespace(returncode=0, stdout="ok", stderr=""))
    monkeypatch.setattr(cct.subprocess, "run", run)

    result = _load(cct.ask_claude_code("work", workdir=str(workdir)))
    env = run.call_args.kwargs["env"]

    assert "HERMES_HOME" not in env
    assert "ANTHROPIC_API_KEY" not in env
    assert "CUSTOM_TOKEN" not in env
    assert "PASSWORD" not in env
    assert "PASS" not in env
    assert "CREDENTIAL" not in env
    assert "AUTH" not in env
    assert "COOKIE" not in env
    assert "SESSION" not in env
    assert set(env) <= cct.ENV_ALLOWLIST
    metadata = json.loads(Path(result["metadata_path"]).read_text())
    assert "HERMES_HOME" not in metadata["env_allowlist"]
    assert "key, secret, token, password, pass, credential, auth, cookie, session" in metadata["env_policy"]


def test_unicode_prompt_output_and_metadata_round_trip(tmp_path, fake_claude, monkeypatch):
    workdir = tmp_path / "repo"
    workdir.mkdir()
    prompt = "اكتب ملخصًا عن ابن عربي — こんにちは 🌙"
    output = "نتيجة: حكمة شرقية 漢字 ✅"
    run = Mock(return_value=SimpleNamespace(returncode=0, stdout=output, stderr="خطأ؟ لا"))
    monkeypatch.setattr(cct.subprocess, "run", run)

    result = _load(cct.ask_claude_code(prompt, workdir=str(workdir)))

    assert result["stdout_tail"] == output
    assert Path(result["stdout_path"]).read_text(encoding="utf-8") == output
    command = run.call_args.args[0]
    assert command[2] == prompt
    metadata_text = Path(result["metadata_path"]).read_text(encoding="utf-8")
    assert "حكمة شرقية" in metadata_text or json.loads(metadata_text)["stdout_chars"] == len(output)


def test_check_fn_uses_which_fallback_and_auth_probe(monkeypatch, tmp_path):
    auth_probe = Mock(return_value=True)
    monkeypatch.setattr(cct, "_check_claude_auth_available", auth_probe)
    monkeypatch.setattr(cct.shutil, "which", lambda name: "/bin/claude")
    assert cct.check_claude_code_requirements() is True
    auth_probe.assert_called_with("/bin/claude")

    monkeypatch.setattr(cct.shutil, "which", lambda name: None)
    fallback = tmp_path / "claude"
    fallback.write_text("#!/bin/sh\n")
    monkeypatch.setattr(cct, "CLAUDE_FALLBACK_PATH", fallback)
    assert cct.check_claude_code_requirements() is True
    auth_probe.assert_called_with(str(fallback))

    auth_probe.return_value = False
    assert cct.check_claude_code_requirements() is False

    fallback.unlink()
    auth_probe.reset_mock()
    assert cct.check_claude_code_requirements() is False
    auth_probe.assert_not_called()


def test_auth_probe_runs_noninteractive_plan_mode(monkeypatch):
    run = Mock(return_value=SimpleNamespace(returncode=0, stdout="OK", stderr=""))
    monkeypatch.setattr(cct.subprocess, "run", run)

    assert cct._check_claude_auth_available("/bin/claude") is True

    command = run.call_args.args[0]
    assert command == [
        "/bin/claude",
        "-p",
        "Reply with OK.",
        "--max-turns",
        "1",
        "--output-format",
        "text",
        "--permission-mode",
        "plan",
    ]
    assert run.call_args.kwargs["timeout"] == cct.AUTH_CHECK_TIMEOUT_SECONDS
    assert run.call_args.kwargs["shell"] is False


def test_auth_probe_fails_closed_on_nonzero_or_exception(monkeypatch):
    monkeypatch.setattr(cct.subprocess, "run", Mock(return_value=SimpleNamespace(returncode=1, stdout="", stderr="login")))
    assert cct._check_claude_auth_available("/bin/claude") is False

    monkeypatch.setattr(cct.subprocess, "run", Mock(side_effect=TimeoutError("boom")))
    assert cct._check_claude_auth_available("/bin/claude") is False
