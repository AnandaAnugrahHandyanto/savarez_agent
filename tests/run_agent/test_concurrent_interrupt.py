"""Tests for interrupt handling in concurrent tool execution."""

import concurrent.futures
import threading
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _isolate_hermes(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    (tmp_path / ".hermes").mkdir(exist_ok=True)


def _make_agent(monkeypatch):
    """Create a minimal AIAgent-like object with just the methods under test."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("HERMES_INFERENCE_PROVIDER", "")
    # Avoid full AIAgent init — just import the class and build a stub
    import run_agent as _ra

    class _Stub:
        _interrupt_requested = False
        _interrupt_message = None
        # Bind to this thread's ident so interrupt() targets a real tid.
        _execution_thread_id = threading.current_thread().ident
        _interrupt_thread_signal_pending = False
        log_prefix = ""
        quiet_mode = True
        verbose_logging = False
        log_prefix_chars = 200
        _checkpoint_mgr = MagicMock(enabled=False)
        _subdirectory_hints = MagicMock(check_tool_call=MagicMock(return_value=""))
        tool_progress_callback = None
        tool_start_callback = None
        tool_complete_callback = None
        _todo_store = MagicMock()
        _session_db = None
        valid_tool_names = set()
        _turns_since_memory = 0
        _iters_since_skill = 0
        _current_tool = None
        _last_activity = 0
        _print_fn = print
        _tool_guardrails = MagicMock(
            before_call=MagicMock(
                return_value=SimpleNamespace(allows_execution=True)
            )
        )
        # Worker-thread tracking state mirrored from AIAgent.__init__ so the
        # real interrupt() method can fan out to concurrent-tool workers.
        _active_children: list = []

        def __init__(self):
            # Instance-level (not class-level) so each test gets a fresh set.
            self._tool_worker_threads: set = set()
            self._tool_worker_threads_lock = threading.Lock()
            self._active_children_lock = threading.Lock()
            self._active_concurrent_batch = None
            self._active_concurrent_batch_lock = threading.Lock()
            self._concurrent_batch_seq = 0

        def _touch_activity(self, desc):
            self._last_activity = time.time()

        def _vprint(self, msg, force=False):
            pass

        def _safe_print(self, msg):
            pass

        def _should_emit_quiet_tool_messages(self):
            return False

        def _should_start_quiet_spinner(self):
            return False

        def _has_stream_consumers(self):
            return False

        def _guardrail_block_result(self, decision):
            raise AssertionError("guardrail block path should not be used in this test")

        def _append_guardrail_observation(self, function_name, function_args, function_result, failed=False):
            return function_result

    stub = _Stub()
    # Bind the real methods under test
    stub._execute_tool_calls_concurrent = _ra.AIAgent._execute_tool_calls_concurrent.__get__(stub)
    stub.interrupt = _ra.AIAgent.interrupt.__get__(stub)
    stub.clear_interrupt = _ra.AIAgent.clear_interrupt.__get__(stub)
    # /steer injection (added in PR #12116) fires after every concurrent
    # tool batch. Stub it as a no-op — this test exercises interrupt
    # fanout, not steer injection.
    stub._apply_pending_steer_to_tool_results = lambda *a, **kw: None
    stub._invoke_tool = MagicMock(side_effect=lambda *a, **kw: '{"ok": true}')
    return stub


class _FakeToolCall:
    def __init__(self, name, args="{}", call_id="tc_1"):
        self.function = MagicMock(name=name, arguments=args)
        self.function.name = name
        self.id = call_id


class _FakeAssistantMsg:
    def __init__(self, tool_calls):
        self.tool_calls = tool_calls




def test_concurrent_preflight_interrupt_skips_all(monkeypatch):
    """When _interrupt_requested is already set before concurrent execution,
    all tools are skipped with cancellation messages."""
    agent = _make_agent(monkeypatch)
    agent._interrupt_requested = True

    tc1 = _FakeToolCall("tool_a", call_id="tc_a")
    tc2 = _FakeToolCall("tool_b", call_id="tc_b")
    msg = _FakeAssistantMsg([tc1, tc2])
    messages = []

    agent._execute_tool_calls_concurrent(msg, messages, "test_task")

    assert len(messages) == 2
    assert "skipped due to user interrupt" in messages[0]["content"]
    assert "skipped due to user interrupt" in messages[1]["content"]
    # _invoke_tool should never have been called
    agent._invoke_tool.assert_not_called()




def test_clear_interrupt_clears_worker_tids(monkeypatch):
    """After clear_interrupt(), stale worker-tid bits must be cleared so the
    next turn's tools — which may be scheduled onto recycled tids — don't
    see a false interrupt."""
    from tools.interrupt import is_interrupted, set_interrupt

    agent = _make_agent(monkeypatch)
    # Simulate a worker having registered but not yet exited cleanly (e.g. a
    # hypothetical bug in the tear-down).  Put a fake tid in the set and
    # flag it interrupted.
    fake_tid = threading.current_thread().ident  # use real tid so is_interrupted can see it
    with agent._tool_worker_threads_lock:
        agent._tool_worker_threads.add(fake_tid)
    set_interrupt(True, fake_tid)
    assert is_interrupted() is True  # sanity

    agent.clear_interrupt()

    assert is_interrupted() is False, (
        "clear_interrupt() did not clear the interrupt bit for a tracked "
        "worker tid — stale interrupt can leak into the next turn"
    )


def test_concurrent_interrupt_detaches_running_workers_and_returns_fast(monkeypatch):
    """Interrupting a running concurrent batch must return promptly.

    Regression target: ``_execute_tool_calls_concurrent`` used a ``with
    ThreadPoolExecutor(...)`` block, so even after cancelling pending futures it
    still waited for already-running workers when ``__exit__`` called
    ``shutdown(wait=True)``. That made /stop look successful while the turn was
    still blocked on non-interruptible tools.
    """
    agent = _make_agent(monkeypatch)
    started = threading.Event()
    release = threading.Event()
    shutdown_calls: list[tuple[bool, bool]] = []

    real_shutdown = concurrent.futures.ThreadPoolExecutor.shutdown

    def tracking_shutdown(self, wait=True, cancel_futures=False):
        shutdown_calls.append((wait, cancel_futures))
        return real_shutdown(self, wait=wait, cancel_futures=cancel_futures)

    monkeypatch.setattr(
        concurrent.futures.ThreadPoolExecutor,
        "shutdown",
        tracking_shutdown,
    )

    def _slow_tool(*args, **kwargs):
        started.set()
        release.wait(timeout=5.0)
        return '{"ok": true, "late": true}'

    agent._invoke_tool = MagicMock(side_effect=_slow_tool)

    tc1 = _FakeToolCall("tool_a", call_id="tc_a")
    tc2 = _FakeToolCall("tool_b", call_id="tc_b")
    msg = _FakeAssistantMsg([tc1, tc2])
    messages = []

    runner = threading.Thread(
        target=agent._execute_tool_calls_concurrent,
        args=(msg, messages, "test_task"),
    )
    t0 = time.time()
    runner.start()

    assert started.wait(timeout=1.0), "concurrent worker never started"
    agent.interrupt("stop")
    runner.join(timeout=1.0)
    elapsed = time.time() - t0

    assert not runner.is_alive(), (
        f"concurrent interrupt path blocked for {elapsed:.2f}s waiting on a "
        "running worker; it should detach the batch and return promptly"
    )
    assert elapsed < 1.0, (
        f"interrupt path took {elapsed:.2f}s — expected prompt return after "
        "detaching the concurrent batch"
    )
    assert len(messages) == 2
    contents = [m["content"] for m in messages]
    assert all("skipped due to user interrupt" in content for content in contents)
    assert any(
        wait is False and cancel_futures is True
        for wait, cancel_futures in shutdown_calls
    ), (
        "interrupt never triggered a non-blocking executor shutdown; a live "
        "worker can still hold the turn open if shutdown(wait=True) wins"
    )

    # Let the detached worker threads unwind. Their late results must not
    # replace the interrupt placeholders already emitted to the model.
    release.set()
    time.sleep(0.05)
    assert [m["content"] for m in messages] == contents
