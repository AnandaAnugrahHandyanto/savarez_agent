"""Tests for shell.exec fail-closed behaviour in the TUI gateway.

shell.exec gates dangerous commands via tools.approval.detect_dangerous_command.
If that module cannot be imported the gate must fail CLOSED (refuse to run)
rather than swallowing the ImportError and executing the command unchecked.
"""

import sys
import types
from unittest.mock import MagicMock, patch

from tui_gateway import server


def _shell_exec(params):
    """Dispatch shell.exec through the method registry, as the server does."""
    return server._methods["shell.exec"](1, params)


def test_fail_closed_when_approval_module_unavailable():
    """ImportError on tools.approval must block, not execute."""
    run_mock = MagicMock()
    # sys.modules[name] = None makes `from name import ...` raise ImportError.
    with patch.dict(sys.modules, {"tools.approval": None}), \
            patch.object(server.subprocess, "run", run_mock):
        resp = _shell_exec({"command": "echo hi"})

    assert "error" in resp
    assert resp["error"]["code"] == 4005
    assert "approval module unavailable" in resp["error"]["message"]
    run_mock.assert_not_called()  # command must not run when the gate is down


def test_dangerous_command_blocked_without_executing():
    """A dangerous verdict blocks and never reaches subprocess.run."""
    fake = types.ModuleType("tools.approval")
    fake.detect_dangerous_command = lambda cmd: (True, "recursive-delete", "recursive delete")
    run_mock = MagicMock()
    with patch.dict(sys.modules, {"tools.approval": fake}), \
            patch.object(server.subprocess, "run", run_mock):
        resp = _shell_exec({"command": "rm -rf /tmp/x"})

    assert resp["error"]["code"] == 4005
    assert "recursive delete" in resp["error"]["message"]
    run_mock.assert_not_called()


def test_safe_command_executes_when_approval_available():
    """A non-dangerous verdict proceeds to execution (gate open)."""
    fake = types.ModuleType("tools.approval")
    fake.detect_dangerous_command = lambda cmd: (False, None, None)
    run_mock = MagicMock(
        return_value=types.SimpleNamespace(stdout="hi\n", stderr="", returncode=0)
    )
    with patch.dict(sys.modules, {"tools.approval": fake}), \
            patch.object(server.subprocess, "run", run_mock):
        resp = _shell_exec({"command": "echo hi"})

    assert "result" in resp
    assert resp["result"]["code"] == 0
    assert resp["result"]["stdout"] == "hi\n"
    run_mock.assert_called_once()


def test_empty_command_rejected():
    resp = _shell_exec({"command": ""})
    assert resp["error"]["code"] == 4004
