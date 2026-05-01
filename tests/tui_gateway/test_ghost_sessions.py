"""Tests for TUI ghost session fix (#18269).

Verify that ``_finalize_session`` calls ``db.end_session`` so that
sessions created eagerly by the TUI are properly closed in state.db
when the user quits without sending a message.
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import pytest


def _make_session(key: str = "ses_abc123", *, with_agent: bool = False) -> dict:
    session: dict = {
        "agent": None,
        "history": [],
        "history_lock": threading.Lock(),
        "session_key": key,
    }
    if with_agent:
        agent = MagicMock()
        agent.session_id = key
        session["agent"] = agent
    return session


class TestFinalizeSessionEndsDB:
    """_finalize_session must call db.end_session to avoid ghost rows."""

    def test_end_session_called_on_finalize(self):
        from tui_gateway.server import _finalize_session

        mock_db = MagicMock()
        session = _make_session("ses_test1")

        with patch("tui_gateway.server._get_db", return_value=mock_db):
            _finalize_session(session)

        mock_db.end_session.assert_called_once_with("ses_test1", "tui_close")

    def test_end_session_custom_reason(self):
        from tui_gateway.server import _finalize_session

        mock_db = MagicMock()
        session = _make_session("ses_test2")

        with patch("tui_gateway.server._get_db", return_value=mock_db):
            _finalize_session(session, end_reason="tui_shutdown")

        mock_db.end_session.assert_called_once_with("ses_test2", "tui_shutdown")

    def test_no_double_finalize(self):
        from tui_gateway.server import _finalize_session

        mock_db = MagicMock()
        session = _make_session("ses_test3")

        with patch("tui_gateway.server._get_db", return_value=mock_db):
            _finalize_session(session)
            _finalize_session(session)  # second call should be no-op

        mock_db.end_session.assert_called_once()

    def test_no_crash_when_db_unavailable(self):
        from tui_gateway.server import _finalize_session

        session = _make_session("ses_test4")

        with patch("tui_gateway.server._get_db", return_value=None):
            _finalize_session(session)  # should not raise

    def test_no_crash_when_end_session_raises(self):
        from tui_gateway.server import _finalize_session

        mock_db = MagicMock()
        mock_db.end_session.side_effect = Exception("db locked")
        session = _make_session("ses_test5")

        with patch("tui_gateway.server._get_db", return_value=mock_db):
            _finalize_session(session)  # should not raise
