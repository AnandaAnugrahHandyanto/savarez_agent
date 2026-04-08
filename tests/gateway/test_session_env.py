import os

from gateway.config import Platform
from gateway.run import GatewayRunner
from gateway.session import SessionContext, SessionSource


def test_set_session_env_includes_thread_id(monkeypatch):
    runner = object.__new__(GatewayRunner)
    source = SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="-1001",
        chat_name="Group",
        chat_type="group",
        thread_id="17585",
    )
    context = SessionContext(source=source, connected_platforms=[], home_channels={})

    monkeypatch.delenv("HERMES_SESSION_PLATFORM", raising=False)
    monkeypatch.delenv("HERMES_SESSION_CHAT_ID", raising=False)
    monkeypatch.delenv("HERMES_SESSION_CHAT_NAME", raising=False)
    monkeypatch.delenv("HERMES_SESSION_THREAD_ID", raising=False)

    runner._set_session_env(context)

    assert os.getenv("HERMES_SESSION_PLATFORM") == "telegram"
    assert os.getenv("HERMES_SESSION_CHAT_ID") == "-1001"
    assert os.getenv("HERMES_SESSION_CHAT_NAME") == "Group"
    assert os.getenv("HERMES_SESSION_THREAD_ID") == "17585"


def test_clear_session_env_removes_thread_id(monkeypatch):
    runner = object.__new__(GatewayRunner)

    monkeypatch.setenv("HERMES_SESSION_PLATFORM", "telegram")
    monkeypatch.setenv("HERMES_SESSION_CHAT_ID", "-1001")
    monkeypatch.setenv("HERMES_SESSION_CHAT_NAME", "Group")
    monkeypatch.setenv("HERMES_SESSION_THREAD_ID", "17585")

    runner._clear_session_env()

    assert os.getenv("HERMES_SESSION_PLATFORM") is None
    assert os.getenv("HERMES_SESSION_CHAT_ID") is None
    assert os.getenv("HERMES_SESSION_CHAT_NAME") is None
    assert os.getenv("HERMES_SESSION_THREAD_ID") is None


def test_set_session_env_clears_stale_optional_values(monkeypatch):
    runner = object.__new__(GatewayRunner)

    threaded_source = SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="-1001",
        chat_name="Group",
        chat_type="group",
        thread_id="17585",
    )
    plain_source = SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="12345",
        chat_type="dm",
    )

    threaded_context = SessionContext(
        source=threaded_source,
        connected_platforms=[],
        home_channels={},
    )
    plain_context = SessionContext(
        source=plain_source,
        connected_platforms=[],
        home_channels={},
    )

    monkeypatch.delenv("HERMES_SESSION_PLATFORM", raising=False)
    monkeypatch.delenv("HERMES_SESSION_CHAT_ID", raising=False)
    monkeypatch.delenv("HERMES_SESSION_CHAT_NAME", raising=False)
    monkeypatch.delenv("HERMES_SESSION_THREAD_ID", raising=False)

    runner._set_session_env(threaded_context)
    runner._set_session_env(plain_context)

    assert os.getenv("HERMES_SESSION_PLATFORM") == "telegram"
    assert os.getenv("HERMES_SESSION_CHAT_ID") == "12345"
    assert os.getenv("HERMES_SESSION_CHAT_NAME") is None
    assert os.getenv("HERMES_SESSION_THREAD_ID") is None
