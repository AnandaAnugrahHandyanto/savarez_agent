"""Tests for the claude-mem memory provider plugin.

Covers is_available, initialize (primary/subagent/cron), prefetch (semantic
+ search fallback + worker-down path), tool dispatch (recall/save/timeline/
unknown), non-blocking sync_turn, and on_session_end. All HTTP calls are
mocked via ``provider._client = MagicMock()`` — no network traffic.
"""
import json
import sys
import time
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Ensure no stale claude-mem env vars leak between tests."""
    for key in ("CLAUDE_MEM_WORKER_URL", "CLAUDE_MEM_DEFAULT_PROJECT"):
        monkeypatch.delenv(key, raising=False)


@pytest.fixture()
def provider_cls(tmp_path, monkeypatch):
    """Fresh ClaudeMemMemoryProvider instance loaded via the plugin loader."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    from plugins.memory import load_memory_provider

    p = load_memory_provider("claude-mem")
    assert p is not None
    return p


@pytest.fixture()
def client_module():
    """The claude-mem client submodule (hyphenated; must be looked up via sys.modules)."""
    # load_memory_provider triggers import of both parent and client submodule.
    from plugins.memory import load_memory_provider

    assert load_memory_provider("claude-mem") is not None
    mod = sys.modules.get("plugins.memory.claude-mem.client")
    assert mod is not None, "claude-mem client submodule was not registered"
    return mod


@pytest.fixture()
def provider(provider_cls, tmp_path):
    """Provider initialized in primary context with a mocked HTTP client."""
    provider_cls.initialize(
        session_id="test-content-session-abc",
        hermes_home=str(tmp_path),
        platform="cli",
        agent_context="primary",
        agent_workspace="test-project",
    )
    # Replace the real HTTP client with a mock so no network calls happen.
    provider_cls._client = MagicMock()
    # Drain the background init thread so subsequent assertions are stable.
    time.sleep(0.2)
    return provider_cls


# ---------------------------------------------------------------------------
# is_available
# ---------------------------------------------------------------------------


def test_is_available_true_when_requests_installed(provider_cls):
    assert provider_cls.is_available() is True


# ---------------------------------------------------------------------------
# initialize
# ---------------------------------------------------------------------------


def test_initialize_primary_posts_init_async(provider_cls, client_module, tmp_path, monkeypatch):
    """Primary context: init_session is called asynchronously via a daemon thread."""
    fake_client = MagicMock()
    # Patch the ClaudeMemClient constructor on the client submodule so that
    # when initialize() does `from .client import ClaudeMemClient`, it picks
    # up our mock factory.
    monkeypatch.setattr(client_module, "ClaudeMemClient", lambda **kw: fake_client)

    provider_cls.initialize(
        session_id="sess-xyz",
        hermes_home=str(tmp_path),
        platform="cli",
        agent_context="primary",
        agent_workspace="my-proj",
    )
    # Allow the background init thread to run.
    time.sleep(0.3)

    fake_client.init_session.assert_called_once()
    call_kwargs = fake_client.init_session.call_args.kwargs
    assert call_kwargs["content_session_id"] == "sess-xyz"
    assert call_kwargs["project"] == "my-proj"
    assert call_kwargs["platform_source"] == "hermes-cli"


def test_initialize_subagent_skips_init(provider_cls, client_module, tmp_path, monkeypatch):
    """agent_context='subagent' must NOT fire init_session."""
    fake_client = MagicMock()
    monkeypatch.setattr(client_module, "ClaudeMemClient", lambda **kw: fake_client)

    provider_cls.initialize(
        session_id="sub-1",
        hermes_home=str(tmp_path),
        platform="cli",
        agent_context="subagent",
        agent_workspace="proj",
    )
    time.sleep(0.2)
    fake_client.init_session.assert_not_called()


def test_initialize_cron_skips_init(provider_cls, client_module, tmp_path, monkeypatch):
    """platform='cron' must NOT fire init_session."""
    fake_client = MagicMock()
    monkeypatch.setattr(client_module, "ClaudeMemClient", lambda **kw: fake_client)

    provider_cls.initialize(
        session_id="cron-1",
        hermes_home=str(tmp_path),
        platform="cron",
        agent_context="primary",
        agent_workspace="proj",
    )
    time.sleep(0.2)
    fake_client.init_session.assert_not_called()


# ---------------------------------------------------------------------------
# prefetch / queue_prefetch
# ---------------------------------------------------------------------------


def test_prefetch_returns_cached_context(provider):
    """Long (>=20 char) query routes through context_semantic; prefetch returns the cached markdown."""
    provider._client.context_semantic.return_value = {
        "context": "some markdown recall",
        "count": 1,
    }
    provider.queue_prefetch("this is a query longer than twenty characters")
    # prefetch() joins the background thread (up to 3s) and returns the cache.
    result = provider.prefetch("this is a query longer than twenty characters")

    provider._client.context_semantic.assert_called_once()
    provider._client.search.assert_not_called()
    assert "some markdown recall" in result


def test_prefetch_short_query_uses_search_fallback(provider):
    """Queries shorter than 20 chars should fall back to /api/search, not context_semantic."""
    markdown = "- obs 1\n- obs 2"
    provider._client.search.return_value = {
        "text": markdown,
        "raw": {"content": [{"type": "text", "text": markdown}]},
    }
    provider.queue_prefetch("short")  # 5 chars
    # Drain the background worker.
    if provider._prefetch_thread:
        provider._prefetch_thread.join(timeout=3.0)

    provider._client.search.assert_called_once()
    provider._client.context_semantic.assert_not_called()
    # The prefetch worker wraps the markdown in "## Claude-Mem Recall\n...".
    result = provider.prefetch("short")
    assert "## Claude-Mem Recall" in result
    assert markdown in result


def test_prefetch_returns_empty_on_worker_down(provider, client_module):
    """If the worker raises ClaudeMemUnavailable, prefetch returns '' — no exception."""
    unavailable_exc = client_module.ClaudeMemUnavailable
    provider._client.context_semantic.side_effect = unavailable_exc("worker down")

    provider.queue_prefetch("this query is definitely long enough to trigger semantic")
    result = provider.prefetch("this query is definitely long enough to trigger semantic")

    assert result == ""


# ---------------------------------------------------------------------------
# handle_tool_call dispatch
# ---------------------------------------------------------------------------


def test_recall_tool_routes_to_search(provider):
    markdown = "## Results\n- hit A\n- hit B"
    provider._client.search.return_value = {
        "text": markdown,
        "raw": {"content": [{"type": "text", "text": markdown}]},
    }
    result_str = provider.handle_tool_call(
        "claude_mem_recall", {"query": "test", "limit": 5}
    )
    assert isinstance(result_str, str)
    result = json.loads(result_str)
    assert result == {"results_markdown": markdown}
    provider._client.search.assert_called_once()


def test_recall_tool_empty_text_returns_no_match_message(provider):
    """When the worker returns no markdown, recall surfaces a human-friendly sentinel."""
    provider._client.search.return_value = {
        "text": "",
        "raw": {"content": [{"type": "text", "text": ""}]},
    }
    result_str = provider.handle_tool_call(
        "claude_mem_recall", {"query": "nothing matches", "limit": 5}
    )
    assert json.loads(result_str) == {"results_markdown": "No matching observations."}


def test_save_tool_routes_to_memory_save(provider):
    provider._client.memory_save.return_value = {"ok": True, "id": 42}
    result_str = provider.handle_tool_call(
        "claude_mem_save", {"text": "remember this", "title": "note"}
    )
    assert isinstance(result_str, str)
    assert json.loads(result_str) == {"ok": True, "id": 42}
    provider._client.memory_save.assert_called_once()


def test_timeline_tool_routes_to_timeline(provider):
    markdown = "## Timeline around #7\n- #5 foo\n- #7 anchor\n- #9 bar"
    provider._client.timeline.return_value = {
        "text": markdown,
        "raw": {"content": [{"type": "text", "text": markdown}]},
    }
    result_str = provider.handle_tool_call(
        "claude_mem_timeline",
        {"anchor_id": 7, "depth_before": 2, "depth_after": 2},
    )
    assert isinstance(result_str, str)
    assert json.loads(result_str) == {"timeline_markdown": markdown}
    provider._client.timeline.assert_called_once()


def test_unknown_tool_returns_json_error(provider):
    result_str = provider.handle_tool_call("bogus", {})
    assert isinstance(result_str, str)
    assert json.loads(result_str) == {"error": "unknown tool: bogus"}


# ---------------------------------------------------------------------------
# sync_turn non-blocking contract
# ---------------------------------------------------------------------------


def test_sync_turn_is_non_blocking(provider):
    """sync_turn must return in <100ms even if the underlying HTTP call is slow."""
    def slow(*a, **kw):
        time.sleep(1.0)

    provider._client.post_observation.side_effect = slow

    t0 = time.time()
    provider.sync_turn("u", "a", session_id="test-content-session-abc")
    elapsed = time.time() - t0
    assert elapsed < 0.1, f"sync_turn must return in <100ms, took {elapsed:.3f}s"

    # The background thread should eventually complete.
    if provider._sync_thread:
        provider._sync_thread.join(timeout=5.0)
        assert not provider._sync_thread.is_alive()
    provider._client.post_observation.assert_called_once()


# ---------------------------------------------------------------------------
# on_session_end
# ---------------------------------------------------------------------------


def test_on_session_end_fires_complete(provider):
    """on_session_end must fire a complete_session call exactly once."""
    provider.on_session_end([])
    # Background daemon thread fires-and-forgets; wait briefly.
    time.sleep(0.2)
    provider._client.complete_session.assert_called_once()


# ---------------------------------------------------------------------------
# JSON-string contract
# ---------------------------------------------------------------------------


def test_handle_tool_call_returns_string(provider):
    """Every tool call result must be a string (per MemoryProvider ABC)."""
    provider._client.search.return_value = {
        "text": "",
        "raw": {"content": [{"type": "text", "text": ""}]},
    }
    provider._client.memory_save.return_value = {}
    provider._client.timeline.return_value = {
        "text": "",
        "raw": {"content": [{"type": "text", "text": ""}]},
    }

    calls = [
        ("claude_mem_recall", {"query": "x"}),
        ("claude_mem_save", {"text": "y"}),
        ("claude_mem_timeline", {"anchor_id": 1}),
        ("bogus", {}),
    ]
    for name, args in calls:
        result = provider.handle_tool_call(name, args)
        assert isinstance(result, str), f"{name} returned {type(result)}"
        # And it must be valid JSON.
        json.loads(result)


# ---------------------------------------------------------------------------
# _extract_mcp_text malformed-envelope handling
# ---------------------------------------------------------------------------


def test_extract_mcp_text_handles_malformed_envelopes(client_module):
    """_extract_mcp_text must never raise on bad envelopes — it returns '' instead."""
    ClaudeMemClient = client_module.ClaudeMemClient

    # Missing content key.
    assert ClaudeMemClient._extract_mcp_text({}) == ""
    # Empty content list.
    assert ClaudeMemClient._extract_mcp_text({"content": []}) == ""
    # Non-dict element inside content.
    assert ClaudeMemClient._extract_mcp_text({"content": ["not a dict"]}) == ""
    # Dict element missing the text key.
    assert ClaudeMemClient._extract_mcp_text({"content": [{"type": "text"}]}) == ""
    # Happy path: text is extracted verbatim.
    assert (
        ClaudeMemClient._extract_mcp_text(
            {"content": [{"type": "text", "text": "hi"}]}
        )
        == "hi"
    )
