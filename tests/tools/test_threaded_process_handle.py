"""Tests for _ThreadedProcessHandle — the adapter for SDK backends."""

import os
import threading
import time

from tools.environments.base import (
    RESOURCE_LIFETIME_POLICY,
    BaseEnvironment,
    _ThreadedProcessHandle,
)


class _DummyEnvironment(BaseEnvironment):
    def _run_bash(self, *args, **kwargs):
        raise NotImplementedError

    def cleanup(self):
        pass


class TestBasicExecution:
    def test_successful_execution(self):
        def exec_fn():
            return ("hello world", 0)

        handle = _ThreadedProcessHandle(exec_fn)
        handle.wait(timeout=5)

        assert handle.returncode == 0
        output = handle.stdout.read()
        assert "hello world" in output

    def test_nonzero_exit_code(self):
        def exec_fn():
            return ("error occurred", 42)

        handle = _ThreadedProcessHandle(exec_fn)
        handle.wait(timeout=5)

        assert handle.returncode == 42
        output = handle.stdout.read()
        assert "error occurred" in output

    def test_exception_in_exec_fn(self):
        def exec_fn():
            raise RuntimeError("boom")

        handle = _ThreadedProcessHandle(exec_fn)
        handle.wait(timeout=5)

        assert handle.returncode == 1

    def test_empty_output(self):
        def exec_fn():
            return ("", 0)

        handle = _ThreadedProcessHandle(exec_fn)
        handle.wait(timeout=5)

        assert handle.returncode == 0
        output = handle.stdout.read()
        assert output == ""


class TestPolling:
    def test_poll_returns_none_while_running(self):
        event = threading.Event()

        def exec_fn():
            event.wait(timeout=5)
            return ("done", 0)

        handle = _ThreadedProcessHandle(exec_fn)
        assert handle.poll() is None

        event.set()
        handle.wait(timeout=5)
        assert handle.poll() == 0

    def test_poll_returns_returncode_when_done(self):
        def exec_fn():
            return ("ok", 0)

        handle = _ThreadedProcessHandle(exec_fn)
        handle.wait(timeout=5)
        assert handle.poll() == 0


class TestCancelFn:
    def test_cancel_fn_called_on_kill(self):
        called = threading.Event()

        def cancel():
            called.set()

        def exec_fn():
            time.sleep(10)
            return ("", 0)

        handle = _ThreadedProcessHandle(exec_fn, cancel_fn=cancel)
        handle.kill()
        assert called.is_set()

    def test_kill_closes_synthetic_stdout_writer_without_waiting_for_worker(self):
        """SDK-backed handles must not hold pipe fds forever when
        cancellation does not immediately stop the worker thread.
        """
        started = threading.Event()

        def exec_fn():
            started.set()
            time.sleep(10)
            return ("late output", 0)

        handle = _ThreadedProcessHandle(exec_fn, cancel_fn=None)
        assert started.wait(timeout=1)

        handle.kill()

        assert handle.stdout.read() == ""

    def test_cancel_fn_none_is_safe(self):
        def exec_fn():
            return ("ok", 0)

        handle = _ThreadedProcessHandle(exec_fn, cancel_fn=None)
        handle.kill()  # should not raise
        handle.wait(timeout=5)
        assert handle.returncode == 0

    def test_cancel_fn_exception_swallowed(self):
        def cancel():
            raise RuntimeError("cancel failed")

        def exec_fn():
            return ("ok", 0)

        handle = _ThreadedProcessHandle(exec_fn, cancel_fn=cancel)
        handle.kill()  # should not raise despite cancel raising
        handle.wait(timeout=5)


class TestStdoutPipe:
    def test_stdout_is_readable(self):
        def exec_fn():
            return ("line1\nline2\nline3\n", 0)

        handle = _ThreadedProcessHandle(exec_fn)
        handle.wait(timeout=5)

        lines = handle.stdout.readlines()
        assert len(lines) == 3
        assert lines[0] == "line1\n"

    def test_stdout_iterable(self):
        def exec_fn():
            return ("a\nb\nc\n", 0)

        handle = _ThreadedProcessHandle(exec_fn)
        handle.wait(timeout=5)

        collected = list(handle.stdout)
        assert len(collected) == 3

    def test_unicode_output(self):
        def exec_fn():
            return ("hello 世界 🌍\n", 0)

        handle = _ThreadedProcessHandle(exec_fn)
        handle.wait(timeout=5)

        output = handle.stdout.read()
        assert "世界" in output
        assert "🌍" in output


class TestWaitForProcessFdCleanup:
    def test_resource_lifetime_policy_is_explicit_and_versioned(self):
        assert RESOURCE_LIFETIME_POLICY.version == 1
        assert RESOURCE_LIFETIME_POLICY.drain_join_timeout_seconds == 2.0
        assert RESOURCE_LIFETIME_POLICY.poll_interval_seconds == 0.2

    class _NeverExitsProc:
        def __init__(self):
            self.read_fd, self.write_fd = os.pipe()
            self.stdout = os.fdopen(self.read_fd, "rb", buffering=0)
            self.returncode = None

        def poll(self):
            return self.returncode

        def kill(self):
            self.returncode = -9
            try:
                os.close(self.write_fd)
            except OSError:
                pass

    def test_wait_for_process_closes_stdout_on_timeout(self):
        env = _DummyEnvironment(cwd=".", timeout=1)
        proc = self._NeverExitsProc()

        result = env._wait_for_process(proc, timeout=0)

        assert result["returncode"] == 124
        assert proc.stdout.closed
