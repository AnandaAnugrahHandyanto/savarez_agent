"""Unit tests for the Alibaba Cloud AgentRun cloud sandbox backend.

The real ``agentrun-sdk`` package is intentionally not imported here. We
patch ``sys.modules['agentrun.sandbox']`` with a stand-in module so
``AgentRunEnvironment`` can be constructed and exercised without any
network or credentials. Every test in this file is expected to pass on
CI without the SDK installed and without ``AGENTRUN_*`` env vars.
"""

from __future__ import annotations

import types as _types
from unittest.mock import MagicMock

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


_FAKE_REMOTE_HOME = "/home/code"


def _make_fake_sandbox(
    sandbox_id: str = "sb-fake-123",
    remote_home: str = _FAKE_REMOTE_HOME,
) -> MagicMock:
    """Build a ``MagicMock`` shaped like a Code Interpreter sandbox.

    The default ``process.cmd`` response carries *remote_home* on stdout
    so the adapter's ``_detect_remote_home`` probe resolves to a
    realistic non-root directory.
    """
    sb = MagicMock()
    sb.sandbox_id = sandbox_id
    sb.check_health.return_value = {"status": "ok"}
    sb.process.cmd.return_value = {
        "stdout": remote_home,
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
    fake_container_configuration = MagicMock(name="FakeTemplateContainerConfiguration")

    sandbox_mod = _types.ModuleType("agentrun.sandbox")
    sandbox_mod.Sandbox = fake_sandbox_cls
    sandbox_mod.TemplateType = _FakeTemplateType
    sandbox_mod.TemplateInput = fake_template_input
    sandbox_mod.TemplateContainerConfiguration = fake_container_configuration

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

        # ``cwd`` left to the adapter so that the $HOME probe takes
        # effect; individual tests pass ``cwd=...`` to override.
        kwargs.setdefault("cwd", None)
        env = AgentRunEnvironment(
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
            timeout=60,
            task_id="beta",
            persistent_filesystem=False,
        )

        agentrun_sdk.create_template.assert_called_once()
        # template_name must propagate into the TemplateInput payload.
        # We constructed TemplateInput via a MagicMock — assert the mock
        # was invoked with the right template_name keyword.
        import agentrun.sandbox as patched_sandbox_mod  # type: ignore[import-not-found]

        patched_sandbox_mod.TemplateInput.assert_called_once()
        ti_kwargs = patched_sandbox_mod.TemplateInput.call_args.kwargs
        assert ti_kwargs["template_name"] == "hermes-beta"
        assert ti_kwargs["template_type"] == _FakeTemplateType.CODE_INTERPRETER

    def test_default_image_targets_python_runtime(
        self, agentrun_sdk, isolated_store, monkeypatch
    ):
        """The default ``agentrun_image`` must be a Python-bearing image.

        AgentRun's stock CODE_INTERPRETER template ships with a minimal
        image; the live e2e on 2026-05-12 reproduced a ``Python 3 is not
        available`` error from ``execute_code``. The adapter now defaults
        ``agentrun_image`` to a Python+Node image so that hermes' code
        tooling works out of the box. This test pins the default by name
        AND asserts it is forwarded into ``TemplateContainerConfiguration``
        when a new template is created.
        """
        monkeypatch.setattr("tools.environments.base.is_interrupted", lambda: False)
        agentrun_sdk.get_template.side_effect = RuntimeError("not found")

        from tools.environments.agentrun import (
            _DEFAULT_IMAGE,
            AgentRunEnvironment,
        )

        assert "python" in _DEFAULT_IMAGE.lower(), (
            "Default agentrun image must include Python; got " + _DEFAULT_IMAGE
        )

        AgentRunEnvironment(
            timeout=60, task_id="image-check", persistent_filesystem=False,
        )

        import agentrun.sandbox as patched_sandbox_mod  # type: ignore[import-not-found]

        # TemplateContainerConfiguration must have been instantiated with
        # the default image (not None, not a placeholder).
        patched_sandbox_mod.TemplateContainerConfiguration.assert_called_once()
        cc_kwargs = patched_sandbox_mod.TemplateContainerConfiguration.call_args.kwargs
        assert cc_kwargs.get("image") == _DEFAULT_IMAGE

        # And TemplateInput must have received that container_configuration.
        ti_kwargs = patched_sandbox_mod.TemplateInput.call_args.kwargs
        assert ti_kwargs.get("container_configuration") is not None

    def test_explicit_image_overrides_default(
        self, agentrun_sdk, isolated_store, monkeypatch
    ):
        monkeypatch.setattr("tools.environments.base.is_interrupted", lambda: False)
        agentrun_sdk.get_template.side_effect = RuntimeError("not found")

        from tools.environments.agentrun import AgentRunEnvironment

        AgentRunEnvironment(
            timeout=60, task_id="custom-img", persistent_filesystem=False,
            image="my-registry.example/custom-python:1.0",
        )

        import agentrun.sandbox as patched_sandbox_mod  # type: ignore[import-not-found]

        cc_kwargs = patched_sandbox_mod.TemplateContainerConfiguration.call_args.kwargs
        assert cc_kwargs.get("image") == "my-registry.example/custom-python:1.0"


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
        # cwd resolved to the worker user's $HOME (detected via the
        # mock's process.cmd response).
        assert last_call.kwargs["cwd"] == _FAKE_REMOTE_HOME

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

    def test_sync_targets_detected_home_not_root(self, make_env):
        """File sync MUST honour the probed ``$HOME`` of the worker user.

        AgentRun's CODE_INTERPRETER prebuilt image runs as a non-root
        user, so the legacy hard-coded ``/root/.hermes`` path triggers a
        ``permission denied`` on the very first ``mkdir`` (this was the
        Bug 3 surfaced by the 2026-05-12 live e2e). The adapter now
        records ``_remote_home`` and every sync helper composes its
        target path relative to it.
        """
        env = make_env()
        # Probe should have written the mocked ``/home/code`` into the
        # adapter's _remote_home, and the bulk_download path should use
        # it rather than /root.
        assert env._remote_home == _FAKE_REMOTE_HOME
        assert env.cwd == _FAKE_REMOTE_HOME

        env._mock_sandbox.process.cmd.reset_mock()
        env._mock_sandbox.process.cmd.return_value = {
            "stdout": "", "stderr": "", "exit_code": 0,
        }
        env._agentrun_bulk_download(env.__class__.__dict__.get(
            "_throwaway_path", __import__("pathlib").Path("/tmp/throwaway.tar")
        ))
        tar_cmds = [
            c.kwargs.get("command", "")
            for c in env._mock_sandbox.process.cmd.call_args_list
            if "tar cf" in c.kwargs.get("command", "")
        ]
        assert tar_cmds, "expected a tar command"
        # Sandbox-side tar target must reference the probed HOME, not /root.
        joined = " ".join(tar_cmds)
        assert "home/code/.hermes" in joined
        assert "/root/.hermes" not in joined

    def test_remote_home_falls_back_when_probe_fails(
        self, agentrun_sdk, isolated_store, monkeypatch, fake_sandbox
    ):
        """If the ``$HOME`` probe blows up we fall back to ``/workspace``.

        Crashing the adapter on home-detection failure would tear every
        AgentRun session down on transient errors; the fallback keeps
        the backend usable (and writes still work because /workspace is
        writable in every prebuilt template).
        """
        monkeypatch.setattr("tools.environments.base.is_interrupted", lambda: False)

        # First cmd() call (the $HOME probe) raises; subsequent calls
        # (init_session, file sync, etc.) return a clean response.
        clean = {"stdout": "", "stderr": "", "exit_code": 0}
        fake_sandbox.process.cmd.side_effect = [
            RuntimeError("network blip"),
            clean, clean, clean, clean, clean, clean,
        ]

        from tools.environments.agentrun import (
            _FALLBACK_CWD,
            AgentRunEnvironment,
        )

        env = AgentRunEnvironment(
            timeout=60, task_id="fallback-task", persistent_filesystem=False,
        )

        assert env._remote_home == _FALLBACK_CWD
        assert env.cwd == _FALLBACK_CWD


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
    def test_second_construction_reconnects(
        self, agentrun_sdk, isolated_store, monkeypatch, fake_sandbox,
    ):
        # First construction should hit ``create`` and persist the id.
        monkeypatch.setattr("tools.environments.base.is_interrupted", lambda: False)

        from tools.environments.agentrun import AgentRunEnvironment

        env1 = AgentRunEnvironment(
            timeout=60,
            task_id="resume-me", persistent_filesystem=True,
        )
        env1.cleanup()

        # Second construction with same task_id should reconnect, not
        # re-create.
        agentrun_sdk.create.reset_mock()
        agentrun_sdk.connect.reset_mock()
        agentrun_sdk.connect.return_value = fake_sandbox

        env2 = AgentRunEnvironment(
            timeout=60,
            task_id="resume-me", persistent_filesystem=True,
        )

        assert agentrun_sdk.connect.call_count == 1
        assert agentrun_sdk.create.call_count == 0
        env2.cleanup()
