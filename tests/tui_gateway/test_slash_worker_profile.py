"""Tests for profile propagation to slash workers (fixes #41517).

When Desktop/Dashboard starts a session under a non-default profile, the
slash worker subprocess must inherit that profile via HERMES_HOME and
HERMES_PROFILE env vars so it resolves the correct config, skills, memory,
and session DB.
"""

import json
import os
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# _SlashWorker profile propagation
# ---------------------------------------------------------------------------

class TestSlashWorkerProfilePropagation:
    """Verify _SlashWorker passes profile info to its subprocess."""

    def test_argv_includes_profile_when_provided(self):
        """--profile <name> appears in argv when profile is set."""
        from tui_gateway.server import _SlashWorker

        captured = {}

        class FakeProc:
            def __init__(self, cmd, **kwargs):
                captured["cmd"] = list(cmd)
                captured["env"] = kwargs.get("env", {})
                self.stdin = None
                self.stdout = []
                self.stderr = []
                self.pid = 1
                self.returncode = None

            def poll(self):
                return None

            def terminate(self):
                pass

            def wait(self, timeout=None):
                return 0

            def kill(self):
                pass

        with patch("subprocess.Popen", FakeProc):
            _SlashWorker("test-key", "test-model", profile="myprofile")

        cmd = captured["cmd"]
        assert "--profile" in cmd
        idx = cmd.index("--profile")
        assert cmd[idx + 1] == "myprofile"

    def test_env_sets_hermes_home_when_profile_home_provided(self):
        """HERMES_HOME is set to profile_home in the worker's env."""
        from tui_gateway.server import _SlashWorker

        captured = {}

        class FakeProc:
            def __init__(self, cmd, **kwargs):
                captured["env"] = kwargs.get("env", {})
                self.stdin = None
                self.stdout = []
                self.stderr = []
                self.pid = 1
                self.returncode = None

            def poll(self):
                return None

            def terminate(self):
                pass

            def wait(self, timeout=None):
                return 0

            def kill(self):
                pass

        with patch("subprocess.Popen", FakeProc):
            _SlashWorker(
                "test-key", "test-model",
                profile="myprofile",
                profile_home="/home/user/.hermes/profiles/myprofile",
            )

        env = captured["env"]
        assert env["HERMES_HOME"] == "/home/user/.hermes/profiles/myprofile"
        assert env["HERMES_PROFILE"] == "myprofile"

    def test_no_profile_args_when_none(self):
        """No --profile or HERMES_HOME/HERMES_PROFILE when profile is None."""
        from tui_gateway.server import _SlashWorker

        captured = {}

        class FakeProc:
            def __init__(self, cmd, **kwargs):
                captured["cmd"] = list(cmd)
                captured["env"] = kwargs.get("env", {})
                self.stdin = None
                self.stdout = []
                self.stderr = []
                self.pid = 1
                self.returncode = None

            def poll(self):
                return None

            def terminate(self):
                pass

            def wait(self, timeout=None):
                return 0

            def kill(self):
                pass

        with patch("subprocess.Popen", FakeProc):
            _SlashWorker("test-key", "test-model")

        cmd = captured["cmd"]
        assert "--profile" not in cmd
        env = captured["env"]
        assert "HERMES_PROFILE" not in env or env.get("HERMES_PROFILE") == os.environ.get("HERMES_PROFILE")
        # HERMES_HOME should not be overridden by the worker
        assert env.get("HERMES_HOME") == os.environ.get("HERMES_HOME")


# ---------------------------------------------------------------------------
# _init_session stores profile info on session dict
# ---------------------------------------------------------------------------

class TestInitSessionProfileStorage:
    """_init_session stores profile_name and profile_home on the session dict."""

    def test_init_session_stores_profile_info(self):
        from tui_gateway.server import _sessions, _init_session

        class FakeAgent:
            model = "test-model"

        class FakeWorker:
            def __init__(self, *a, **kw):
                pass

            def close(self):
                pass

        with patch("tui_gateway.server._SlashWorker", FakeWorker):
            sid = "test-init-profile"
            _init_session(
                sid, "session-key", FakeAgent(), [],
                profile_name="myprofile",
                profile_home="/home/user/.hermes/profiles/myprofile",
            )

        assert sid in _sessions
        assert _sessions[sid]["profile_name"] == "myprofile"
        assert _sessions[sid]["profile_home"] == "/home/user/.hermes/profiles/myprofile"

        # Cleanup
        _sessions.pop(sid, None)

    def test_init_session_defaults_profile_to_none(self):
        from tui_gateway.server import _sessions, _init_session

        class FakeAgent:
            model = "test-model"

        class FakeWorker:
            def __init__(self, *a, **kw):
                pass

            def close(self):
                pass

        with patch("tui_gateway.server._SlashWorker", FakeWorker):
            sid = "test-init-default"
            _init_session(sid, "session-key", FakeAgent(), [])

        assert _sessions[sid]["profile_name"] is None
        assert _sessions[sid]["profile_home"] is None

        # Cleanup
        _sessions.pop(sid, None)
