"""Tests for agent.title_generator — auto-generated session titles."""

import threading
from unittest.mock import MagicMock, patch

import pytest

from agent.title_generator import (
    generate_title,
    generate_refined_title,
    auto_title_session,
    maybe_auto_title,
    maybe_refine_title,
)


class TestGenerateTitle:
    """Unit tests for generate_title()."""

    def test_returns_title_on_success(self):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Debugging Python Import Errors"

        with patch("agent.title_generator.call_llm", return_value=mock_response):
            title = generate_title("help me fix this import", "Sure, let me check...")
            assert title == "Debugging Python Import Errors"

    def test_strips_quotes(self):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '"Setting Up Docker Environment"'

        with patch("agent.title_generator.call_llm", return_value=mock_response):
            title = generate_title("how do I set up docker", "First install...")
            assert title == "Setting Up Docker Environment"

    def test_strips_title_prefix(self):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Title: Kubernetes Pod Debugging"

        with patch("agent.title_generator.call_llm", return_value=mock_response):
            title = generate_title("my pod keeps crashing", "Let me look...")
            assert title == "Kubernetes Pod Debugging"

    def test_truncates_long_titles(self):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "A" * 100

        with patch("agent.title_generator.call_llm", return_value=mock_response):
            title = generate_title("question", "answer")
            assert len(title) == 80
            assert title.endswith("...")

    def test_returns_none_on_empty_response(self):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = ""

        with patch("agent.title_generator.call_llm", return_value=mock_response):
            assert generate_title("question", "answer") is None

    def test_returns_none_on_exception(self):
        with patch("agent.title_generator.call_llm", side_effect=RuntimeError("no provider")):
            assert generate_title("question", "answer") is None

    def test_invokes_failure_callback_on_exception(self):
        """failure_callback must fire so the user sees a warning (issue #15775)."""
        captured = []

        def _cb(task, exc):
            captured.append((task, exc))

        exc = RuntimeError("openrouter 402: credits exhausted")
        with patch("agent.title_generator.call_llm", side_effect=exc):
            result = generate_title("question", "answer", failure_callback=_cb)

        assert result is None
        assert len(captured) == 1
        assert captured[0][0] == "title generation"
        assert captured[0][1] is exc

    def test_failure_callback_errors_are_swallowed(self):
        """A broken callback must not crash title generation."""

        def _bad_cb(task, exc):
            raise ValueError("callback bug")

        with patch("agent.title_generator.call_llm", side_effect=RuntimeError("nope")):
            # Should return None without re-raising the callback error
            assert generate_title("q", "a", failure_callback=_bad_cb) is None

    def test_no_callback_matches_legacy_behavior(self):
        """Omitting failure_callback preserves the silent-None return."""
        with patch("agent.title_generator.call_llm", side_effect=RuntimeError("nope")):
            assert generate_title("q", "a") is None

    def test_truncates_long_messages(self):
        """Long user/assistant messages should be truncated in the LLM request."""
        captured_kwargs = {}

        def mock_call_llm(**kwargs):
            captured_kwargs.update(kwargs)
            resp = MagicMock()
            resp.choices = [MagicMock()]
            resp.choices[0].message.content = "Short Title"
            return resp

        with patch("agent.title_generator.call_llm", side_effect=mock_call_llm):
            generate_title("x" * 1000, "y" * 1000)

        # The user content in the messages should be truncated
        user_content = captured_kwargs["messages"][1]["content"]
        assert len(user_content) < 1100  # 500 + 500 + formatting


class FakeTitleDB:
    """Tiny session DB double for title provenance tests."""

    def __init__(self, title=None, model_config=None):
        self.title = title
        self.model_config = model_config or {}
        self.set_titles = []
        self.merged_model_configs = []

    def get_session_title(self, session_id):
        return self.title

    def set_session_title(self, session_id, title):
        self.title = title
        self.set_titles.append((session_id, title))
        return True

    def get_session(self, session_id):
        return {"id": session_id, "title": self.title, "model_config": self.model_config}

    def merge_session_model_config(self, session_id, patch):
        self.model_config.update(patch)
        self.merged_model_configs.append((session_id, patch))
        return True


class TestGenerateRefinedTitle:
    """Unit tests for generating later, topic-aligned titles."""

    def test_uses_conversation_context_and_existing_title(self):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hermes Adaptive Session Titles"

        history = [
            {"role": "user", "content": "initial vague request"},
            {"role": "assistant", "content": "sure"},
            {"role": "user", "content": "now implement adaptive title refinement"},
        ]

        captured = {}

        def mock_call_llm(**kwargs):
            captured.update(kwargs)
            return mock_response

        with patch("agent.title_generator.call_llm", side_effect=mock_call_llm):
            title = generate_refined_title("Initial Help", history)

        assert title == "Hermes Adaptive Session Titles"
        user_content = captured["messages"][1]["content"]
        assert "Existing title: Initial Help" in user_content
        assert "adaptive title refinement" in user_content


class TestMaybeRefineTitle:
    """Tests for adaptive retitling policy and provenance guards."""

    def _history(self, user_turns=4):
        history = []
        for i in range(user_turns):
            history.append({"role": "user", "content": f"user topic turn {i}"})
            history.append({"role": "assistant", "content": f"assistant answer {i}"})
        return history

    def test_refines_auto_title_after_configured_user_turns(self):
        db = FakeTitleDB(
            title="Initial Setup Help",
            model_config={"title_metadata": {"title_source": "auto_initial", "title_turn_count": 1}},
        )
        cfg = {
            "enabled": True,
            "adaptive_retitle": True,
            "retitle_after_user_turns": 4,
            "retitle_auto_titles_only": True,
            "lock_manual_titles": True,
        }

        with patch("agent.title_generator.generate_refined_title", return_value="Hermes Adaptive Titles"):
            maybe_refine_title(db, "sess-1", self._history(4), title_config=cfg, run_in_background=False)

        assert db.set_titles == [("sess-1", "Hermes Adaptive Titles")]
        metadata = db.model_config["title_metadata"]
        assert metadata["title_source"] == "auto_refined"
        assert metadata["title_turn_count"] == 4
        assert metadata["previous_title"] == "Initial Setup Help"

    def test_does_not_overwrite_manual_or_unknown_title_by_default(self):
        db = FakeTitleDB(title="User Chosen Title", model_config={})
        cfg = {
            "enabled": True,
            "adaptive_retitle": True,
            "retitle_after_user_turns": 4,
            "retitle_auto_titles_only": True,
            "lock_manual_titles": True,
        }

        with patch("agent.title_generator.generate_refined_title") as gen:
            maybe_refine_title(db, "sess-1", self._history(4), title_config=cfg, run_in_background=False)

        gen.assert_not_called()
        assert db.set_titles == []
        assert db.title == "User Chosen Title"

    def test_does_not_refine_more_than_once_without_explicit_opt_in(self):
        db = FakeTitleDB(
            title="Already Refined Title",
            model_config={"title_metadata": {"title_source": "auto_refined", "title_turn_count": 4}},
        )
        cfg = {
            "enabled": True,
            "adaptive_retitle": True,
            "retitle_after_user_turns": 4,
            "retitle_auto_titles_only": True,
            "lock_manual_titles": True,
        }

        with patch("agent.title_generator.generate_refined_title") as gen:
            maybe_refine_title(db, "sess-1", self._history(6), title_config=cfg, run_in_background=False)

        gen.assert_not_called()
        assert db.set_titles == []


class TestAutoTitleSession:
    """Tests for auto_title_session() — the sync worker function."""

    def test_skips_if_no_session_db(self):
        auto_title_session(None, "sess-1", "hi", "hello")  # should not crash

    def test_skips_if_title_exists(self):
        db = MagicMock()
        db.get_session_title.return_value = "Existing Title"

        with patch("agent.title_generator.generate_title") as gen:
            auto_title_session(db, "sess-1", "hi", "hello")
            gen.assert_not_called()

    def test_generates_and_sets_title(self):
        db = MagicMock()
        db.get_session_title.return_value = None

        with patch("agent.title_generator.generate_title", return_value="New Title"):
            auto_title_session(db, "sess-1", "hi", "hello")
            db.set_session_title.assert_called_once_with("sess-1", "New Title")

    def test_invokes_title_callback_after_setting_title(self):
        db = MagicMock()
        db.get_session_title.return_value = None
        seen = []
        with patch("agent.title_generator.generate_title", return_value="Readable Session"):
            auto_title_session(
                db,
                "sess-1",
                "hello",
                "hi there",
                title_callback=seen.append,
            )
        db.set_session_title.assert_called_once_with("sess-1", "Readable Session")
        assert seen == ["Readable Session"]

    def test_skips_if_generation_fails(self):
        db = MagicMock()
        db.get_session_title.return_value = None

        with patch("agent.title_generator.generate_title", return_value=None):
            auto_title_session(db, "sess-1", "hi", "hello")
            db.set_session_title.assert_not_called()


class TestMaybeAutoTitle:
    """Tests for maybe_auto_title() — the fire-and-forget entry point."""

    def test_skips_if_not_first_exchange(self):
        """Should not fire for conversations with more than 2 user messages."""
        db = MagicMock()
        history = [
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "response 1"},
            {"role": "user", "content": "second"},
            {"role": "assistant", "content": "response 2"},
            {"role": "user", "content": "third"},
            {"role": "assistant", "content": "response 3"},
        ]

        with patch("agent.title_generator.auto_title_session") as mock_auto:
            maybe_auto_title(db, "sess-1", "third", "response 3", history)
            # Wait briefly for any thread to start
            import time
            time.sleep(0.1)
            mock_auto.assert_not_called()

    def test_fires_on_first_exchange(self):
        """Should fire a background thread for the first exchange."""
        db = MagicMock()
        db.get_session_title.return_value = None
        history = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]

        with patch("agent.title_generator.auto_title_session") as mock_auto:
            maybe_auto_title(db, "sess-1", "hello", "hi there", history)
            # Wait for the daemon thread to complete
            import time
            time.sleep(0.3)
            mock_auto.assert_called_once_with(
                db,
                "sess-1",
                "hello",
                "hi there",
                failure_callback=None,
                main_runtime=None,
                title_callback=None,
            )

    def test_forwards_failure_callback_to_worker(self):
        """maybe_auto_title must forward failure_callback into the thread."""
        db = MagicMock()
        db.get_session_title.return_value = None
        history = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]

        def _cb(task, exc):
            pass

        with patch("agent.title_generator.auto_title_session") as mock_auto:
            maybe_auto_title(db, "sess-1", "hello", "hi there", history, failure_callback=_cb)
            import time
            time.sleep(0.3)
            mock_auto.assert_called_once_with(
                db,
                "sess-1",
                "hello",
                "hi there",
                failure_callback=_cb,
                main_runtime=None,
                title_callback=None,
            )

    def test_skips_if_no_response(self):
        db = MagicMock()
        maybe_auto_title(db, "sess-1", "hello", "", [])  # empty response

    def test_skips_if_no_session_db(self):
        maybe_auto_title(None, "sess-1", "hello", "response", [])  # no db
