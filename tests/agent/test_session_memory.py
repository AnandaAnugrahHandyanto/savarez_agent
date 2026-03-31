"""Tests for SessionMemory — structured 9-section session notes."""

from unittest.mock import MagicMock

import pytest

from agent.session_memory import (
    DEFAULT_SESSION_MEMORY_TEMPLATE,
    SESSION_SECTIONS,
    SessionMemory,
    _has_valid_sections,
)


@pytest.fixture
def mock_aux():
    """Mock auxiliary client."""
    client = MagicMock()
    return client


@pytest.fixture
def session_mem(mock_aux):
    """SessionMemory with default config and mock aux client."""
    return SessionMemory(auxiliary_client=mock_aux, config={
        "minimum_tokens_to_init": 100,  # low for testing
        "minimum_tokens_between_update": 50,
        "tool_calls_between_updates": 2,
        "max_section_length": 500,
    })


class TestBasicUpdate:
    def test_update_returns_true_when_thresholds_met(self, session_mem, mock_aux):
        mock_aux.call_llm.return_value = DEFAULT_SESSION_MEMORY_TEMPLATE.replace(
            "_A short and distinctive", "Porting Memory Features"
        )
        messages = [{"role": "user", "content": "test message"}]
        result = session_mem.update(messages, token_count=200, tool_call_count=5)
        assert result is True
        assert session_mem.update_count == 1

    def test_update_calls_auxiliary_client(self, session_mem, mock_aux):
        mock_aux.call_llm.return_value = DEFAULT_SESSION_MEMORY_TEMPLATE
        messages = [{"role": "user", "content": "hello"}]
        session_mem.update(messages, token_count=200, tool_call_count=5)
        mock_aux.call_llm.assert_called_once()

    def test_update_preserves_notes_on_success(self, session_mem, mock_aux):
        updated_notes = DEFAULT_SESSION_MEMORY_TEMPLATE.replace(
            "_A short and distinctive 5-10 word descriptive title for the session. Super info dense, no filler_",
            "My Updated Title"
        )
        mock_aux.call_llm.return_value = updated_notes
        messages = [{"role": "user", "content": "hello"}]
        session_mem.update(messages, token_count=200, tool_call_count=5)
        assert "My Updated Title" in session_mem.get_summary()


class TestThresholdGating:
    def test_below_init_threshold_skips(self, session_mem, mock_aux):
        messages = [{"role": "user", "content": "hello"}]
        result = session_mem.update(messages, token_count=50, tool_call_count=5)
        assert result is False
        mock_aux.call_llm.assert_not_called()

    def test_below_tool_call_threshold_skips(self, session_mem, mock_aux):
        messages = [{"role": "user", "content": "hello"}]
        # First call to initialize
        mock_aux.call_llm.return_value = DEFAULT_SESSION_MEMORY_TEMPLATE
        session_mem.update(messages, token_count=200, tool_call_count=5)
        mock_aux.call_llm.reset_mock()
        # Second call with enough tokens but not enough tool calls
        result = session_mem.update(messages, token_count=260, tool_call_count=6)
        assert result is False

    def test_both_thresholds_needed(self, session_mem, mock_aux):
        messages = [{"role": "user", "content": "hello"}]
        # Enough tokens but not enough tool calls since last update
        result = session_mem.update(messages, token_count=200, tool_call_count=1)
        assert result is False

    def test_no_aux_client_always_false(self):
        sm = SessionMemory(auxiliary_client=None)
        result = sm.update([], token_count=99999, tool_call_count=99)
        assert result is False


class TestSectionRendering:
    def test_default_template_has_all_sections(self):
        for section in SESSION_SECTIONS:
            assert f"# {section}" in DEFAULT_SESSION_MEMORY_TEMPLATE

    def test_get_summary_returns_default(self):
        sm = SessionMemory()
        summary = sm.get_summary()
        assert "# Session Title" in summary
        assert "# Current State" in summary

    def test_has_valid_sections_passes_for_template(self):
        assert _has_valid_sections(DEFAULT_SESSION_MEMORY_TEMPLATE) is True

    def test_has_valid_sections_fails_for_junk(self):
        assert _has_valid_sections("just some random text") is False

    def test_invalid_response_discarded(self, session_mem, mock_aux):
        mock_aux.call_llm.return_value = "This has no sections at all."
        messages = [{"role": "user", "content": "hello"}]
        result = session_mem.update(messages, token_count=200, tool_call_count=5)
        assert result is False
        # Notes should still be the default template
        assert "# Session Title" in session_mem.get_summary()


class TestClear:
    def test_clear_resets_to_template(self, session_mem, mock_aux):
        mock_aux.call_llm.return_value = DEFAULT_SESSION_MEMORY_TEMPLATE.replace(
            "_A short and distinctive", "Updated Title"
        )
        messages = [{"role": "user", "content": "hello"}]
        session_mem.update(messages, token_count=200, tool_call_count=5)
        assert session_mem.update_count == 1

        session_mem.clear()
        assert session_mem.update_count == 0
        assert session_mem.is_initialized is False
        assert "# Session Title" in session_mem.get_summary()

    def test_clear_allows_reinit(self, session_mem, mock_aux):
        mock_aux.call_llm.return_value = DEFAULT_SESSION_MEMORY_TEMPLATE
        messages = [{"role": "user", "content": "hello"}]
        session_mem.update(messages, token_count=200, tool_call_count=5)
        session_mem.clear()
        # Should need to meet init threshold again
        result = session_mem.update(messages, token_count=50, tool_call_count=5)
        assert result is False
