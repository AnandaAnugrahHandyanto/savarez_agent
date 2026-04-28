"""Unit tests for the Koyeb cloud sandbox environment backend."""

import threading
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers to build mock Koyeb SDK objects
# ---------------------------------------------------------------------------

def _make_exec_response(stdout="", stderr="", exit_code=0):
    return SimpleNamespace(stdout=stdout, stderr=stderr, exit_code=exit_code)


def _make_sandbox(sandbox_id="sb-koyeb-123"):
    sb = MagicMock()
    sb.id = sandbox_id
    sb.exec.return_value = _make_exec_response()
    sb.filesystem = MagicMock()
    return sb


def _patch_koyeb_imports(monkeypatch):
    """Patch the koyeb SDK so KoyebEnvironment can be imported without it."""
    import types as _types

    koyeb_mod = _types.ModuleType("koyeb")
    koyeb_mod.Sandbox = MagicMock()

    monkeypatch.setitem(__import__("sys").modules, "koyeb", koyeb_mod)
    return koyeb_mod


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def koyeb_sdk(monkeypatch):
    """Provide a mock koyeb SDK module and return it for assertions."""
    return _patch_koyeb_imports(monkeypatch)


@pytest.fixture()
def make_env(koyeb_sdk, monkeypatch):
    """Factory that creates a KoyebEnvironment with a mocked SDK."""
    monkeypatch.setattr("tools.environments.base.is_interrupted", lambda: False)
    monkeypatch.setattr("tools.credential_files.get_credential_file_mounts", lambda: [])
    monkeypatch.setattr("tools.credential_files.get_skills_directory_mount", lambda **kw: None)
    monkeypatch.setattr("tools.credential_files.iter_skills_files", lambda **kw: [])

    def _factory(
        sandbox=None,
        home_dir="/root",
        **kwargs,
    ):
        sandbox = sandbox or _make_sandbox()
        # Mock the $HOME detection
        sandbox.exec.return_value = _make_exec_response(stdout=home_dir)

        koyeb_sdk.Sandbox.create.return_value = sandbox

        from tools.environments.koyeb import KoyebEnvironment

        kwargs.setdefault("task_id", "test-task")
        env = KoyebEnvironment(
            image="koyeb/sandbox:latest",
            **kwargs,
        )
        return env

    return _factory


# ---------------------------------------------------------------------------
# Constructor / cwd resolution
# ---------------------------------------------------------------------------

class TestCwdResolution:
    def test_default_cwd_resolves_home(self, make_env):
        env = make_env(home_dir="/home/testuser")
        assert env.cwd == "/home/testuser"

    def test_tilde_cwd_resolves_home(self, make_env):
        env = make_env(cwd="~", home_dir="/home/testuser")
        assert env.cwd == "/home/testuser"

    def test_explicit_cwd_not_overridden(self, make_env):
        env = make_env(cwd="/workspace", home_dir="/root")
        assert env.cwd == "/workspace"

    def test_home_detection_failure_keeps_default_cwd(self, make_env):
        sb = _make_sandbox()
        sb.exec.side_effect = RuntimeError("exec failed")
        env = make_env(sandbox=sb)
        assert env.cwd == "/root"  # keeps constructor default

    def test_empty_home_keeps_default_cwd(self, make_env):
        env = make_env(home_dir="")
        assert env.cwd == "/root"


# ---------------------------------------------------------------------------
# Sandbox name sanitization
# ---------------------------------------------------------------------------

class TestSandboxNameSanitization:
    def test_underscores_replaced_with_hyphens(self, make_env, koyeb_sdk):
        make_env(task_id="my_test_task")
        name_arg = koyeb_sdk.Sandbox.create.call_args[1]["name"]
        assert "_" not in name_arg
        assert name_arg == "hermes-my-test-task"

    def test_uppercase_lowered(self, make_env, koyeb_sdk):
        make_env(task_id="MyTask")
        name_arg = koyeb_sdk.Sandbox.create.call_args[1]["name"]
        assert name_arg == "hermes-mytask"

    def test_special_chars_removed(self, make_env, koyeb_sdk):
        make_env(task_id="task@#$123")
        name_arg = koyeb_sdk.Sandbox.create.call_args[1]["name"]
        assert name_arg == "hermes-task-123"

    def test_name_truncated_to_63_chars(self, make_env, koyeb_sdk):
        make_env(task_id="a" * 100)
        name_arg = koyeb_sdk.Sandbox.create.call_args[1]["name"]
        assert len(name_arg) <= 63

    def test_consecutive_hyphens_collapsed(self, make_env, koyeb_sdk):
        make_env(task_id="a__b---c")
        name_arg = koyeb_sdk.Sandbox.create.call_args[1]["name"]
        assert "--" not in name_arg


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

class TestCleanup:
    def test_cleanup_deletes_sandbox(self, make_env):
        env = make_env()
        sb = env._sandbox
        env.cleanup()
        sb.delete.assert_called_once()

    def test_cleanup_idempotent(self, make_env):
        env = make_env()
        env.cleanup()
        env.cleanup()  # should not raise

    def test_cleanup_swallows_errors(self, make_env):
        env = make_env()
        env._sandbox.delete.side_effect = RuntimeError("delete failed")
        env.cleanup()  # should not raise
        assert env._sandbox is None

    def test_cleanup_calls_sync_back_before_delete(self, make_env):
        env = make_env()
        call_order = []
        sync_mgr = MagicMock()
        sync_mgr.sync_back = lambda: call_order.append("sync_back")
        env._sync_manager = sync_mgr
        original_delete = env._sandbox.delete
        env._sandbox.delete = lambda: (call_order.append("delete"), original_delete())

        env.cleanup()

        assert "sync_back" in call_order
        assert "delete" in call_order
        assert call_order.index("sync_back") < call_order.index("delete")


# ---------------------------------------------------------------------------
# Execute
# ---------------------------------------------------------------------------

class TestExecute:
    def test_basic_command(self, make_env):
        sb = _make_sandbox()
        # Calls: (1) $HOME detection, (2) init_session bootstrap, (3) actual command
        sb.exec.side_effect = [
            _make_exec_response(stdout="/root"),           # $HOME
            _make_exec_response(stdout="", exit_code=0),   # init_session
            _make_exec_response(stdout="hello", exit_code=0),  # actual cmd
        ]
        env = make_env(sandbox=sb)

        result = env.execute("echo hello")
        assert "hello" in result["output"]
        assert result["returncode"] == 0

    def test_nonzero_exit_code(self, make_env):
        sb = _make_sandbox()
        sb.exec.side_effect = [
            _make_exec_response(stdout="/root"),
            _make_exec_response(stdout="", exit_code=0),   # init_session
            _make_exec_response(stdout="not found", exit_code=127),
        ]
        env = make_env(sandbox=sb)

        result = env.execute("bad_cmd")
        assert result["returncode"] == 127

    def test_stderr_included_in_output(self, make_env):
        sb = _make_sandbox()
        sb.exec.side_effect = [
            _make_exec_response(stdout="/root"),
            _make_exec_response(stdout="", exit_code=0),   # init_session
            _make_exec_response(stdout="out", stderr="err", exit_code=0),
        ]
        env = make_env(sandbox=sb)

        result = env.execute("cmd")
        assert "out" in result["output"]
        assert "err" in result["output"]

    def test_stdin_data_wraps_heredoc(self, make_env):
        sb = _make_sandbox()
        sb.exec.side_effect = [
            _make_exec_response(stdout="/root"),
            _make_exec_response(stdout="", exit_code=0),   # init_session
            _make_exec_response(stdout="ok", exit_code=0),
        ]
        env = make_env(sandbox=sb)

        env.execute("python3", stdin_data="print('hi')")
        call_args = sb.exec.call_args_list[-1]
        cmd = call_args[0][0]
        assert "HERMES_STDIN_" in cmd
        assert "print" in cmd


# ---------------------------------------------------------------------------
# Interrupt
# ---------------------------------------------------------------------------

class TestInterrupt:
    def test_interrupt_kills_and_returns_130(self, make_env, monkeypatch):
        sb = _make_sandbox()
        event = threading.Event()
        calls = {"n": 0}

        def exec_side_effect(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                return _make_exec_response(stdout="/root")  # $HOME
            if calls["n"] == 2:
                return _make_exec_response(stdout="", exit_code=0)  # init_session
            event.wait(timeout=5)  # simulate long-running command
            return _make_exec_response(stdout="done", exit_code=0)

        sb.exec.side_effect = exec_side_effect
        env = make_env(sandbox=sb)

        monkeypatch.setattr(
            "tools.environments.base.is_interrupted", lambda: True
        )
        try:
            result = env.execute("sleep 10")
            assert result["returncode"] == 130
            sb.delete.assert_called()  # cancel_fn calls sandbox.delete()
        finally:
            event.set()
