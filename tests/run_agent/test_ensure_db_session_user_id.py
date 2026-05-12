"""Tests for AIAgent._ensure_db_session — user_id propagation (issue #24321)."""

from unittest.mock import MagicMock


def _make_agent(user_id):
    """Build a minimal AIAgent-like object with _ensure_db_session."""
    import run_agent

    agent = object.__new__(run_agent.AIAgent)
    agent.session_id = "test-session-001"
    agent.user_id = user_id
    agent.platform = "telegram"
    agent._session_db = MagicMock()
    agent._session_db_created = False
    agent.model = "gpt-4o"
    agent._session_init_model_config = {}
    agent._cached_system_prompt = ""
    agent._parent_session_id = None
    return agent


class TestEnsureDbSessionUserId:
    def test_user_id_propagated(self):
        agent = _make_agent("user-123")
        agent._ensure_db_session()
        kwargs = agent._session_db.create_session.call_args.kwargs
        assert kwargs["user_id"] == "user-123"

    def test_none_user_id_flows_through(self):
        """user_id=None is valid for CLI sessions and must not be replaced."""
        agent = _make_agent(None)
        agent._ensure_db_session()
        kwargs = agent._session_db.create_session.call_args.kwargs
        assert kwargs["user_id"] is None

    def test_idempotent_when_already_created(self):
        agent = _make_agent("user-456")
        agent._session_db_created = True
        agent._ensure_db_session()
        agent._session_db.create_session.assert_not_called()
