"""Regression tests for explicit CLI session source precedence (#45107)."""

from unittest import mock

from run_agent import AIAgent


def _agent_with_session_db(*, platform):
    agent = AIAgent.__new__(AIAgent)
    agent._session_db_created = False
    agent._session_db = mock.Mock()
    agent.session_id = "test-session"
    agent.platform = platform
    agent.model = "test-model"
    agent._session_init_model_config = {"model": "test-model"}
    agent._cached_system_prompt = "system"
    agent._parent_session_id = None
    return agent


def test_explicit_source_overrides_cli_platform(monkeypatch):
    monkeypatch.setenv("HERMES_SESSION_SOURCE", "distiller")
    agent = _agent_with_session_db(platform="cli")

    agent._ensure_db_session()

    assert agent._session_db.create_session.call_args.kwargs["source"] == "distiller"


def test_gateway_platform_used_when_no_explicit_source(monkeypatch):
    monkeypatch.delenv("HERMES_SESSION_SOURCE", raising=False)
    agent = _agent_with_session_db(platform="telegram")

    agent._ensure_db_session()

    assert agent._session_db.create_session.call_args.kwargs["source"] == "telegram"
