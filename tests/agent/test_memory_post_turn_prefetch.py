"""Regression tests for suppressing useless post-turn memory prefetch.

Single-query CLI sessions end immediately after the response.  Queueing a
"next turn" prefetch in that path starts Honcho background threads that have no
consumer and can race interpreter shutdown.
"""

from __future__ import annotations

from run_agent import AIAgent


class _RecordingMemoryManager:
    def __init__(self):
        self.sync_calls = []
        self.prefetch_calls = []

    def sync_all(self, user_content, assistant_content, **kwargs):
        self.sync_calls.append((user_content, assistant_content, kwargs))

    def queue_prefetch_all(self, query, **kwargs):
        self.prefetch_calls.append((query, kwargs))


def _agent_with_memory_manager(suppress_prefetch: bool = False):
    agent = AIAgent.__new__(AIAgent)
    setattr(agent, "_memory_manager", _RecordingMemoryManager())
    setattr(agent, "session_id", "sess-1")
    setattr(agent, "_suppress_post_turn_prefetch", suppress_prefetch)
    return agent


def test_external_memory_sync_can_suppress_next_turn_prefetch():
    agent = _agent_with_memory_manager(suppress_prefetch=True)

    agent._sync_external_memory_for_turn(
        original_user_message="hello",
        final_response="world",
        interrupted=False,
        messages=[{"role": "user", "content": "hello"}],
    )

    mm = getattr(agent, "_memory_manager")
    assert len(mm.sync_calls) == 1
    assert mm.prefetch_calls == []


def test_external_memory_sync_prefetches_by_default():
    agent = _agent_with_memory_manager(suppress_prefetch=False)

    agent._sync_external_memory_for_turn(
        original_user_message="hello",
        final_response="world",
        interrupted=False,
    )

    mm = getattr(agent, "_memory_manager")
    assert len(mm.sync_calls) == 1
    assert mm.prefetch_calls == [("hello", {"session_id": "sess-1"})]
