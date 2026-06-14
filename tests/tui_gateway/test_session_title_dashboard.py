"""Dashboard session chrome: title in session.info and auto-title callback."""

import threading
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture()
def server():
    with patch.dict(
        "sys.modules",
        {
            "hermes_constants": MagicMock(
                get_hermes_home=MagicMock(return_value=Path("/tmp/hermes_test_title"))
            ),
            "hermes_cli.env_loader": MagicMock(),
            "hermes_cli.banner": MagicMock(),
            "hermes_state": MagicMock(),
        },
    ):
        import importlib

        mod = importlib.import_module("tui_gateway.server")
        yield mod
        mod._sessions.clear()
        mod._pending.clear()
        mod._answers.clear()


@pytest.fixture()
def emits(server, monkeypatch):
    captured: list = []
    monkeypatch.setattr(
        server,
        "_emit",
        lambda event, sid, payload=None: captured.append((event, sid, payload)),
    )
    return captured


def test_session_info_includes_title(server, monkeypatch):
    agent = MagicMock()
    agent.model = "test/model"
    agent.provider = "openrouter"
    agent.tools = []
    agent.reasoning_config = None
    agent.service_tier = None

    session = {"session_key": "sess-1", "pending_title": "Draft title"}

    class _DB:
        def get_session_title(self, key):
            assert key == "sess-1"
            return "Persisted title"

    monkeypatch.setattr(server, "_get_db", lambda: _DB())
    monkeypatch.setattr(server, "_session_cwd", lambda _s: "/tmp")
    monkeypatch.setattr(server, "_load_cfg", lambda: {"display": {}})
    monkeypatch.setattr(server, "_get_usage", lambda _a: {})
    monkeypatch.setattr(server, "_probe_credentials", lambda _a: None)
    monkeypatch.setattr(server, "_current_profile_name", lambda: "default")
    monkeypatch.setattr(server, "_git_branch_for_cwd", lambda _c: "")

    info = server._session_info(agent, session)
    assert info["title"] == "Persisted title"


def _wait_for_prompt_turn(session: dict, *, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with session["history_lock"]:
            if not session.get("running"):
                return
        time.sleep(0.01)
    raise AssertionError("prompt turn did not finish before timeout")


def test_run_prompt_submit_auto_title_emits_session_info(server, monkeypatch, emits):
    agent = SimpleNamespace(
        model="test/model",
        provider="openrouter",
        session_id="stored-1",
    )
    agent.run_conversation = MagicMock(
        return_value={
            "final_response": "Here is the answer.",
            "messages": [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "Here is the answer."},
            ],
        }
    )

    session = {
        "session_key": "stored-1",
        "history": [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "Here is the answer."},
        ],
        "history_lock": threading.Lock(),
        "running": True,
        "agent": agent,
        "pending_title": None,
    }

    monkeypatch.setattr(server, "_get_db", lambda: MagicMock())
    monkeypatch.setattr(server, "_get_usage", lambda _a: {})
    monkeypatch.setattr(server, "render_message", lambda raw, cols: raw)
    monkeypatch.setattr(
        server,
        "_session_info",
        lambda _a, _s: {"model": "m", "title": "Generated title"},
    )
    monkeypatch.setattr(server, "_sync_agent_model_with_config", lambda _sid, _session: None)
    monkeypatch.setattr(server, "_wire_callbacks", lambda _sid: None)
    monkeypatch.setattr(server, "_register_session_cwd", lambda _session: None)

    def fake_maybe_auto_title(db, sid, user, response, history, **kwargs):
        cb = kwargs.get("title_callback")
        if cb:
            cb("Generated title")

    monkeypatch.setattr(
        "agent.title_generator.maybe_auto_title",
        fake_maybe_auto_title,
    )

    server._run_prompt_submit("rid-title", "live-1", session, "hello")
    _wait_for_prompt_turn(session)

    errors = [e for e in emits if e[0] == "error"]
    assert not errors, f"unexpected errors: {errors}"

    info_events = [e for e in emits if e[0] == "session.info"]
    assert any(
        e[2].get("title") == "Generated title" for e in info_events
    ), f"expected title in session.info emits, got {emits}"
