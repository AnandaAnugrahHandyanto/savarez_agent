"""Unit tests for the Alibaba Cloud AgentRun cloud sandbox backend.

The real ``agentrun-sdk`` package is intentionally not imported here. We
patch ``sys.modules['agentrun.sandbox']`` with a stand-in module so
``AgentRunEnvironment`` can be constructed and exercised without any
network or credentials. Every test in this file is expected to pass on
CI without the SDK installed and without ``AGENTRUN_*`` env vars.
"""

from __future__ import annotations

import types as _types
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers to build a stand-in agentrun.sandbox module
# ---------------------------------------------------------------------------


class _FakeTemplateType:
    """Minimal stand-in for ``agentrun.sandbox.model.TemplateType``."""

    CODE_INTERPRETER = "code-interpreter"
    BROWSER = "browser"
    AIO = "aio"
    CUSTOM = "custom"


def _make_fake_sandbox(sandbox_id: str = "sb-fake-123") -> MagicMock:
    """Build a ``MagicMock`` shaped like a Code Interpreter sandbox."""
    sb = MagicMock()
    sb.sandbox_id = sandbox_id
    sb.check_health.return_value = {"status": "ok"}
    # Default cmd response matches the documented Code Interpreter shape.
    sb.process.cmd.return_value = {
        "stdout": "",
        "stderr": "",
        "exit_code": 0,
    }
    return sb


def _patch_agentrun_imports(monkeypatch, sandbox: MagicMock):
    """Install a stand-in ``agentrun.sandbox`` module that the adapter imports.

    Returns the fake ``Sandbox`` class so individual tests can assert on
    its calls (``Sandbox.create`` / ``Sandbox.connect`` / ``Sandbox.get_template``
    / ``Sandbox.create_template``).
    """
    fake_sandbox_cls = MagicMock(name="FakeSandboxClass")
    # By default the template already exists (get_template succeeds) so we
    # exercise the happy path. Individual tests override the side effects
    # as needed.
    fake_sandbox_cls.get_template.return_value = MagicMock(
        template_type=_FakeTemplateType.CODE_INTERPRETER,
    )
    fake_sandbox_cls.create_template.return_value = MagicMock()
    fake_sandbox_cls.create.return_value = sandbox
    fake_sandbox_cls.connect.return_value = sandbox

    fake_template_input = MagicMock(name="FakeTemplateInput")

    sandbox_mod = _types.ModuleType("agentrun.sandbox")
    sandbox_mod.Sandbox = fake_sandbox_cls
    sandbox_mod.TemplateType = _FakeTemplateType
    sandbox_mod.TemplateInput = fake_template_input

    # We also expose top-level ``agentrun`` and ``agentrun.utils.log`` in
    # case importlib walks the package; the adapter currently only
    # touches ``agentrun.sandbox`` so these are defensive.
    parent_mod = _types.ModuleType("agentrun")
    parent_mod.sandbox = sandbox_mod

    monkeypatch.setitem(__import__("sys").modules, "agentrun", parent_mod)
    monkeypatch.setitem(__import__("sys").modules, "agentrun.sandbox", sandbox_mod)
    return fake_sandbox_cls


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def fake_sandbox():
    return _make_fake_sandbox()


@pytest.fixture()
def agentrun_sdk(monkeypatch, fake_sandbox):
    """Install the stand-in SDK and return the fake ``Sandbox`` class."""
    # Quiet down hermes-side noise: skip is_interrupted checks and
    # credential file enumeration so the test only sees calls we drove.
    monkeypatch.setattr("tools.environments.base.is_interrupted", lambda: False)
    monkeypatch.setattr(
        "tools.credential_files.get_credential_file_mounts", lambda: []
    )
    monkeypatch.setattr(
        "tools.credential_files.iter_skills_files", lambda **kw: []
    )
    monkeypatch.setattr(
        "tools.credential_files.iter_cache_files", lambda **kw: []
    )
    return _patch_agentrun_imports(monkeypatch, fake_sandbox)


@pytest.fixture()
def isolated_store(monkeypatch, tmp_path):
    """Redirect the ``agentrun_sandboxes.json`` store at the module level.

    The adapter binds ``_SANDBOX_STORE`` at import time, so we have to
    patch the attribute directly rather than mutating ``HERMES_HOME``.
    """
    import tools.environments.agentrun as agentrun_mod

    monkeypatch.setattr(
        agentrun_mod, "_SANDBOX_STORE", tmp_path / "agentrun_sandboxes.json"
    )
    return tmp_path


@pytest.fixture()
def make_env(agentrun_sdk, fake_sandbox, isolated_store):
    """Factory that constructs an ``AgentRunEnvironment`` with sane defaults."""

    def _factory(*, persistent: bool = True, task_id: str = "test-task", **kwargs):
        from tools.environments.agentrun import AgentRunEnvironment

        env = AgentRunEnvironment(
            cwd="/root",
            timeout=60,
            task_id=task_id,
            persistent_filesystem=persistent,
            **kwargs,
        )
        env._mock_sandbox_cls = agentrun_sdk
        env._mock_sandbox = fake_sandbox
        return env

    return _factory


# ---------------------------------------------------------------------------
# Test 1 — create_sandbox: template name + create call wiring
# ---------------------------------------------------------------------------


class TestCreateSandbox:
    def test_create_uses_task_scoped_template_and_idle_timeout(self, make_env):
        env = make_env(task_id="alpha")
        # template_name defaults to ``hermes-{task_id}``
        env._mock_sandbox_cls.create.assert_called_once()
        kwargs = env._mock_sandbox_cls.create.call_args.kwargs
        assert kwargs["template_name"] == "hermes-alpha"
        # template_type forwarded as CODE_INTERPRETER
        assert kwargs["template_type"] == _FakeTemplateType.CODE_INTERPRETER
        # idle timeout defaults to 5 minutes
        assert kwargs["sandbox_idle_timeout_seconds"] == 300

    def test_explicit_template_name_wins(self, make_env):
        env = make_env(template_name="custom-tpl")
        kwargs = env._mock_sandbox_cls.create.call_args.kwargs
        assert kwargs["template_name"] == "custom-tpl"

    def test_template_created_when_get_returns_not_found(
        self, agentrun_sdk, isolated_store, monkeypatch, fake_sandbox
    ):
        """When the named template does not exist we create it once."""
        # Suppress hermes-internal noise (the agentrun_sdk fixture would
        # have done this, but we need a clean setup here so we replicate
        # the few critical patches).
        monkeypatch.setattr("tools.environments.base.is_interrupted", lambda: False)

        agentrun_sdk.get_template.side_effect = RuntimeError("not found")

        from tools.environments.agentrun import AgentRunEnvironment

        AgentRunEnvironment(
            cwd="/root",
            timeout=60,
            task_id="beta",
            persistent_filesystem=False,
        )

        agentrun_sdk.create_template.assert_called_once()
        # template_name must propagate into the TemplateInput payload.
        called_input = agentrun_sdk.create_template.call_args.kwargs.get("input")
        # We constructed TemplateInput via a MagicMock — assert the mock
        # was invoked with the right template_name keyword.
        # MagicMock records call args; the adapter calls TemplateInput(...)
        # imported from the patched module, so check that mock.
        import agentrun.sandbox as patched_sandbox_mod  # type: ignore[import-not-found]

        patched_sandbox_mod.TemplateInput.assert_called_once()
        ti_kwargs = patched_sandbox_mod.TemplateInput.call_args.kwargs
        assert ti_kwargs["template_name"] == "hermes-beta"
        assert ti_kwargs["template_type"] == _FakeTemplateType.CODE_INTERPRETER


# ---------------------------------------------------------------------------
# Test 2 — run_bash: cmd is invoked with the right args + timeout clamping
# ---------------------------------------------------------------------------


class TestRunBash:
    def test_basic_command_forwards_to_sandbox_process_cmd(self, make_env):
        env = make_env()
        # init_session and bulk-sync may have invoked cmd() already.
        env._mock_sandbox.process.cmd.reset_mock()
        env._mock_sandbox.process.cmd.return_value = {
            "stdout": "hello\n",
            "stderr": "",
            "exit_code": 0,
        }

        result = env.execute("echo hello")
        assert "hello" in result["output"]
        assert result["returncode"] == 0
        # The last cmd() call should have included our payload (wrapped
        # by the base class' session-snapshot machinery; we only assert
        # that ``cmd`` was reached at all and accepted a non-empty
        # command string with the cwd we configured).
        last_call = env._mock_sandbox.process.cmd.call_args
        assert last_call is not None
        assert "command" in last_call.kwargs
        assert last_call.kwargs["command"]  # non-empty
        assert last_call.kwargs["cwd"] == "/root"

    def test_timeout_clamped_to_vendor_limit(self, make_env, caplog):
        env = make_env()
        env._mock_sandbox.process.cmd.reset_mock()
        env._mock_sandbox.process.cmd.return_value = {
            "stdout": "ok",
            "stderr": "",
            "exit_code": 0,
        }

        with caplog.at_level("WARNING", logger="tools.environments.agentrun"):
            env.execute("sleep 1", timeout=120)

        # Vendor-side max is 30s; the adapter must not forward a larger
        # value silently.
        forwarded_timeouts = [
            call.kwargs.get("timeout")
            for call in env._mock_sandbox.process.cmd.call_args_list
        ]
        assert all(t is None or t <= 30 for t in forwarded_timeouts)
        assert any("clamping" in rec.message for rec in caplog.records)


# ---------------------------------------------------------------------------
# Test 3 — file sync: upload + delete + bulk download all reach the SDK
# ---------------------------------------------------------------------------


class TestFileSync:
    def test_upload_calls_mkdir_then_upload(self, make_env):
        env = make_env()
        env._mock_sandbox.file_system.mkdir.reset_mock()
        env._mock_sandbox.file_system.upload.reset_mock()

        env._agentrun_upload("/tmp/host-file.txt", "/root/.hermes/foo/bar.txt")

        env._mock_sandbox.file_system.mkdir.assert_called_once_with(
            path="/root/.hermes/foo", parents=True,
        )
        env._mock_sandbox.file_system.upload.assert_called_once_with(
            local_file_path="/tmp/host-file.txt",
            target_file_path="/root/.hermes/foo/bar.txt",
        )

    def test_delete_invokes_rm_via_process_cmd(self, make_env):
        env = make_env()
        env._mock_sandbox.process.cmd.reset_mock()
        env._mock_sandbox.process.cmd.return_value = {
            "stdout": "", "stderr": "", "exit_code": 0,
        }

        env._agentrun_delete([
            "/root/.hermes/a.txt",
            "/root/.hermes/b.txt",
        ])

        env._mock_sandbox.process.cmd.assert_called_once()
        kwargs = env._mock_sandbox.process.cmd.call_args.kwargs
        assert kwargs["command"].startswith("rm -f ")
        assert "/root/.hermes/a.txt" in kwargs["command"]
        assert "/root/.hermes/b.txt" in kwargs["command"]

    def test_bulk_download_tars_then_downloads(self, make_env, tmp_path):
        env = make_env()
        env._mock_sandbox.process.cmd.reset_mock()
        env._mock_sandbox.process.cmd.return_value = {
            "stdout": "", "stderr": "", "exit_code": 0,
        }
        env._mock_sandbox.file_system.download.reset_mock()

        dest = tmp_path / "out.tar"
        env._agentrun_bulk_download(dest)

        # First we should have invoked ``tar cf`` inside the sandbox.
        cmd_calls = env._mock_sandbox.process.cmd.call_args_list
        assert any("tar cf" in c.kwargs.get("command", "") for c in cmd_calls)
        # Then we pull the archive down.
        env._mock_sandbox.file_system.download.assert_called_once()
        download_kwargs = env._mock_sandbox.file_system.download.call_args.kwargs
        assert download_kwargs["save_path"] == str(dest)


# ---------------------------------------------------------------------------
# Test 4 — cleanup: sync_back, then stop (persistent) or delete (ephemeral),
#                   and both branches swallow underlying SDK errors.
# ---------------------------------------------------------------------------


class TestCleanup:
    def test_persistent_cleanup_calls_sync_back_then_stop(self, make_env):
        env = make_env(persistent=True)
        sb = env._mock_sandbox
        env._sync_manager.sync_back = MagicMock(name="sync_back")

        env.cleanup()

        env._sync_manager.sync_back.assert_called_once()
        sb.stop.assert_called_once()
        sb.delete.assert_not_called()
        assert env._sandbox is None

    def test_non_persistent_cleanup_deletes_sandbox(self, make_env):
        env = make_env(persistent=False)
        sb = env._mock_sandbox
        env._sync_manager.sync_back = MagicMock(name="sync_back")

        env.cleanup()

        sb.delete.assert_called_once()
        sb.stop.assert_not_called()

    def test_cleanup_swallows_sync_back_failure(self, make_env):
        env = make_env(persistent=True)
        sb = env._mock_sandbox
        env._sync_manager.sync_back = MagicMock(
            name="sync_back", side_effect=RuntimeError("sync failed")
        )

        # The exception must be swallowed and stop() must still run, so
        # that an unhealthy sync_back never leaks a dangling sandbox.
        env.cleanup()
        sb.stop.assert_called_once()

    def test_cleanup_swallows_stop_failure(self, make_env):
        env = make_env(persistent=True)
        sb = env._mock_sandbox
        sb.stop.side_effect = RuntimeError("stop boom")
        env._sync_manager.sync_back = MagicMock(name="sync_back")

        env.cleanup()  # must not raise
        assert env._sandbox is None


# ---------------------------------------------------------------------------
# Bonus — response normalisation: payload shape variants from the data API
# ---------------------------------------------------------------------------


class TestResponseNormalisation:
    def test_handles_stdout_stderr_shape(self):
        from tools.environments.agentrun import _normalise_cmd_response

        out, code = _normalise_cmd_response(
            {"stdout": "hi", "stderr": "warn", "exit_code": 0}
        )
        assert "hi" in out and "warn" in out
        assert code == 0

    def test_handles_output_shape(self):
        from tools.environments.agentrun import _normalise_cmd_response

        out, code = _normalise_cmd_response({"output": "hi", "exit_code": 1})
        assert out == "hi"
        assert code == 1

    def test_handles_nested_data_shape(self):
        from tools.environments.agentrun import _normalise_cmd_response

        out, code = _normalise_cmd_response(
            {"data": {"stdout": "x", "exit_code": 2}}
        )
        assert "x" in out
        assert code == 2

    def test_handles_none(self):
        from tools.environments.agentrun import _normalise_cmd_response

        out, code = _normalise_cmd_response(None)
        assert out == ""
        assert code == 1


# ---------------------------------------------------------------------------
# Persistence — task_id ↔ sandbox_id store survives across constructions
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_second_construction_reconnects(self, agentrun_sdk, isolated_store, monkeypatch, fake_sandbox):
        # First construction should hit ``create`` and persist the id.
        monkeypatch.setattr("tools.environments.base.is_interrupted", lambda: False)

        from tools.environments.agentrun import AgentRunEnvironment

        env1 = AgentRunEnvironment(
            cwd="/root", timeout=60,
            task_id="resume-me", persistent_filesystem=True,
        )
        first_create_calls = agentrun_sdk.create.call_count
        first_connect_calls = agentrun_sdk.connect.call_count
        env1.cleanup()

        # Second construction with same task_id should reconnect, not
        # re-create.
        agentrun_sdk.create.reset_mock()
        agentrun_sdk.connect.reset_mock()
        agentrun_sdk.connect.return_value = fake_sandbox

        env2 = AgentRunEnvironment(
            cwd="/root", timeout=60,
            task_id="resume-me", persistent_filesystem=True,
        )

        assert agentrun_sdk.connect.call_count == 1
        assert agentrun_sdk.create.call_count == 0
        env2.cleanup()
