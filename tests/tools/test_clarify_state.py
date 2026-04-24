"""Tests for blocking gateway clarify state."""

import threading
import time

from tools import clarify_state as mod


def _clear_state():
    mod._gateway_queues.clear()


class TestBlockingGatewayClarify:
    def setup_method(self):
        _clear_state()

    def test_request_and_resolve_unblocks_entry(self):
        session_key = "clarify-session"
        seen = {}
        result_box = {}

        def _runner():
            result_box["result"] = mod.request_gateway_clarify(
                session_key=session_key,
                question="Pick one",
                choices=["Alpha", "Beta"],
                notify_callback=lambda data: seen.update(data),
                timeout_seconds=5,
            )

        thread = threading.Thread(target=_runner)
        thread.start()

        for _ in range(50):
            if seen:
                break
            time.sleep(0.02)

        assert seen["question"] == "Pick one"
        assert seen["choices"] == ["Alpha", "Beta"]
        assert mod.has_blocking_clarify(session_key) is True

        assert mod.resolve_gateway_clarify(session_key, "2") == 1
        thread.join(timeout=5)

        assert result_box["result"] == "Beta"
        assert mod.has_blocking_clarify(session_key) is False

    def test_resolve_by_clarify_id_targets_matching_entry(self):
        session_key = "clarify-id-session"
        seen = []
        results = []

        def _ask(question: str):
            result = mod.request_gateway_clarify(
                session_key=session_key,
                question=question,
                choices=["A", "B"],
                notify_callback=lambda data: seen.append(data),
                timeout_seconds=5,
            )
            results.append((question, result))

        t1 = threading.Thread(target=_ask, args=("First?",))
        t2 = threading.Thread(target=_ask, args=("Second?",))
        t1.start()
        t2.start()

        for _ in range(50):
            if len(seen) == 2:
                break
            time.sleep(0.02)

        second_id = next(item["clarify_id"] for item in seen if item["question"] == "Second?")
        assert mod.resolve_gateway_clarify(session_key, "B", clarify_id=second_id) == 1
        assert mod.resolve_gateway_clarify(session_key, "A") == 1

        t1.join(timeout=5)
        t2.join(timeout=5)

        assert ("First?", "A") in results
        assert ("Second?", "B") in results
