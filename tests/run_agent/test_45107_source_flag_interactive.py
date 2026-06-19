"""Regression tests for issue #45107.

``_ensure_db_session`` must honour ``HERMES_SESSION_SOURCE`` even when
``self.platform`` is already set to ``"cli"`` (which is the case for the
interactive ``hermes chat`` mode).  The env-var must take precedence over the
platform default so that ``hermes chat --source mytag`` persists
``source=mytag`` instead of ``source=cli``.
"""

import os
from unittest.mock import MagicMock, patch

import pytest


def _make_agent(session_db, *, platform: str = "cli"):
    with (
        patch("run_agent.get_tool_definitions", return_value=[]),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("run_agent.OpenAI"),
    ):
        from run_agent import AIAgent

        agent = AIAgent(
            api_key="test-key",
            base_url="https://openrouter.ai/api/v1",
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
            session_db=session_db,
            session_id="test-session-45107",
            platform=platform,
        )
    return agent


class TestEnsureDbSessionSourcePrecedence:
    """HERMES_SESSION_SOURCE must override self.platform in _ensure_db_session."""

    def test_env_overrides_cli_platform(self):
        """When HERMES_SESSION_SOURCE=mytag, source must be 'mytag' not 'cli'."""
        session_db = MagicMock()
        with patch.dict(os.environ, {"HERMES_SESSION_SOURCE": "mytag"}):
            agent = _make_agent(session_db, platform="cli")
            agent._ensure_db_session()

        session_db.create_session.assert_called_once()
        call_kwargs = session_db.create_session.call_args
        source_used = call_kwargs.kwargs.get("source") or call_kwargs.args[1] if call_kwargs.args and len(call_kwargs.args) > 1 else call_kwargs.kwargs["source"]
        assert source_used == "mytag", (
            f"Expected source='mytag' but got source='{source_used}'. "
            "HERMES_SESSION_SOURCE must take precedence over self.platform."
        )

    def test_env_overrides_non_cli_platform(self):
        """HERMES_SESSION_SOURCE also overrides non-cli platform values."""
        session_db = MagicMock()
        with patch.dict(os.environ, {"HERMES_SESSION_SOURCE": "integration-test"}):
            agent = _make_agent(session_db, platform="telegram")
            agent._ensure_db_session()

        session_db.create_session.assert_called_once()
        kwargs = session_db.create_session.call_args.kwargs
        assert kwargs["source"] == "integration-test"

    def test_platform_used_when_no_env_var(self):
        """When HERMES_SESSION_SOURCE is absent, self.platform is used."""
        session_db = MagicMock()
        env_without_source = {k: v for k, v in os.environ.items() if k != "HERMES_SESSION_SOURCE"}
        with patch.dict(os.environ, env_without_source, clear=True):
            agent = _make_agent(session_db, platform="telegram")
            agent._ensure_db_session()

        session_db.create_session.assert_called_once()
        kwargs = session_db.create_session.call_args.kwargs
        assert kwargs["source"] == "telegram"

    def test_cli_default_when_no_env_or_platform(self):
        """When neither HERMES_SESSION_SOURCE nor platform are set, source='cli'."""
        session_db = MagicMock()
        env_without_source = {k: v for k, v in os.environ.items() if k != "HERMES_SESSION_SOURCE"}
        with patch.dict(os.environ, env_without_source, clear=True):
            agent = _make_agent(session_db, platform=None)
            agent._ensure_db_session()

        session_db.create_session.assert_called_once()
        kwargs = session_db.create_session.call_args.kwargs
        assert kwargs["source"] == "cli"

    def test_idempotent_after_first_call(self):
        """_ensure_db_session is a no-op after first successful call."""
        session_db = MagicMock()
        with patch.dict(os.environ, {"HERMES_SESSION_SOURCE": "mytag"}):
            agent = _make_agent(session_db, platform="cli")
            agent._ensure_db_session()
            agent._ensure_db_session()

        assert session_db.create_session.call_count == 1, (
            "_ensure_db_session must not call create_session more than once."
        )
