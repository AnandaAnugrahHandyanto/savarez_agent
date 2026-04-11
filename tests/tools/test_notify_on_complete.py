"""Tests for notify_on_complete background process feature.

Covers:
  - ProcessSession.notify_on_complete field
  - ProcessRegistry.completion_queue population on _move_to_finished()
  - Checkpoint persistence of notify_on_complete
  - Terminal tool schema includes notify_on_complete
  - Terminal tool handler passes notify_on_complete through
"""

import json
import os
import queue
import time
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tools.process_registry import (
    ProcessRegistry,
    ProcessSession,
)


@pytest.fixture()
def registry():
    """Create a fresh ProcessRegistry."""
    return ProcessRegistry()


def _make_session(
    sid="proc_test_notify",
    command="echo hello",
    task_id="t1",
    exited=False,
    exit_code=None,
    output="",
    notify_on_complete=False,
) -> ProcessSession:
    s = ProcessSession(
        id=sid,
        command=command,
        task_id=task_id,
        started_at=time.time(),
        exited=exited,
        exit_code=exit_code,
        output_buffer=output,
        notify_on_complete=notify_on_complete,
    )
    return s


# =========================================================================
# ProcessSession field
# =========================================================================

class TestProcessSessionField:
    def test_default_false(self):
        s = ProcessSession(id="proc_1", command="echo hi")
        assert s.notify_on_complete is False

    def test_set_true(self):
        s = ProcessSession(id="proc_1", command="echo hi", notify_on_complete=True)
        assert s.notify_on_complete is True


# =========================================================================
# Completion queue
# =========================================================================

class TestCompletionQueue:
    def test_queue_exists(self, registry):
        assert hasattr(registry, "completion_queue")
        assert registry.completion_queue.empty()

    def test_move_to_finished_no_notify(self, registry):
        """Processes without notify_on_complete don't enqueue."""
        s = _make_session(notify_on_complete=False, output="done")
        s.exited = True
        s.exit_code = 0
        registry._running[s.id] = s
        with patch.object(registry, "_write_checkpoint"):
            registry._move_to_finished(s)
        assert registry.completion_queue.empty()

    def test_move_to_finished_with_notify(self, registry):
        """Processes with notify_on_complete push to queue."""
        s = _make_session(
            notify_on_complete=True,
            output="build succeeded",
            exit_code=0,
        )
        s.exited = True
        s.exit_code = 0
        registry._running[s.id] = s
        with patch.object(registry, "_write_checkpoint"):
            registry._move_to_finished(s)

        assert not registry.completion_queue.empty()
        completion = registry.completion_queue.get_nowait()
        assert completion["session_id"] == s.id
        assert completion["command"] == "echo hello"
        assert completion["exit_code"] == 0
        assert "build succeeded" in completion["output"]

    def test_move_to_finished_nonzero_exit(self, registry):
        """Nonzero exit codes are captured correctly."""
        s = _make_session(
            notify_on_complete=True,
            output="FAILED",
            exit_code=1,
        )
        s.exited = True
        s.exit_code = 1
        registry._running[s.id] = s
        with patch.object(registry, "_write_checkpoint"):
            registry._move_to_finished(s)

        completion = registry.completion_queue.get_nowait()
        assert completion["exit_code"] == 1
        assert "FAILED" in completion["output"]

    def test_move_to_finished_idempotent_no_duplicate(self, registry):
        """Calling _move_to_finished twice must NOT enqueue two notifications.

        Regression test: kill_process() and the reader thread can both call
        _move_to_finished() for the same session, producing duplicate
        [SYSTEM: Background process ...] messages.
        """
        s = _make_session(notify_on_complete=True, output="done", exit_code=-15)
        s.exited = True
        s.exit_code = -15
        registry._running[s.id] = s
        with patch.object(registry, "_write_checkpoint"):
            registry._move_to_finished(s)  # first call — should enqueue
            s.exit_code = 143  # reader thread updates exit code
            registry._move_to_finished(s)  # second call — should be no-op

        assert registry.completion_queue.qsize() == 1
        completion = registry.completion_queue.get_nowait()
        assert completion["exit_code"] == -15  # from the first (kill) call

    def test_output_truncated_to_2000(self, registry):
        """Long output is truncated to last 2000 chars."""
        long_output = "x" * 5000
        s = _make_session(
            notify_on_complete=True,
            output=long_output,
        )
        s.exited = True
        s.exit_code = 0
        registry._running[s.id] = s
        with patch.object(registry, "_write_checkpoint"):
            registry._move_to_finished(s)

        completion = registry.completion_queue.get_nowait()
        assert len(completion["output"]) == 2000

    def test_multiple_completions_queued(self, registry):
        """Multiple notify processes all push to the same queue."""
        for i in range(3):
            s = _make_session(
                sid=f"proc_{i}",
                notify_on_complete=True,
                output=f"output_{i}",
            )
            s.exited = True
            s.exit_code = 0
            registry._running[s.id] = s
            with patch.object(registry, "_write_checkpoint"):
                registry._move_to_finished(s)

        completions = []
        while not registry.completion_queue.empty():
            completions.append(registry.completion_queue.get_nowait())
        assert len(completions) == 3
        ids = {c["session_id"] for c in completions}
        assert ids == {"proc_0", "proc_1", "proc_2"}


# =========================================================================
# Checkpoint persistence
# =========================================================================

class TestCheckpointNotify:
    def test_checkpoint_includes_notify(self, registry, tmp_path):
        with patch("tools.process_registry.CHECKPOINT_PATH", tmp_path / "procs.json"):
            s = _make_session(notify_on_complete=True)
            registry._running[s.id] = s
            registry._write_checkpoint()

            data = json.loads((tmp_path / "procs.json").read_text())
            assert len(data) == 1
            assert data[0]["notify_on_complete"] is True

    def test_checkpoint_without_notify(self, registry, tmp_path):
        with patch("tools.process_registry.CHECKPOINT_PATH", tmp_path / "procs.json"):
            s = _make_session(notify_on_complete=False)
            registry._running[s.id] = s
            registry._write_checkpoint()

            data = json.loads((tmp_path / "procs.json").read_text())
            assert data[0]["notify_on_complete"] is False

    def test_recover_preserves_notify(self, registry, tmp_path):
        checkpoint = tmp_path / "procs.json"
        checkpoint.write_text(json.dumps([{
            "session_id": "proc_live",
            "command": "sleep 999",
            "pid": os.getpid(),
            "task_id": "t1",
            "notify_on_complete": True,
        }]))
        with patch("tools.process_registry.CHECKPOINT_PATH", checkpoint):
            recovered = registry.recover_from_checkpoint()
            assert recovered == 1
            s = registry.get("proc_live")
            assert s.notify_on_complete is True

    def test_recover_requeues_notify_watchers(self, registry, tmp_path):
        checkpoint = tmp_path / "procs.json"
        checkpoint.write_text(json.dumps([{
            "session_id": "proc_live",
            "command": "sleep 999",
            "pid": os.getpid(),
            "task_id": "t1",
            "session_key": "sk1",
            "watcher_platform": "telegram",
            "watcher_chat_id": "123",
            "watcher_user_id": "u123",
            "watcher_user_name": "alice",
            "watcher_thread_id": "42",
            "watcher_interval": 5,
            "notify_on_complete": True,
        }]))
        with patch("tools.process_registry.CHECKPOINT_PATH", checkpoint):
            recovered = registry.recover_from_checkpoint()
            assert recovered == 1
            assert len(registry.pending_watchers) == 1
            assert registry.pending_watchers[0]["notify_on_complete"] is True
            assert registry.pending_watchers[0]["user_id"] == "u123"
            assert registry.pending_watchers[0]["user_name"] == "alice"

    def test_recover_defaults_false(self, registry, tmp_path):
        """Old checkpoint entries without the field default to False."""
        checkpoint = tmp_path / "procs.json"
        checkpoint.write_text(json.dumps([{
            "session_id": "proc_live",
            "command": "sleep 999",
            "pid": os.getpid(),
            "task_id": "t1",
        }]))
        with patch("tools.process_registry.CHECKPOINT_PATH", checkpoint):
            recovered = registry.recover_from_checkpoint()
            assert recovered == 1
            s = registry.get("proc_live")
            assert s.notify_on_complete is False


# =========================================================================
# Terminal tool schema
# =========================================================================

class TestTerminalSchema:
    def test_schema_has_notify_on_complete(self):
        from tools.terminal_tool import TERMINAL_SCHEMA
        props = TERMINAL_SCHEMA["parameters"]["properties"]
        assert "notify_on_complete" in props
        assert props["notify_on_complete"]["type"] == "boolean"
        assert props["notify_on_complete"]["default"] is False

    def test_handler_passes_notify(self):
        """_handle_terminal passes notify_on_complete to terminal_tool."""
        from tools.terminal_tool import _handle_terminal
        with patch("tools.terminal_tool.terminal_tool", return_value='{"ok":true}') as mock_tt:
            _handle_terminal(
                {"command": "echo hi", "background": True, "notify_on_complete": True},
                task_id="t1",
            )
            _, kwargs = mock_tt.call_args
            assert kwargs["notify_on_complete"] is True


# =========================================================================
# Combined notify_on_complete + check_interval watcher registration
# =========================================================================

class TestNotifyWithCheckInterval:
    """notify_on_complete=True must survive into the check_interval watcher dict."""

    @pytest.fixture(autouse=True)
    def _clear_active_envs(self):
        """Ensure terminal_tool module state is clean before and after each test."""
        import tools.terminal_tool as tt
        tt._active_environments.clear()
        yield
        tt._active_environments.clear()

    def _fake_gse(self, key, default=""):
        return {
            "HERMES_SESSION_PLATFORM": "telegram",
            "HERMES_SESSION_CHAT_ID": "chat_1",
            "HERMES_SESSION_THREAD_ID": "",
            "HERMES_SESSION_USER_ID": "u1",
            "HERMES_SESSION_USER_NAME": "bob",
        }.get(key, default)

    def _make_registry(self, sid="proc_combined"):
        fake_session = MagicMock()
        fake_session.id = sid
        fake_session.pid = 99
        fake_session.notify_on_complete = False

        fake_registry = MagicMock()
        fake_registry.pending_watchers = []
        fake_registry.spawn_local.return_value = fake_session
        return fake_registry

    def test_check_interval_watcher_includes_notify_on_complete(self):
        """When both notify_on_complete=True and check_interval are set, the
        check_interval watcher appended to pending_watchers must carry
        notify_on_complete=True so _run_process_watcher notifies on completion."""
        from tools.terminal_tool import terminal_tool

        fake_registry = self._make_registry("proc_combined")

        with (
            patch("tools.terminal_tool._check_all_guards",
                  return_value={"approved": True}),
            patch("tools.terminal_tool._create_environment",
                  return_value=MagicMock()),
            patch("tools.process_registry.process_registry", fake_registry),
            patch("tools.approval.get_current_session_key", return_value="sk1"),
            patch("gateway.session_context.get_session_env", self._fake_gse),
        ):
            terminal_tool(
                command="sleep 60",
                background=True,
                notify_on_complete=True,
                check_interval=30,
                task_id="t_combined",
            )

        # Two watcher entries: the fast notify_on_complete watcher (interval=5)
        # and the user-requested check_interval watcher.
        assert len(fake_registry.pending_watchers) == 2

        check_interval_watcher = next(
            w for w in fake_registry.pending_watchers if w["check_interval"] >= 30
        )
        assert check_interval_watcher["notify_on_complete"] is True

    def test_notify_only_no_check_interval_watcher_registered(self):
        """When only notify_on_complete=True (no check_interval), only the fast
        notify watcher (interval=5) is added — no second watcher."""
        from tools.terminal_tool import terminal_tool

        fake_registry = self._make_registry("proc_notify_only")

        with (
            patch("tools.terminal_tool._check_all_guards",
                  return_value={"approved": True}),
            patch("tools.terminal_tool._create_environment",
                  return_value=MagicMock()),
            patch("tools.process_registry.process_registry", fake_registry),
            patch("tools.approval.get_current_session_key", return_value="sk1"),
            patch("gateway.session_context.get_session_env", self._fake_gse),
        ):
            terminal_tool(
                command="sleep 60",
                background=True,
                notify_on_complete=True,
                task_id="t_notify_only",
            )

        assert len(fake_registry.pending_watchers) == 1
        assert fake_registry.pending_watchers[0]["notify_on_complete"] is True
        assert fake_registry.pending_watchers[0]["check_interval"] == 5


# =========================================================================
# Code execution blocked params
# =========================================================================

class TestCodeExecutionBlocked:
    def test_notify_on_complete_blocked_in_sandbox(self):
        from tools.code_execution_tool import _TERMINAL_BLOCKED_PARAMS
        assert "notify_on_complete" in _TERMINAL_BLOCKED_PARAMS
