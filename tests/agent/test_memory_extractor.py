"""Tests for automatic memory extraction."""

import json
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from agent.memory_extractor import (
    _do_extraction,
    _format_messages,
    _run_extraction,
    extract_memories_background,
    get_extractor_state,
    reset_extractor_state,
)


@pytest.fixture
def mock_engine():
    """Mock MemoryEngine for extraction tests."""
    engine = MagicMock()
    engine.get_manifest.return_value = "[abc12345|pref|user] User prefers terse responses"
    engine.add.return_value = {"success": True, "id": "new-id"}
    return engine


@pytest.fixture
def mock_aux_client():
    """Mock auxiliary client that returns extraction results."""
    client = MagicMock()
    return client


class TestFormatMessages:
    def test_basic_formatting(self):
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        result = _format_messages(messages)
        assert "[user] Hello" in result
        assert "[assistant] Hi there" in result

    def test_skips_system_messages(self):
        messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hello"},
        ]
        result = _format_messages(messages)
        assert "system" not in result
        assert "[user] Hello" in result

    def test_truncates_long_messages(self):
        messages = [{"role": "user", "content": "x" * 2000}]
        result = _format_messages(messages)
        assert len(result) < 2000
        assert "..." in result

    def test_respects_budget(self):
        messages = [{"role": "user", "content": "word " * 500}] * 20
        result = _format_messages(messages, max_chars=1000)
        assert len(result) <= 1100  # some slack for formatting

    def test_handles_multipart_content(self):
        messages = [
            {"role": "user", "content": [
                {"type": "text", "text": "Hello"},
                {"type": "text", "text": "World"},
            ]},
        ]
        result = _format_messages(messages)
        assert "Hello" in result
        assert "World" in result


class TestDoExtraction:
    def test_saves_extracted_memories(self, mock_engine, mock_aux_client):
        mock_aux_client.call_llm.return_value = (
            '{"target": "user", "type": "preference", "content": "User likes cats"}\n'
            '{"target": "memory", "type": "project", "content": "Project uses Rust"}'
        )
        _do_extraction(
            recent_messages=[{"role": "user", "content": "I love cats and Rust"}],
            engine=mock_engine,
            auxiliary_client=mock_aux_client,
        )
        assert mock_engine.add.call_count == 2
        calls = mock_engine.add.call_args_list
        assert calls[0].kwargs["target"] == "user"
        assert calls[0].kwargs["type"] == "preference"
        assert calls[1].kwargs["target"] == "memory"
        assert calls[1].kwargs["source"] == "extraction"

    def test_none_response_skips(self, mock_engine, mock_aux_client):
        mock_aux_client.call_llm.return_value = "NONE"
        _do_extraction(
            recent_messages=[{"role": "user", "content": "boring stuff"}],
            engine=mock_engine,
            auxiliary_client=mock_aux_client,
        )
        mock_engine.add.assert_not_called()

    def test_empty_response_skips(self, mock_engine, mock_aux_client):
        mock_aux_client.call_llm.return_value = ""
        _do_extraction(
            recent_messages=[{"role": "user", "content": "test"}],
            engine=mock_engine,
            auxiliary_client=mock_aux_client,
        )
        mock_engine.add.assert_not_called()

    def test_malformed_json_skipped(self, mock_engine, mock_aux_client):
        mock_aux_client.call_llm.return_value = (
            'not json at all\n'
            '{"target": "memory", "type": "general", "content": "valid entry"}\n'
            '{broken json'
        )
        _do_extraction(
            recent_messages=[{"role": "user", "content": "test"}],
            engine=mock_engine,
            auxiliary_client=mock_aux_client,
        )
        # Only the valid line should be saved
        assert mock_engine.add.call_count == 1

    def test_passes_manifest_for_dedup(self, mock_engine, mock_aux_client):
        mock_aux_client.call_llm.return_value = "NONE"
        _do_extraction(
            recent_messages=[{"role": "user", "content": "test"}],
            engine=mock_engine,
            auxiliary_client=mock_aux_client,
        )
        mock_engine.get_manifest.assert_called_once()
        # Check manifest was included in the LLM prompt
        call_kwargs = mock_aux_client.call_llm.call_args.kwargs
        assert "terse responses" in call_kwargs.get("prompt", "")

    def test_invalid_target_skipped(self, mock_engine, mock_aux_client):
        mock_aux_client.call_llm.return_value = (
            '{"target": "invalid", "type": "general", "content": "bad target"}'
        )
        _do_extraction(
            recent_messages=[{"role": "user", "content": "test"}],
            engine=mock_engine,
            auxiliary_client=mock_aux_client,
        )
        mock_engine.add.assert_not_called()

    def test_strips_code_fences(self, mock_engine, mock_aux_client):
        mock_aux_client.call_llm.return_value = (
            '```json\n'
            '{"target": "memory", "type": "general", "content": "fact"}\n'
            '```'
        )
        _do_extraction(
            recent_messages=[{"role": "user", "content": "test"}],
            engine=mock_engine,
            auxiliary_client=mock_aux_client,
        )
        assert mock_engine.add.call_count == 1

    def test_llm_failure_handled(self, mock_engine, mock_aux_client):
        mock_aux_client.call_llm.side_effect = RuntimeError("API error")
        # Should not raise
        _do_extraction(
            recent_messages=[{"role": "user", "content": "test"}],
            engine=mock_engine,
            auxiliary_client=mock_aux_client,
        )
        mock_engine.add.assert_not_called()


# ---------------------------------------------------------------------------
# Cursor Tracking Tests
# ---------------------------------------------------------------------------


class TestCursorTracking:
    def setup_method(self):
        reset_extractor_state()

    def test_cursor_advances_after_extraction(self, mock_engine, mock_aux_client):
        """Cursor should advance to the last message index after successful extraction."""
        mock_aux_client.call_llm.return_value = "NONE"
        messages = [
            {"role": "user", "content": "msg1"},
            {"role": "assistant", "content": "resp1"},
            {"role": "user", "content": "msg2"},
        ]

        from agent.memory_extractor import _run_extraction
        _run_extraction(
            recent_messages=messages,
            engine=mock_engine,
            auxiliary_client=mock_aux_client,
        )
        state = get_extractor_state()
        assert state.last_extracted_message_index == 2  # len(messages) - 1

    def test_cursor_skips_already_processed(self, mock_engine, mock_aux_client):
        """Second extraction should only process new messages."""
        call_count = 0
        prompts_seen = []

        def track_calls(**kwargs):
            nonlocal call_count
            call_count += 1
            prompts_seen.append(kwargs.get("prompt", ""))
            return "NONE"

        mock_aux_client.call_llm.side_effect = track_calls
        state = get_extractor_state()

        messages_1 = [
            {"role": "user", "content": "first message"},
            {"role": "assistant", "content": "first response"},
        ]

        from agent.memory_extractor import _run_extraction
        _run_extraction(
            recent_messages=messages_1,
            engine=mock_engine,
            auxiliary_client=mock_aux_client,
        )
        assert call_count == 1

        # Add new messages
        messages_2 = messages_1 + [
            {"role": "user", "content": "second message"},
            {"role": "assistant", "content": "second response"},
        ]

        _run_extraction(
            recent_messages=messages_2,
            engine=mock_engine,
            auxiliary_client=mock_aux_client,
        )
        assert call_count == 2
        # Second call should only contain the new messages
        assert "second message" in prompts_seen[1]

    def test_cursor_reset_processes_all(self, mock_engine, mock_aux_client):
        """After reset, all messages should be processed."""
        mock_aux_client.call_llm.return_value = "NONE"
        messages = [{"role": "user", "content": "test"}]

        from agent.memory_extractor import _run_extraction
        _run_extraction(
            recent_messages=messages,
            engine=mock_engine,
            auxiliary_client=mock_aux_client,
        )
        reset_extractor_state()
        mock_aux_client.call_llm.reset_mock()

        _run_extraction(
            recent_messages=messages,
            engine=mock_engine,
            auxiliary_client=mock_aux_client,
        )
        # Should have been called since cursor was reset
        mock_aux_client.call_llm.assert_called_once()


# ---------------------------------------------------------------------------
# Mutual Exclusion Tests
# ---------------------------------------------------------------------------


class TestMutualExclusion:
    def setup_method(self):
        reset_extractor_state()

    def test_agent_wrote_memory_skips_extraction(self, mock_engine, mock_aux_client):
        """When agent wrote memories this turn, extraction should be skipped."""
        state = get_extractor_state()
        state.mark_agent_wrote_memory()

        mock_store = MagicMock()
        mock_store._engine = mock_engine

        messages = [{"role": "user", "content": "test"}]
        extract_memories_background(
            recent_messages=messages,
            memory_store=mock_store,
            auxiliary_client=mock_aux_client,
        )
        # Give the background thread time (it shouldn't start)
        time.sleep(0.1)
        mock_aux_client.call_llm.assert_not_called()

    def test_agent_wrote_memory_advances_cursor(self, mock_engine, mock_aux_client):
        """When skipped due to agent write, cursor should still advance."""
        state = get_extractor_state()
        state.mark_agent_wrote_memory()

        mock_store = MagicMock()
        mock_store._engine = mock_engine

        messages = [
            {"role": "user", "content": "msg1"},
            {"role": "assistant", "content": "resp1"},
        ]
        extract_memories_background(
            recent_messages=messages,
            memory_store=mock_store,
            auxiliary_client=mock_aux_client,
        )
        time.sleep(0.1)
        assert state.last_extracted_message_index == 1

    def test_clear_agent_wrote_memory(self):
        """Flag should be clearable."""
        state = get_extractor_state()
        state.mark_agent_wrote_memory()
        assert state.agent_wrote_memory is True
        state.clear_agent_wrote_memory()
        assert state.agent_wrote_memory is False

    def test_stash_trailing_run(self, mock_engine, mock_aux_client):
        """When extraction is in progress, context should be stashed."""
        state = get_extractor_state()

        # Simulate in-progress by setting the flag directly
        with state._lock:
            state._in_progress = True

        mock_store = MagicMock()
        mock_store._engine = mock_engine

        messages = [{"role": "user", "content": "stashed message"}]
        extract_memories_background(
            recent_messages=messages,
            memory_store=mock_store,
            auxiliary_client=mock_aux_client,
        )

        # Should have stashed, not started a new thread
        assert state._pending_context is not None
        assert state._pending_context["recent_messages"] == messages

        # Clean up
        with state._lock:
            state._in_progress = False
            state._pending_context = None
