"""ContextSessionStore: one agent per context, history continuity, cancellation."""

from __future__ import annotations

import threading

from a2a_adapter.sessions import ContextSessionStore


class _InterruptibleAgent:
    """Fake that mimics AIAgent's interrupt semantics.

    ``interrupt()`` sets a sticky ``_interrupt_requested`` flag; a turn that
    sees the flag set at its start returns interrupted (as AIAgent's loop does);
    ``clear_interrupt()`` resets it.
    """

    def __init__(self) -> None:
        self._interrupt_requested = False
        self.stream_delta_callback = None
        self.reasoning_callback = None
        self.tool_progress_callback = None
        self.step_callback = None
        self.thinking_callback = None
        self.runs: list[str] = []

    def run_conversation(
        self, *, user_message, conversation_history=None, task_id=None, **kw
    ):
        if self._interrupt_requested:
            return {"final_response": None, "interrupted": True}
        self.runs.append(user_message)
        msgs = list(conversation_history or [])
        msgs += [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": f"echo: {user_message}"},
        ]
        return {"final_response": f"echo: {user_message}", "messages": msgs}

    def interrupt(self, message=None):
        self._interrupt_requested = True

    def clear_interrupt(self):
        self._interrupt_requested = False


def test_same_context_reuses_one_agent(fakes):
    created = []

    def factory():
        agent = fakes.FakeAgent()
        created.append(agent)
        return agent

    store = ContextSessionStore(agent_factory=factory)
    first = store.get_or_create("ctx-1")
    again = store.get_or_create("ctx-1")
    other = store.get_or_create("ctx-2")

    assert first is again
    assert other is not first
    assert len(created) == 2


def test_run_turn_appends_to_history(fakes):
    store = ContextSessionStore(agent_factory=fakes.FakeAgent)
    session = store.get_or_create("ctx-1")

    first = session.run_turn("hello", task_id="t1")
    assert first["final_response"] == "echo: hello"
    assert session.history[-1] == {"role": "assistant", "content": "echo: hello"}

    # Second turn sees the prior history.
    session.run_turn("again", task_id="t2")
    assert session.agent.runs == ["hello", "again"]
    assert len(session.history) == 4


def test_cancel_sets_event_and_interrupts(fakes):
    agent = fakes.FakeAgent()
    store = ContextSessionStore(agent_factory=lambda: agent)
    session = store.get_or_create("ctx-1")

    session.cancel()

    assert session.cancel_event.is_set()
    assert agent.interrupted is True


def test_lru_eviction_caps_session_count(fakes):
    store = ContextSessionStore(agent_factory=fakes.FakeAgent, max_sessions=2)
    a = store.get_or_create("a")
    store.get_or_create("b")
    # Touch "a" so "b" becomes the least-recently-used entry.
    store.get_or_create("a")
    c = store.get_or_create("c")  # over cap -> evicts LRU ("b")

    assert store.get("b") is None
    assert store.get("a") is a
    assert store.get("c") is c


def test_cancel_after_turn_does_not_poison_next_turn():
    """A cancel that arrives with no turn running must not abort the next turn.

    AIAgent.interrupt() sets a sticky flag that is only cleared by a turn that
    runs to completion. If cancel() fires while idle (e.g. just after a turn
    finished, or on a reused context), the next turn must start from a clean
    slate instead of inheriting the stale interrupt and aborting immediately.
    """
    agent = _InterruptibleAgent()
    session = ContextSessionStore(agent_factory=lambda: agent).get_or_create("ctx")

    session.cancel()  # no turn running; sets the sticky interrupt flag
    assert agent._interrupt_requested is True

    result = session.run_turn("hello", task_id="t-new")
    assert result.get("interrupted") is not True
    assert result["final_response"] == "echo: hello"


def test_cancel_of_non_running_task_does_not_interrupt_agent():
    """Task-scoped cancel: cancelling a task that is not the running one must
    not interrupt the agent (which would kill an unrelated in-flight turn on the
    same context). The targeted task is instead skipped if it later starts."""
    agent = _InterruptibleAgent()
    session = ContextSessionStore(agent_factory=lambda: agent).get_or_create("ctx")

    session.cancel(task_id="queued-task")  # nothing running on this context
    assert agent._interrupt_requested is False

    result = session.run_turn("hi", task_id="queued-task")
    assert result.get("interrupted") is True
    assert agent.runs == []  # the cancelled task never actually ran


def test_run_turn_applies_passed_callbacks_under_the_turn():
    """Per-turn callbacks must be the ones active during this turn's run, and be
    cleared afterwards — so concurrent turns can't cross-wire the shared agent."""
    agent = _InterruptibleAgent()
    seen = []
    agent.run_conversation = (  # type: ignore[method-assign]
        lambda **kw: (
            agent.stream_delta_callback("d"),
            {"final_response": "ok", "messages": []},
        )[1]
    )

    def cb(text):
        seen.append(text)

    session = ContextSessionStore(agent_factory=lambda: agent).get_or_create("ctx")
    session.run_turn("go", task_id="t1", callbacks={"stream_delta_callback": cb})

    assert seen == ["d"]  # the passed callback fired during the turn
    assert agent.stream_delta_callback is None  # cleared after the turn


def test_lru_does_not_evict_an_in_flight_session(fakes):
    """An in-flight turn's session must survive eviction; an idle LRU session is
    dropped instead. Evicting a busy session silently forks its history into a
    fresh empty agent and orphans the running worker thread."""
    release = threading.Event()
    started = threading.Event()

    class BlockingAgent(_InterruptibleAgent):
        def run_conversation(
            self, *, user_message, conversation_history=None, task_id=None, **kw
        ):
            started.set()
            release.wait(5)
            return {"final_response": "done", "messages": []}

    blocking = BlockingAgent()
    agents = iter([blocking, fakes.FakeAgent(), fakes.FakeAgent()])
    store = ContextSessionStore(agent_factory=lambda: next(agents), max_sessions=2)

    busy = store.get_or_create("busy")
    store.get_or_create("idle")  # idle, least-recently-used after "busy" runs

    worker = threading.Thread(target=lambda: busy.run_turn("x", task_id="t-busy"))
    worker.start()
    assert started.wait(5)  # turn is now in flight -> "busy" is active

    try:
        third = store.get_or_create("third")  # over cap -> must evict an idle one
        assert store.get("busy") is busy  # in-flight session preserved
        assert store.get("idle") is None  # idle LRU evicted instead
        assert store.get("third") is third
    finally:
        release.set()
        worker.join(5)
