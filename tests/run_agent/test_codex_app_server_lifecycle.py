from __future__ import annotations

from run_agent import AIAgent


class CloseRecorder:
    def __init__(self) -> None:
        self.closed = 0

    def close(self) -> None:
        self.closed += 1


def test_release_clients_closes_codex_app_server_session():
    agent = AIAgent.__new__(AIAgent)
    agent._active_children = []
    agent._active_children_lock = type(
        "Lock",
        (),
        {"__enter__": lambda self: self, "__exit__": lambda self, *args: None},
    )()
    agent.client = None
    codex_session = CloseRecorder()
    agent._codex_session = codex_session

    agent.release_clients()

    assert codex_session.closed == 1
    assert agent._codex_session is None


def test_close_closes_codex_app_server_session():
    agent = AIAgent.__new__(AIAgent)
    agent.session_id = "session"
    agent._active_children = []
    agent._active_children_lock = type(
        "Lock",
        (),
        {"__enter__": lambda self: self, "__exit__": lambda self, *args: None},
    )()
    agent.client = None
    codex_session = CloseRecorder()
    agent._codex_session = codex_session

    agent.close()

    assert codex_session.closed == 1
    assert agent._codex_session is None
