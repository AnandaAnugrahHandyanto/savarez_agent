"""Tests for SessionMemory — structured 9-section session notes."""

from unittest.mock import MagicMock, patch

import pytest

from agent.session_memory import (
    DEFAULT_SESSION_MEMORY_TEMPLATE,
    SESSION_SECTIONS,
    SessionMemory,
    _has_valid_sections,
)

# Patch targets — _generate_update does a local import from agent.auxiliary_client
_CALL_LLM = "agent.auxiliary_client.call_llm"
_EXTRACT = "agent.auxiliary_client.extract_content_or_reasoning"


@pytest.fixture
def session_mem():
    """SessionMemory with low thresholds for testing."""
    return SessionMemory(config={
        "minimum_tokens_to_init": 100,  # low for testing
        "minimum_tokens_between_update": 50,
        "tool_calls_between_updates": 2,
        "max_section_length": 500,
    })


class TestBasicUpdate:
    @patch(_EXTRACT)
    @patch(_CALL_LLM)
    def test_update_returns_true_when_thresholds_met(self, mock_call, mock_extract, session_mem):
        updated = DEFAULT_SESSION_MEMORY_TEMPLATE.replace(
            "_A short and distinctive", "Porting Memory Features"
        )
        mock_call.return_value = MagicMock()
        mock_extract.return_value = updated
        messages = [{"role": "user", "content": "test message"}]
        result = session_mem.update(messages, token_count=200, tool_call_count=5)
        assert result is True
        assert session_mem.update_count == 1

    @patch(_EXTRACT)
    @patch(_CALL_LLM)
    def test_update_calls_llm(self, mock_call, mock_extract, session_mem):
        mock_call.return_value = MagicMock()
        mock_extract.return_value = DEFAULT_SESSION_MEMORY_TEMPLATE
        messages = [{"role": "user", "content": "hello"}]
        session_mem.update(messages, token_count=200, tool_call_count=5)
        mock_call.assert_called_once()

    @patch(_EXTRACT)
    @patch(_CALL_LLM)
    def test_update_preserves_notes_on_success(self, mock_call, mock_extract, session_mem):
        updated_notes = DEFAULT_SESSION_MEMORY_TEMPLATE.replace(
            "_A short and distinctive 5-10 word descriptive title for the session. Super info dense, no filler_",
            "My Updated Title"
        )
        mock_call.return_value = MagicMock()
        mock_extract.return_value = updated_notes
        messages = [{"role": "user", "content": "hello"}]
        session_mem.update(messages, token_count=200, tool_call_count=5)
        assert "My Updated Title" in session_mem.get_summary()


class TestThresholdGating:
    @patch(_CALL_LLM)
    def test_below_init_threshold_skips(self, mock_call, session_mem):
        messages = [{"role": "user", "content": "hello"}]
        result = session_mem.update(messages, token_count=50, tool_call_count=5)
        assert result is False
        mock_call.assert_not_called()

    @patch(_EXTRACT)
    @patch(_CALL_LLM)
    def test_below_tool_call_threshold_skips(self, mock_call, mock_extract, session_mem):
        messages = [{"role": "user", "content": "hello"}]
        # First call to initialize
        mock_call.return_value = MagicMock()
        mock_extract.return_value = DEFAULT_SESSION_MEMORY_TEMPLATE
        session_mem.update(messages, token_count=200, tool_call_count=5)
        mock_call.reset_mock()
        # Second call with enough tokens but not enough tool calls
        result = session_mem.update(messages, token_count=260, tool_call_count=6)
        assert result is False

    @patch(_CALL_LLM)
    def test_both_thresholds_needed(self, mock_call, session_mem):
        messages = [{"role": "user", "content": "hello"}]
        # Enough tokens but not enough tool calls since last update
        result = session_mem.update(messages, token_count=200, tool_call_count=1)
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

    @patch(_EXTRACT)
    @patch(_CALL_LLM)
    def test_invalid_response_discarded(self, mock_call, mock_extract, session_mem):
        mock_call.return_value = MagicMock()
        mock_extract.return_value = "This has no sections at all."
        messages = [{"role": "user", "content": "hello"}]
        result = session_mem.update(messages, token_count=200, tool_call_count=5)
        assert result is False
        # Notes should still be the default template
        assert "# Session Title" in session_mem.get_summary()


class TestClear:
    @patch(_EXTRACT)
    @patch(_CALL_LLM)
    def test_clear_resets_to_template(self, mock_call, mock_extract, session_mem):
        mock_call.return_value = MagicMock()
        mock_extract.return_value = DEFAULT_SESSION_MEMORY_TEMPLATE.replace(
            "_A short and distinctive", "Updated Title"
        )
        messages = [{"role": "user", "content": "hello"}]
        session_mem.update(messages, token_count=200, tool_call_count=5)
        assert session_mem.update_count == 1

        session_mem.clear()
        assert session_mem.update_count == 0
        assert session_mem.is_initialized is False
        assert "# Session Title" in session_mem.get_summary()

    @patch(_EXTRACT)
    @patch(_CALL_LLM)
    def test_clear_allows_reinit(self, mock_call, mock_extract, session_mem):
        mock_call.return_value = MagicMock()
        mock_extract.return_value = DEFAULT_SESSION_MEMORY_TEMPLATE
        messages = [{"role": "user", "content": "hello"}]
        session_mem.update(messages, token_count=200, tool_call_count=5)
        session_mem.clear()
        mock_call.reset_mock()
        # Should need to meet init threshold again
        result = session_mem.update(messages, token_count=50, tool_call_count=5)
        assert result is False
