"""Test that HERMES_SESSION_ID is exposed as an env var and ContextVar."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from run_agent import AIAgent


@pytest.fixture(autouse=True)
def _cleanup_env():
    """Remove HERMES_SESSION_ID before/after each test."""
    os.environ.pop("HERMES_SESSION_ID", None)
    os.environ.pop("HERMES_SESSION_SOURCE", None)
    os.environ.pop("HERMES_SESSION_VISIBILITY", None)
    yield
    os.environ.pop("HERMES_SESSION_ID", None)
    os.environ.pop("HERMES_SESSION_SOURCE", None)
    os.environ.pop("HERMES_SESSION_VISIBILITY", None)


def test_session_id_env_set_on_init():
    """AIAgent.__init__ sets HERMES_SESSION_ID in the environment."""
    agent = AIAgent(
        api_key="test-key",
        base_url="https://openrouter.ai/api/v1",
        quiet_mode=True,
        skip_context_files=True,
        skip_memory=True,
    )
    assert os.environ.get("HERMES_SESSION_ID") == agent.session_id
    assert len(agent.session_id) > 0


def test_session_id_env_uses_provided_id():
    """When session_id is passed explicitly, HERMES_SESSION_ID reflects it."""
    custom_id = "20260511_120000_abc12345"
    agent = AIAgent(
        api_key="test-key",
        base_url="https://openrouter.ai/api/v1",
        session_id=custom_id,
        quiet_mode=True,
        skip_context_files=True,
        skip_memory=True,
    )
    assert os.environ["HERMES_SESSION_ID"] == custom_id
    assert agent.session_id == custom_id


def test_session_id_contextvar_set():
    """AIAgent.__init__ also sets the ContextVar for concurrency safety."""
    custom_id = "20260511_130000_def67890"
    AIAgent(
        api_key="test-key",
        base_url="https://openrouter.ai/api/v1",
        session_id=custom_id,
        quiet_mode=True,
        skip_context_files=True,
        skip_memory=True,
    )
    from gateway.session_context import get_session_env
    assert get_session_env("HERMES_SESSION_ID") == custom_id


def test_cli_session_source_env_is_persisted(tmp_path, monkeypatch):
    """CLI integrations can tag their persisted session source and visibility."""
    from hermes_state import SessionDB

    monkeypatch.setenv("HERMES_SESSION_SOURCE", "flashbyte-dashboard")
    monkeypatch.setenv("HERMES_SESSION_VISIBILITY", "internal")
    db = SessionDB(tmp_path / "state.db")
    try:
        agent = AIAgent(
            api_key="test-key",
            base_url="https://openrouter.ai/api/v1",
            session_id="flashbyte-test",
            platform="cli",
            session_db=db,
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
        )
        agent._ensure_db_session()
        row = db.get_session("flashbyte-test")
    finally:
        db.close()

    assert row["source"] == "flashbyte-dashboard"
    assert row["visibility"] == "internal"


def test_non_cli_platform_ignores_cli_session_source_env(tmp_path, monkeypatch):
    """A CLI source env var must not relabel gateway platform sessions."""
    from hermes_state import SessionDB

    monkeypatch.setenv("HERMES_SESSION_SOURCE", "flashbyte-dashboard")
    monkeypatch.setenv("HERMES_SESSION_VISIBILITY", "internal")
    db = SessionDB(tmp_path / "state.db")
    try:
        agent = AIAgent(
            api_key="test-key",
            base_url="https://openrouter.ai/api/v1",
            session_id="telegram-test",
            platform="telegram",
            session_db=db,
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
        )
        agent._ensure_db_session()
        row = db.get_session("telegram-test")
    finally:
        db.close()

    assert row["source"] == "telegram"
    assert row["visibility"] == "user"
