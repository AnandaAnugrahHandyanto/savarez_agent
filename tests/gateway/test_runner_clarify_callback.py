"""End-to-end logic test for gateway clarify_callback wiring.

Issue #21032: ``AIAgent.clarify_callback`` was never set on the messaging
gateway path. This test verifies:

1. The gateway code in ``gateway/run.py`` actually assigns
   ``agent.clarify_callback`` next to ``agent.status_callback`` (regression
   guard against future deletions).
2. The clarify-callback contract — a sync function that posts an async
   ``send_clarify_prompt`` coroutine to the adapter and blocks on a
   ``threading.Event`` until the platform resolves it — works correctly
   when reproduced against a mock adapter.
"""

import asyncio
import re
import sys
import threading
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

_repo = Path(__file__).resolve().parents[2]
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))


# ---------------------------------------------------------------------------
# Static guard: the wiring line must remain in gateway/run.py.
# ---------------------------------------------------------------------------

def test_run_py_wires_clarify_callback_on_agent():
    """gateway/run.py must assign agent.clarify_callback for every turn."""
    src = (_repo / "gateway" / "run.py").read_text(encoding="utf-8")
    # Wired right after status_callback, on the per-turn assignment block
    pattern = re.compile(
        r"agent\.status_callback\s*=\s*_status_callback_sync\s*\n"
        r"\s*agent\.clarify_callback\s*=\s*_clarify_callback_sync",
    )
    assert pattern.search(src), (
        "agent.clarify_callback wiring missing in gateway/run.py — "
        "issue #21032 regression"
    )


# ---------------------------------------------------------------------------
# Behavioural test: reproduce the closure's contract against a mock adapter.
# This exercises the same logic the gateway uses (post coroutine, park on
# Event, return choice) without standing up a full GatewayRunner.
# ---------------------------------------------------------------------------

class _FakeAdapter:
    """Stand-in for an adapter that supports send_clarify_prompt."""

    def __init__(self):
        self._clarify_state = {}
        self.calls = []

    async def send_clarify_prompt(self, *, chat_id, question, choices, clarify_id, metadata=None):
        self.calls.append({
            "chat_id": chat_id, "question": question,
            "choices": list(choices), "clarify_id": clarify_id,
            "metadata": metadata,
        })
        # Return a SendResult-shaped object — only success matters here.
        return MagicMock(success=True, message_id="1")


def _build_clarify_callback(adapter, *, loop, chat_id="12345",
                            thread_metadata=None,
                            run_still_current=lambda: True):
    """Reproduces the closure built inside gateway.run.GatewayRunner._run_agent."""
    import logging
    logger = logging.getLogger(__name__)

    def _clarify_callback_sync(question, choices=None):
        if not adapter or not run_still_current():
            return ""
        send_prompt = getattr(adapter, "send_clarify_prompt", None)
        clarify_state = getattr(adapter, "_clarify_state", None)
        if not callable(send_prompt) or clarify_state is None:
            return ""
        import uuid
        clarify_id = uuid.uuid4().hex
        event = threading.Event()
        clarify_state[clarify_id] = {
            "event": event, "choice": None,
            "choices": list(choices or []), "question": question,
        }
        try:
            asyncio.run_coroutine_threadsafe(
                send_prompt(
                    chat_id=chat_id, question=question,
                    choices=list(choices or []),
                    clarify_id=clarify_id, metadata=thread_metadata,
                ),
                loop,
            ).result(timeout=5)
        except Exception as exc:
            logger.error("clarify_callback send error: %s", exc)
            clarify_state.pop(clarify_id, None)
            return ""
        event.wait(timeout=5)
        state = clarify_state.pop(clarify_id, {"choice": ""})
        return state.get("choice") or ""

    return _clarify_callback_sync


def test_clarify_callback_posts_coroutine_and_blocks_until_resolved():
    """Mirror the gateway contract: post async send, park, return user's choice."""
    adapter = _FakeAdapter()

    # Run the asyncio loop in a background thread (matches gateway shape).
    loop = asyncio.new_event_loop()
    loop_thread = threading.Thread(target=loop.run_forever, daemon=True)
    loop_thread.start()
    try:
        cb = _build_clarify_callback(adapter, loop=loop)

        # Resolver thread acts as the inline-button click — once the
        # callback posts state, find the clarify_id and resolve it.
        resolved_with = {}

        def _resolver():
            for _ in range(50):
                if adapter._clarify_state:
                    cid, state = next(iter(adapter._clarify_state.items()))
                    state["choice"] = "green"
                    state["event"].set()
                    resolved_with["id"] = cid
                    return
                time.sleep(0.05)

        threading.Thread(target=_resolver, daemon=True).start()

        result = cb("Pick a colour:", ["red", "green", "blue"])

        assert result == "green"
        assert resolved_with.get("id") is not None
        assert len(adapter.calls) == 1
        call = adapter.calls[0]
        assert call["question"] == "Pick a colour:"
        assert call["choices"] == ["red", "green", "blue"]
        # State should be cleaned up
        assert adapter._clarify_state == {}
    finally:
        loop.call_soon_threadsafe(loop.stop)
        loop_thread.join(timeout=2)


def test_clarify_callback_returns_empty_when_adapter_lacks_method():
    """Adapters without send_clarify_prompt must not raise — return "" so the
    agent falls back to its own judgement."""
    bare_adapter = MagicMock(spec=[])  # has nothing
    loop = asyncio.new_event_loop()
    try:
        cb = _build_clarify_callback(bare_adapter, loop=loop)
        assert cb("Q?", ["a"]) == ""
    finally:
        loop.close()
