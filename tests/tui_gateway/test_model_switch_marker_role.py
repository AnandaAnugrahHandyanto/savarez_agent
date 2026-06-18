"""Tests for _append_model_switch_marker role fix (issue #48338).

The model switch marker must NOT use role="system" because strict providers
(vLLM, Qwen) reject system messages that appear mid-conversation. Using
role="user" is safe — sanitize_api_messages() already merges consecutive
user messages, and user-role messages can appear at any position.
"""

from __future__ import annotations

import threading

from tui_gateway.server import _append_model_switch_marker


class TestAppendModelSwitchMarkerRole:
    """Verify the marker uses role='user', not role='system'."""

    def test_marker_uses_user_role(self) -> None:
        """The history entry must be role='user', not role='system'."""
        session: dict = {"session_key": "test-session", "history": []}
        _append_model_switch_marker(session, model="gpt-4o", provider="openai")
        assert len(session["history"]) == 1
        entry = session["history"][0]
        assert entry["role"] == "user", (
            f"Expected role='user' but got role='{entry['role']}'. "
            "Strict providers (vLLM, Qwen) reject mid-conversation system messages."
        )

    def test_marker_content_preserved(self) -> None:
        """The marker content must still describe the model switch."""
        session: dict = {"session_key": "s", "history": []}
        _append_model_switch_marker(session, model="qwen3.6-35b", provider="vllm")
        content = session["history"][0]["content"]
        assert "qwen3.6-35b" in content
        assert "vllm" in content
        assert "model" in content.lower()

    def test_marker_with_empty_provider(self) -> None:
        """Provider part should be omitted when provider is empty."""
        session: dict = {"session_key": "s", "history": []}
        _append_model_switch_marker(session, model="claude-sonnet-4", provider="")
        content = session["history"][0]["content"]
        assert "claude-sonnet-4" in content
        assert "via provider" not in content

    def test_marker_with_lock(self) -> None:
        """Marker should work correctly when session has a history_lock."""
        session: dict = {
            "session_key": "s",
            "history": [],
            "history_lock": threading.Lock(),
        }
        _append_model_switch_marker(session, model="gpt-4o", provider="openai")
        assert len(session["history"]) == 1
        assert session["history"][0]["role"] == "user"

    def test_marker_increments_history_version(self) -> None:
        """history_version should be incremented after appending."""
        session: dict = {"session_key": "s", "history": [], "history_version": 5}
        _append_model_switch_marker(session, model="gpt-4o", provider="openai")
        assert session["history_version"] == 6

    def test_no_marker_for_none_session(self) -> None:
        """None session should be a no-op."""
        _append_model_switch_marker(None, model="gpt-4o", provider="openai")

    def test_no_marker_for_empty_session_key(self) -> None:
        """Empty session_key should be a no-op."""
        session: dict = {"session_key": "", "history": []}
        _append_model_switch_marker(session, model="gpt-4o", provider="openai")
        assert len(session["history"]) == 0
