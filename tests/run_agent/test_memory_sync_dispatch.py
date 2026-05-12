"""Regression guard for #24453 — external memory sync at end-of-turn must
NOT block ``run_conversation`` from returning.

Before this fix, ``run_conversation`` called
``self._sync_external_memory_for_turn(...)`` inline.  With the Hindsight
external memory provider, that call does a daemon connect plus LLM-based
entity resolution, which routinely takes 30-50s of wall time per turn.
The SSE writer was therefore parked between ``response.output_text.delta``
(which streamed the assistant reply quickly) and ``response.completed``
(which couldn't fire until ``run_conversation`` returned).  The user saw
their reply text, then a 30+ second loading spinner.

The fix introduces ``_dispatch_memory_sync_for_turn``: a thin dispatcher
that spawns a daemon thread targeting the existing
``_sync_external_memory_for_turn`` worker.  The dispatcher returns
near-instantly, ``run_conversation`` continues, and the SSE writer can
emit ``response.completed`` immediately.  The worker is unchanged and
its existing behaviour (interrupt guard, no-manager no-op, exception
swallowing) is still exercised by ``test_memory_sync_interrupted.py``.

These tests cover the dispatcher contract directly.
"""
import threading
import time
from unittest.mock import MagicMock, patch


def _bare_agent():
    """Build a bare ``AIAgent`` with only the attributes the dispatcher
    and worker touch — same pattern as ``test_memory_sync_interrupted``.
    """
    from run_agent import AIAgent

    agent = AIAgent.__new__(AIAgent)
    agent._memory_manager = MagicMock()
    agent.session_id = "test_session_dispatch"
    return agent


class TestDispatchMemorySyncForTurn:
    # --- The promptness guarantee (the #24453 fix) ----------------------

    def test_dispatcher_returns_immediately_when_worker_blocks(self):
        """Even if the underlying ``sync_all`` would take seconds, the
        dispatcher must hand control back to ``run_conversation`` in
        well under a single SSE poll interval (0.5s) — otherwise the
        client still sees the original delayed ``response.completed``.
        """
        agent = _bare_agent()
        sync_started = threading.Event()
        sync_finished = threading.Event()

        def _slow_sync(*args, **kwargs):
            sync_started.set()
            # Simulate the 30-50s Hindsight retain — short enough to keep
            # the test fast but long enough that an inline call would
            # blow the deadline by 10x.
            time.sleep(0.5)
            sync_finished.set()

        agent._memory_manager.sync_all.side_effect = _slow_sync

        start = time.monotonic()
        agent._dispatch_memory_sync_for_turn(
            original_user_message="hi",
            final_response="hey",
            interrupted=False,
        )
        elapsed = time.monotonic() - start

        # Wait for the worker to start before measuring "really non-blocking" —
        # the timing fence below is a coarse upper bound, but the primary
        # non-blocking proof is that the dispatcher returned before the
        # 0.5s sleep finished (sync_finished is not set yet on return).
        assert sync_started.wait(timeout=2.0), "worker never ran"
        assert not sync_finished.is_set(), (
            "dispatcher waited for the worker — the 0.5s sleep finished "
            "before dispatch returned, defeating the #24453 fix"
        )

        # Coarse headroom: dispatch should complete in well under the 0.5s
        # SSE poll interval.  0.3s tolerates slow CI runners while still
        # being ~1.5x faster than the synchronous baseline this PR replaces.
        assert elapsed < 0.3, (
            f"dispatcher blocked for {elapsed:.3f}s; must return "
            "well under the 0.5s SSE poll so response.completed fires"
        )

        assert sync_finished.wait(timeout=2.0), "worker never finished"

    def test_dispatcher_uses_daemon_thread(self):
        """Memory sync is best-effort and we don't want a stuck Hindsight
        retain to keep the process alive past ``sys.exit`` / interpreter
        shutdown.  Daemon-flag the thread so the runtime can reap it.
        Matches ``_spawn_background_review`` (issue #15216 lineage).
        """
        agent = _bare_agent()
        captured = {}

        class _ImmediateThread:
            def __init__(self, *args, **kwargs):
                captured["kwargs"] = kwargs
                self._target = kwargs.get("target")
                self._target_kwargs = kwargs.get("kwargs") or {}

            def start(self):
                # Run synchronously so we can assert the target+kwargs
                # were wired up correctly without flaky timing.
                self._target(**self._target_kwargs)

        with patch("threading.Thread", _ImmediateThread):
            agent._dispatch_memory_sync_for_turn(
                original_user_message="hi",
                final_response="hey",
                interrupted=False,
            )

        assert captured["kwargs"].get("daemon") is True, (
            "dispatcher must use daemon=True so a stuck sync does not "
            "keep the interpreter alive past shutdown"
        )
        # Target is the existing worker — proves the dispatcher delegates
        # rather than re-implementing the sync logic and drifting away
        # from the interrupted-turn guard.
        assert captured["kwargs"].get("target") == agent._sync_external_memory_for_turn
        # Kwargs are forwarded unchanged so the worker sees the same
        # state run_conversation observed at end-of-turn.
        assert captured["kwargs"]["kwargs"] == {
            "original_user_message": "hi",
            "final_response": "hey",
            "interrupted": False,
        }

    # --- Cheap early-skips (don't spin up a no-op thread) ---------------

    def test_interrupted_turn_does_not_spawn_thread(self):
        """An interrupted turn would be skipped by the worker anyway; we
        also skip at the dispatcher so we don't pay thread-creation cost
        on every partial turn.  Matches the #15218 contract.
        """
        agent = _bare_agent()
        with patch("threading.Thread") as mock_thread:
            agent._dispatch_memory_sync_for_turn(
                original_user_message="hi",
                final_response="hey",
                interrupted=True,
            )
        mock_thread.assert_not_called()
        agent._memory_manager.sync_all.assert_not_called()

    def test_no_memory_manager_does_not_spawn_thread(self):
        """Sessions without a memory provider must not spawn idle
        threads on every turn."""
        from run_agent import AIAgent

        agent = AIAgent.__new__(AIAgent)
        agent._memory_manager = None
        agent.session_id = "test_session_no_mgr"

        with patch("threading.Thread") as mock_thread:
            agent._dispatch_memory_sync_for_turn(
                original_user_message="hi",
                final_response="hey",
                interrupted=False,
            )
        mock_thread.assert_not_called()

    def test_missing_final_response_does_not_spawn_thread(self):
        agent = _bare_agent()
        with patch("threading.Thread") as mock_thread:
            agent._dispatch_memory_sync_for_turn(
                original_user_message="hi",
                final_response=None,
                interrupted=False,
            )
        mock_thread.assert_not_called()

    def test_missing_original_user_message_does_not_spawn_thread(self):
        agent = _bare_agent()
        with patch("threading.Thread") as mock_thread:
            agent._dispatch_memory_sync_for_turn(
                original_user_message=None,
                final_response="hey",
                interrupted=False,
            )
        mock_thread.assert_not_called()

    # --- Old behaviour regression: dispatcher does sync end-to-end ------

    def test_normal_turn_invokes_sync_all_and_prefetch(self):
        """End-to-end smoke: dispatcher → daemon thread → worker calls
        both ``sync_all`` and ``queue_prefetch_all`` exactly once with
        the kwargs the caller provided.  Without joining the thread the
        assertions would race, so wait for it before checking.
        """
        agent = _bare_agent()

        agent._dispatch_memory_sync_for_turn(
            original_user_message="What's the weather in Paris?",
            final_response="Sunny and 22C.",
            interrupted=False,
        )

        # Find and join the worker thread so the assertions don't race.
        for t in threading.enumerate():
            if t.name.startswith("hermes-memory-sync-"):
                t.join(timeout=2.0)

        agent._memory_manager.sync_all.assert_called_once_with(
            "What's the weather in Paris?", "Sunny and 22C.",
            session_id="test_session_dispatch",
        )
        agent._memory_manager.queue_prefetch_all.assert_called_once_with(
            "What's the weather in Paris?",
            session_id="test_session_dispatch",
        )

    def test_skips_when_prior_sync_still_in_flight(self):
        """Per-agent single-worker discipline: a chatty user who fires
        turns faster than Hindsight can sync (30-50s/turn) must not
        accumulate one daemon thread per turn.  The second dispatch
        within the same agent skips if the first thread is still alive.
        """
        agent = _bare_agent()

        class _LiveThread:
            """Stand-in for a still-running worker thread."""
            def is_alive(self):
                return True

        agent._memory_sync_thread = _LiveThread()

        with patch("threading.Thread") as mock_thread:
            agent._dispatch_memory_sync_for_turn(
                original_user_message="second turn",
                final_response="reply",
                interrupted=False,
            )

        mock_thread.assert_not_called()
        # Sync_all itself must not be re-driven on the dispatcher thread
        # — the whole point is to keep run_conversation off the sync path.
        agent._memory_manager.sync_all.assert_not_called()

    def test_skips_release_when_prior_sync_completed(self):
        """The single-worker guard must NOT permanently latch — once
        the prior thread is done, the next turn should spawn again.
        """
        agent = _bare_agent()

        class _DeadThread:
            def is_alive(self):
                return False

        agent._memory_sync_thread = _DeadThread()

        with patch("threading.Thread") as mock_thread:
            mock_thread.return_value.start.return_value = None
            agent._dispatch_memory_sync_for_turn(
                original_user_message="next turn",
                final_response="reply",
                interrupted=False,
            )

        mock_thread.assert_called_once()

    def test_thread_start_failure_is_swallowed(self):
        """If the process is at its thread limit (or Thread() raises for
        any other reason), the dispatcher must NOT propagate — that
        would block ``run_conversation`` from returning and reintroduce
        the exact regression #24453 fixed.
        """
        agent = _bare_agent()

        with patch("threading.Thread", side_effect=RuntimeError(
            "can't start new thread"
        )):
            # Must not raise.
            agent._dispatch_memory_sync_for_turn(
                original_user_message="hi",
                final_response="hey",
                interrupted=False,
            )

        # The failed attempt must not have stamped a fake "in-flight"
        # tracker that would deadlock future dispatches.
        prior = getattr(agent, "_memory_sync_thread", None)
        if prior is not None:
            assert not prior.is_alive()

    def test_worker_exception_does_not_crash_dispatcher(self):
        """A backend error inside ``sync_all`` must not propagate up out
        of the worker thread — same best-effort contract that
        ``_sync_external_memory_for_turn`` enforces inline.  We test by
        joining the thread; a bubbled-up exception would surface in the
        thread's logger but never reach the dispatcher caller.
        """
        agent = _bare_agent()
        agent._memory_manager.sync_all.side_effect = RuntimeError(
            "backend unreachable"
        )

        # Must not raise.
        agent._dispatch_memory_sync_for_turn(
            original_user_message="hi",
            final_response="hey",
            interrupted=False,
        )

        for t in threading.enumerate():
            if t.name.startswith("hermes-memory-sync-"):
                t.join(timeout=2.0)

        agent._memory_manager.sync_all.assert_called_once()
