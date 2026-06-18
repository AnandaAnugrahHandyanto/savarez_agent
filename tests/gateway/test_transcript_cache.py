"""Tests for gateway transcript cache (_load_transcript_sync)."""

from __future__ import annotations

from collections import OrderedDict
from unittest.mock import MagicMock

import pytest

from gateway.config import GatewayConfig
from gateway.run import GatewayRunner


@pytest.fixture
def runner():
    gw = GatewayRunner(GatewayConfig())
    gw._transcript_cache = OrderedDict()
    gw._session_db = MagicMock()
    gw.session_store = MagicMock()
    return gw


def test_transcript_cache_hit_skips_load_transcript(runner):
    history = [{"role": "user", "content": "hello"}]
    runner._session_db.get_transcript_cache_token.return_value = (1, 42)
    runner.session_store.load_transcript.return_value = history

    first = runner._load_transcript_sync("session-1", "key-1")
    second = runner._load_transcript_sync("session-1", "key-1")

    assert first is history
    assert second is history
    runner.session_store.load_transcript.assert_called_once_with("session-1")


def test_transcript_cache_miss_on_token_change(runner):
    history_v1 = [{"role": "user", "content": "v1"}]
    history_v2 = history_v1 + [{"role": "assistant", "content": "v2"}]
    runner.session_store.load_transcript.side_effect = [history_v1, history_v2]

    runner._session_db.get_transcript_cache_token.return_value = (1, 10)
    runner._load_transcript_sync("session-1", "key-1")

    runner._session_db.get_transcript_cache_token.return_value = (2, 11)
    second = runner._load_transcript_sync("session-1", "key-1")

    assert second is history_v2
    assert runner.session_store.load_transcript.call_count == 2


def test_transcript_cache_miss_when_head_id_changes_same_count(runner):
    """Rewrites/rewinds can change active head id without changing count."""
    history_v1 = [{"role": "user", "content": "before"}]
    history_v2 = [{"role": "user", "content": "after"}]
    runner.session_store.load_transcript.side_effect = [history_v1, history_v2]

    runner._session_db.get_transcript_cache_token.return_value = (1, 10)
    runner._load_transcript_sync("session-1", "key-1")

    runner._session_db.get_transcript_cache_token.return_value = (1, 20)
    second = runner._load_transcript_sync("session-1", "key-1")

    assert second is history_v2
    assert runner.session_store.load_transcript.call_count == 2


def test_transcript_cache_invalidated_on_evict(runner):
    history = [{"role": "user", "content": "hello"}]
    runner._session_db.get_transcript_cache_token.return_value = (1, 42)
    runner.session_store.load_transcript.return_value = history

    runner._load_transcript_sync("session-1", "key-1")
    runner._invalidate_transcript_cache("key-1")
    runner._load_transcript_sync("session-1", "key-1")

    assert runner.session_store.load_transcript.call_count == 2


def test_transcript_cache_invalidated_by_session_id(runner):
    history = [{"role": "user", "content": "hello"}]
    runner._session_db.get_transcript_cache_token.return_value = (1, 42)
    runner.session_store.load_transcript.return_value = history

    runner._load_transcript_sync("session-1", "key-1")
    runner._invalidate_transcript_cache_for_session_id("session-1")
    runner._load_transcript_sync("session-1", "key-1")

    assert runner.session_store.load_transcript.call_count == 2


def test_transcript_cache_miss_on_session_id_change(runner):
    history_a = [{"role": "user", "content": "a"}]
    history_b = [{"role": "user", "content": "b"}]
    runner.session_store.load_transcript.side_effect = [history_a, history_b]
    runner._session_db.get_transcript_cache_token.return_value = (1, 1)

    runner._load_transcript_sync("session-a", "key-1")
    second = runner._load_transcript_sync("session-b", "key-1")

    assert second is history_b
    assert runner.session_store.load_transcript.call_count == 2
