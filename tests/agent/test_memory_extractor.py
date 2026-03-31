"""Tests for automatic memory extraction."""

import json
from unittest.mock import MagicMock, patch

import pytest

from agent.memory_extractor import _do_extraction, _format_messages


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
