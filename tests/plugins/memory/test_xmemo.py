"""Tests for the XMemo memory provider plugin."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

import pytest

from plugins.memory.xmemo import XMemoMemoryProvider


class FakeXMemoClient:
    """Fake synchronous XMemo REST client for unit tests."""

    def __init__(
        self,
        search_results: Optional[List[Dict[str, Any]]] = None,
        recall_context: Optional[Dict[str, Any]] = None,
    ):
        self.search_results = search_results or []
        self.recall_context_response = recall_context or {}
        self.captured_calls: List[Dict[str, Any]] = []

    def _record(self, method: str, **kwargs):
        self.captured_calls.append({"method": method, **kwargs})

    def health(self):
        self._record("health")
        return {"status": "ok"}

    def recall_context(self, **kwargs):
        self._record("recall_context", **kwargs)
        return self.recall_context_response

    def search(self, **kwargs):
        self._record("search", **kwargs)
        return self.search_results

    def remember(self, **kwargs):
        self._record("remember", **kwargs)
        return {"id": "mem-test-123"}

    def update_state(self, **kwargs):
        self._record("update_state", **kwargs)
        return {"state_key": kwargs.get("state_key", "active_task"), "id": "state-123"}

    def record_event(self, **kwargs):
        self._record("record_event", **kwargs)
        return {"id": "event-123"}

    def create_restart_snapshot(self, **kwargs):
        self._record("create_restart_snapshot", **kwargs)
        return {"id": "snapshot-123"}

    def close(self):
        self._record("close")


@pytest.fixture
def provider_with_config(monkeypatch, tmp_path):
    """Create an initialized provider with a fake client."""
    monkeypatch.setenv("XMEMO_KEY", "test-key")
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("XMEMO_AGENT_INSTANCE_ID", "test-instance")

    provider = XMemoMemoryProvider()
    provider.initialize("test-session")
    return provider


class TestAvailability:
    """is_available must be fast and network-free."""

    def test_not_available_without_key(self, monkeypatch, tmp_path):
        monkeypatch.delenv("XMEMO_KEY", raising=False)
        monkeypatch.delenv("MEMORY_OS_API_KEY", raising=False)
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))

        provider = XMemoMemoryProvider()
        assert provider.is_available() is False

    def test_available_with_env_key(self, monkeypatch, tmp_path):
        monkeypatch.setenv("XMEMO_KEY", "test-key")
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))

        provider = XMemoMemoryProvider()
        assert provider.is_available() is True

    def test_available_with_legacy_env_key(self, monkeypatch, tmp_path):
        monkeypatch.delenv("XMEMO_KEY", raising=False)
        monkeypatch.setenv("MEMORY_OS_API_KEY", "legacy-key")
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))

        provider = XMemoMemoryProvider()
        assert provider.is_available() is True


class TestLifecycle:
    """Initialization and shutdown behavior."""

    def test_initialize_loads_config(self, provider_with_config):
        assert provider_with_config._config["api_key"] == "test-key"
        assert provider_with_config._config["agent_id"] == "hermes"
        assert provider_with_config._session_id == "test-session"

    def test_system_prompt_block_active(self, provider_with_config):
        block = provider_with_config.system_prompt_block()
        assert "XMemo Memory" in block
        assert "xmemo_search" in block
        assert "xmemo_remember" in block

    def test_system_prompt_block_empty_when_not_configured(self, monkeypatch, tmp_path):
        monkeypatch.delenv("XMEMO_KEY", raising=False)
        monkeypatch.delenv("MEMORY_OS_API_KEY", raising=False)
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))

        provider = XMemoMemoryProvider()
        provider.initialize("test-session")
        assert provider.system_prompt_block() == ""

    def test_name_property(self):
        provider = XMemoMemoryProvider()
        assert provider.name == "xmemo"


class TestTools:
    """Tool handlers route to the correct API calls."""

    def test_search_tool(self, provider_with_config, monkeypatch):
        fake = FakeXMemoClient(
            search_results=[
                {"content": "user prefers dark mode", "memory_type": "semantic", "similarity": 0.92},
            ]
        )
        monkeypatch.setattr(provider_with_config, "_get_client", lambda: fake)

        result = json.loads(
            provider_with_config.handle_tool_call("xmemo_search", {"query": "preferences"})
        )

        assert result["count"] == 1
        assert result["results"][0]["content"] == "user prefers dark mode"
        assert fake.captured_calls[0]["method"] == "search"
        assert fake.captured_calls[0]["query"] == "preferences"

    def test_search_tool_missing_query(self, provider_with_config, monkeypatch):
        fake = FakeXMemoClient()
        monkeypatch.setattr(provider_with_config, "_get_client", lambda: fake)

        result = json.loads(provider_with_config.handle_tool_call("xmemo_search", {}))
        assert "error" in result

    def test_remember_tool(self, provider_with_config, monkeypatch):
        fake = FakeXMemoClient()
        monkeypatch.setattr(provider_with_config, "_get_client", lambda: fake)

        result = json.loads(
            provider_with_config.handle_tool_call(
                "xmemo_remember",
                {"content": "user likes small PRs", "path": "hermes/preferences"},
            )
        )

        assert result["result"] == "Saved to XMemo."
        assert result["memory_id"] == "mem-test-123"
        assert fake.captured_calls[0]["method"] == "remember"
        assert fake.captured_calls[0]["content"] == "user likes small PRs"

    def test_remember_tool_missing_content(self, provider_with_config, monkeypatch):
        fake = FakeXMemoClient()
        monkeypatch.setattr(provider_with_config, "_get_client", lambda: fake)

        result = json.loads(
            provider_with_config.handle_tool_call(
                "xmemo_remember", {"path": "hermes/preferences"}
            )
        )
        assert "error" in result

    def test_update_state_tool(self, provider_with_config, monkeypatch):
        fake = FakeXMemoClient()
        monkeypatch.setattr(provider_with_config, "_get_client", lambda: fake)

        result = json.loads(
            provider_with_config.handle_tool_call(
                "xmemo_update_state",
                {"current_task": "Implement XMemo plugin", "next_action": "Write tests"},
            )
        )

        assert result["result"] == "Working state saved to XMemo."
        assert fake.captured_calls[0]["method"] == "update_state"
        assert fake.captured_calls[0]["current_task"] == "Implement XMemo plugin"

    def test_update_state_tool_missing_fields(self, provider_with_config, monkeypatch):
        fake = FakeXMemoClient()
        monkeypatch.setattr(provider_with_config, "_get_client", lambda: fake)

        result = json.loads(
            provider_with_config.handle_tool_call("xmemo_update_state", {})
        )
        assert "error" in result


class TestPrefetch:
    """Background recall and prefetch behavior."""

    def test_queue_prefetch_populates_result(self, provider_with_config, monkeypatch):
        fake = FakeXMemoClient(
            recall_context={
                "context_text": "User is working on the XMemo integration.",
                "items": [{"content": "User is working on the XMemo integration."}],
            }
        )
        monkeypatch.setattr(provider_with_config, "_get_client", lambda: fake)

        provider_with_config.queue_prefetch("current task")
        provider_with_config._prefetch_thread.join(timeout=2)

        result = provider_with_config.prefetch("current task")
        assert "XMemo integration" in result
        assert fake.captured_calls[0]["method"] == "recall_context"
        assert fake.captured_calls[0]["query"] == "current task"

    def test_prefetch_skips_trivial_prompts(self, provider_with_config, monkeypatch):
        fake = FakeXMemoClient()
        monkeypatch.setattr(provider_with_config, "_get_client", lambda: fake)

        provider_with_config.queue_prefetch("ok")
        # No thread should have been started
        assert provider_with_config._prefetch_thread is None
        assert provider_with_config.prefetch("ok") == ""

    def test_prefetch_returns_empty_when_no_result(self, provider_with_config):
        result = provider_with_config.prefetch("anything")
        assert result == ""


class TestSyncTurn:
    """Turn synchronization records lightweight events."""

    def test_sync_turn_records_event(self, provider_with_config, monkeypatch):
        fake = FakeXMemoClient()
        monkeypatch.setattr(provider_with_config, "_get_client", lambda: fake)

        provider_with_config.sync_turn("hello", "hi there", session_id="s1")
        provider_with_config._sync_thread.join(timeout=2)

        assert len(fake.captured_calls) == 1
        assert fake.captured_calls[0]["method"] == "record_event"
        assert fake.captured_calls[0]["session_id"] == "s1"


class TestCircuitBreaker:
    """Consecutive failures should pause API calls temporarily."""

    def test_circuit_breaker_trips(self, provider_with_config, monkeypatch):
        class FailingClient:
            def search(self, **kwargs):
                raise RuntimeError("network down")

            def close(self):
                pass

        monkeypatch.setattr(provider_with_config, "_get_client", lambda: FailingClient())

        # Trigger enough failures to trip the breaker
        for _ in range(6):
            provider_with_config.handle_tool_call("xmemo_search", {"query": "x"})

        assert provider_with_config._is_breaker_open() is True

        # After the breaker is open, calls return immediately without hitting client
        result = json.loads(
            provider_with_config.handle_tool_call("xmemo_search", {"query": "y"})
        )
        assert "temporarily unavailable" in result["error"]


class TestConfigSchema:
    """Setup wizard integration."""

    def test_config_schema_has_api_key(self):
        provider = XMemoMemoryProvider()
        schema = provider.get_config_schema()
        keys = {field["key"] for field in schema}
        assert "api_key" in keys
        assert "base_url" in keys
        assert "scope" in keys

    def test_save_config_does_not_persist_api_key(self, tmp_path):
        provider = XMemoMemoryProvider()
        provider.save_config({"api_key": "secret", "scope": "hermes/test"}, str(tmp_path))

        config_file = tmp_path / "xmemo.json"
        assert config_file.exists()
        data = json.loads(config_file.read_text())
        assert "api_key" not in data
        assert data["scope"] == "hermes/test"


class TestProfileIsolation:
    """Different Hermes profiles should use different XMemo scopes."""

    def test_scope_derived_from_profile(self, monkeypatch, tmp_path):
        monkeypatch.setenv("XMEMO_KEY", "test-key")
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))

        provider = XMemoMemoryProvider()
        provider.initialize("test-session", agent_identity="coder")

        assert provider._config["scope"] == "hermes/coder"
