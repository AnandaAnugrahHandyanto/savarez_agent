"""Tests for tools/mem0_tools.py — Mem0 tool handlers."""

import json
from unittest.mock import MagicMock

import pytest

from tools.mem0_tools import (
    set_mem0_context,
    clear_mem0_context,
    _check_mem0_available,
    _handle_mem0_profile,
    _handle_mem0_search,
    _handle_mem0_context,
    _handle_mem0_conclude,
)


@pytest.fixture(autouse=True)
def clean_context():
    """Reset module state before each test."""
    clear_mem0_context()
    yield
    clear_mem0_context()


@pytest.fixture
def mock_manager():
    mgr = MagicMock()
    mgr.get_profile.return_value = [
        {"id": "m1", "memory": "Likes Python"},
        {"id": "m2", "memory": "Works at Acme"},
    ]
    mgr.search.return_value = [
        {"id": "m1", "memory": "Likes Python", "score": 0.9},
    ]
    mgr.store_fact.return_value = {"results": [{"status": "ok"}]}
    return mgr


class TestAvailability:
    def test_unavailable_by_default(self):
        assert _check_mem0_available() is False

    def test_available_after_set_context(self, mock_manager):
        set_mem0_context(mock_manager, "testuser")
        assert _check_mem0_available() is True

    def test_unavailable_after_clear(self, mock_manager):
        set_mem0_context(mock_manager, "testuser")
        clear_mem0_context()
        assert _check_mem0_available() is False


class TestProfile:
    def test_returns_memories(self, mock_manager):
        set_mem0_context(mock_manager, "testuser")
        result = json.loads(_handle_mem0_profile({}))
        assert "result" in result
        assert len(result["result"]) == 2

    def test_error_when_not_active(self):
        result = json.loads(_handle_mem0_profile({}))
        assert "error" in result

    def test_empty_profile(self, mock_manager):
        mock_manager.get_profile.return_value = []
        set_mem0_context(mock_manager, "testuser")
        result = json.loads(_handle_mem0_profile({}))
        assert "result" in result
        assert "No memories" in result["result"]


class TestSearch:
    def test_search_with_query(self, mock_manager):
        set_mem0_context(mock_manager, "testuser")
        result = json.loads(_handle_mem0_search({"query": "programming"}))
        assert "result" in result
        mock_manager.search.assert_called_once()

    def test_error_without_query(self, mock_manager):
        set_mem0_context(mock_manager, "testuser")
        result = json.loads(_handle_mem0_search({}))
        assert "error" in result

    def test_rerank_flag_passed(self, mock_manager):
        set_mem0_context(mock_manager, "testuser")
        _handle_mem0_search({"query": "test", "rerank": True})
        _, kwargs = mock_manager.search.call_args
        assert kwargs["rerank"] is True

    def test_top_k_capped(self, mock_manager):
        set_mem0_context(mock_manager, "testuser")
        _handle_mem0_search({"query": "test", "top_k": 100})
        _, kwargs = mock_manager.search.call_args
        assert kwargs["top_k"] == 50


class TestContext:
    def test_context_uses_rerank(self, mock_manager):
        set_mem0_context(mock_manager, "testuser")
        result = json.loads(_handle_mem0_context({"query": "user goals"}))
        assert "result" in result
        _, kwargs = mock_manager.search.call_args
        assert kwargs["rerank"] is True
        assert kwargs["top_k"] == 5

    def test_error_without_query(self, mock_manager):
        set_mem0_context(mock_manager, "testuser")
        result = json.loads(_handle_mem0_context({}))
        assert "error" in result


class TestConclude:
    def test_stores_fact(self, mock_manager):
        set_mem0_context(mock_manager, "testuser")
        result = json.loads(_handle_mem0_conclude({"conclusion": "Prefers dark mode"}))
        assert "result" in result
        mock_manager.store_fact.assert_called_once_with("Prefers dark mode", "testuser")

    def test_error_without_conclusion(self, mock_manager):
        set_mem0_context(mock_manager, "testuser")
        result = json.loads(_handle_mem0_conclude({}))
        assert "error" in result

    def test_error_when_not_active(self):
        result = json.loads(_handle_mem0_conclude({"conclusion": "test"}))
        assert "error" in result
