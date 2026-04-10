"""Tests for the mem9 memory provider plugin."""

import json
import os
import pytest
from unittest.mock import MagicMock, patch

from plugins.memory.mem9 import (
    Mem9MemoryProvider,
    _Mem9Client,
    _load_config,
)


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

class TestLoadConfig:
    def test_defaults(self):
        with patch.dict(os.environ, {}, clear=True):
            cfg = _load_config()
        assert cfg["api_url"] == "https://api.mem9.ai"
        assert cfg["api_key"] == ""
        assert cfg["agent_id"] == "hermes"

    def test_env_vars(self):
        env = {
            "MEM9_API_KEY": "sk-test",
            "MEM9_API_URL": "http://localhost:8080",
            "MEM9_AGENT_ID": "my-agent",
        }
        with patch.dict(os.environ, env, clear=True):
            cfg = _load_config()
        assert cfg["api_key"] == "sk-test"
        assert cfg["api_url"] == "http://localhost:8080"
        assert cfg["agent_id"] == "my-agent"

    def test_json_overrides(self, tmp_path):
        config_file = tmp_path / "mem9.json"
        config_file.write_text(json.dumps({"agent_id": "custom-agent"}))
        with patch.dict(os.environ, {"MEM9_API_KEY": "sk-test"}, clear=True), \
             patch("hermes_constants.get_hermes_home", return_value=tmp_path):
            cfg = _load_config()
        assert cfg["agent_id"] == "custom-agent"
        assert cfg["api_key"] == "sk-test"


# ---------------------------------------------------------------------------
# Provider availability
# ---------------------------------------------------------------------------

class TestProviderAvailability:
    def test_unavailable_without_key(self):
        with patch.dict(os.environ, {}, clear=True):
            p = Mem9MemoryProvider()
            assert not p.is_available()

    def test_available_with_key(self):
        with patch.dict(os.environ, {"MEM9_API_KEY": "sk-test"}, clear=True):
            p = Mem9MemoryProvider()
            assert p.is_available()


# ---------------------------------------------------------------------------
# Provider metadata
# ---------------------------------------------------------------------------

class TestProviderMetadata:
    def test_name(self):
        assert Mem9MemoryProvider().name == "mem9"

    def test_tool_schemas(self):
        p = Mem9MemoryProvider()
        schemas = p.get_tool_schemas()
        names = [s["name"] for s in schemas]
        assert names == [
            "mem9_store", "mem9_search", "mem9_get",
            "mem9_update", "mem9_delete",
        ]

    def test_config_schema(self):
        p = Mem9MemoryProvider()
        keys = [f["key"] for f in p.get_config_schema()]
        assert "api_key" in keys
        assert "api_url" in keys

    def test_system_prompt_empty_without_client(self):
        p = Mem9MemoryProvider()
        assert p.system_prompt_block() == ""


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------

class TestToolDispatch:
    @pytest.fixture
    def provider(self):
        p = Mem9MemoryProvider()
        p._client = MagicMock(spec=_Mem9Client)
        return p

    def test_store(self, provider):
        provider._client.store.return_value = {"id": "mem-123"}
        result = json.loads(provider.handle_tool_call(
            "mem9_store", {"content": "User prefers dark mode"},
        ))
        assert result["stored"] is True
        assert result["id"] == "mem-123"
        provider._client.store.assert_called_once()

    def test_store_missing_content(self, provider):
        result = json.loads(provider.handle_tool_call("mem9_store", {}))
        assert "error" in result

    def test_search(self, provider):
        provider._client.search.return_value = {
            "memories": [
                {"id": "m1", "content": "dark mode", "score": 0.95,
                 "relative_age": "2h ago", "tags": ["pref"]},
            ],
            "total": 1,
        }
        result = json.loads(provider.handle_tool_call(
            "mem9_search", {"query": "theme"},
        ))
        assert result["count"] == 1
        assert result["results"][0]["content"] == "dark mode"
        assert result["results"][0]["age"] == "2h ago"

    def test_search_empty(self, provider):
        provider._client.search.return_value = {"memories": [], "total": 0}
        result = json.loads(provider.handle_tool_call(
            "mem9_search", {"query": "nonexistent"},
        ))
        assert "No relevant memories" in result.get("result", "")

    def test_get(self, provider):
        provider._client.get.return_value = {"id": "m1", "content": "fact"}
        result = json.loads(provider.handle_tool_call(
            "mem9_get", {"id": "m1"},
        ))
        assert result["id"] == "m1"

    def test_get_not_found(self, provider):
        provider._client.get.return_value = None
        result = json.loads(provider.handle_tool_call(
            "mem9_get", {"id": "missing"},
        ))
        assert "not found" in result.get("error", "").lower()

    def test_update(self, provider):
        provider._client.update.return_value = {"id": "m1"}
        result = json.loads(provider.handle_tool_call(
            "mem9_update", {"id": "m1", "content": "updated fact"},
        ))
        assert result["updated"] is True

    def test_delete(self, provider):
        provider._client.delete.return_value = True
        result = json.loads(provider.handle_tool_call(
            "mem9_delete", {"id": "m1"},
        ))
        assert result["deleted"] is True

    def test_delete_not_found(self, provider):
        provider._client.delete.return_value = False
        result = json.loads(provider.handle_tool_call(
            "mem9_delete", {"id": "missing"},
        ))
        assert "not found" in result.get("error", "").lower()

    def test_unknown_tool(self, provider):
        result = json.loads(provider.handle_tool_call("mem9_foo", {}))
        assert "error" in result

    def test_breaker_open_returns_error(self, provider):
        provider._consecutive_failures = 10
        provider._breaker_open_until = float("inf")
        result = json.loads(provider.handle_tool_call(
            "mem9_search", {"query": "test"},
        ))
        assert "unavailable" in result.get("error", "").lower()


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------

class TestCircuitBreaker:
    def test_not_open_initially(self):
        p = Mem9MemoryProvider()
        assert not p._is_breaker_open()

    def test_opens_after_threshold(self):
        p = Mem9MemoryProvider()
        for _ in range(5):
            p._record_failure()
        assert p._is_breaker_open()

    def test_resets_on_success(self):
        p = Mem9MemoryProvider()
        for _ in range(3):
            p._record_failure()
        p._record_success()
        assert p._consecutive_failures == 0


# ---------------------------------------------------------------------------
# Prefetch formatting
# ---------------------------------------------------------------------------

class TestPrefetch:
    def test_prefetch_empty_without_client(self):
        p = Mem9MemoryProvider()
        assert p.prefetch("test query") == ""

    def test_prefetch_returns_formatted_context(self):
        p = Mem9MemoryProvider()
        with p._prefetch_lock:
            p._prefetch_result = "- [2h ago] User likes dark mode"
        result = p.prefetch("theme")
        assert "mem9 Memory" in result
        assert "dark mode" in result

    def test_prefetch_clears_after_read(self):
        p = Mem9MemoryProvider()
        with p._prefetch_lock:
            p._prefetch_result = "- something"
        p.prefetch("q")
        assert p._prefetch_result == ""


# ---------------------------------------------------------------------------
# Autoprovision
# ---------------------------------------------------------------------------

class TestAutoprovision:
    def test_autoprovision_returns_tenant(self):
        import httpx
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "id": "tenant-abc-123",
            "claim_url": "https://app.mem9.ai/claim/tenant-abc-123",
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.post", return_value=mock_resp) as mock_post:
            result = _Mem9Client.autoprovision("https://api.mem9.ai")
        assert result["id"] == "tenant-abc-123"
        assert "claim_url" in result
        mock_post.assert_called_once_with(
            "https://api.mem9.ai/v1alpha1/mem9s",
            timeout=8.0,
        )

    def test_autoprovision_propagates_errors(self):
        import httpx
        with patch("httpx.post", side_effect=httpx.HTTPStatusError(
            "403", request=MagicMock(), response=MagicMock(),
        )):
            with pytest.raises(httpx.HTTPStatusError):
                _Mem9Client.autoprovision()

    def test_post_setup_exists(self):
        p = Mem9MemoryProvider()
        assert hasattr(p, "post_setup")
        assert callable(p.post_setup)


# ---------------------------------------------------------------------------
# User scoping (source isolation)
# ---------------------------------------------------------------------------

class TestUserScoping:
    def test_initialize_uses_gateway_user_id(self):
        with patch.dict(os.environ, {"MEM9_API_KEY": "sk-test"}, clear=True):
            p = Mem9MemoryProvider()
            p.initialize("sess-1", user_id="gw-user-42")
        assert p._user_id == "gw-user-42"

    def test_initialize_falls_back_to_agent_identity(self):
        with patch.dict(os.environ, {"MEM9_API_KEY": "sk-test"}, clear=True):
            p = Mem9MemoryProvider()
            p.initialize("sess-1", agent_identity="my-profile")
        assert p._user_id == "my-profile"

    def test_initialize_falls_back_to_agent_id(self):
        with patch.dict(os.environ, {
            "MEM9_API_KEY": "sk-test", "MEM9_AGENT_ID": "custom-agent",
        }, clear=True):
            p = Mem9MemoryProvider()
            p.initialize("sess-1")
        assert p._user_id == "custom-agent"

    def test_user_id_priority_order(self):
        """user_id > agent_identity > agent_id."""
        with patch.dict(os.environ, {"MEM9_API_KEY": "sk-test"}, clear=True):
            p = Mem9MemoryProvider()
            p.initialize("s", user_id="u", agent_identity="ai")
        assert p._user_id == "u"

    def test_store_passes_source(self):
        p = Mem9MemoryProvider()
        p._client = MagicMock(spec=_Mem9Client)
        p._client.store.return_value = {"id": "m1"}
        p._user_id = "user-99"
        p._session_id = "sess"
        p.handle_tool_call("mem9_store", {"content": "hello"})
        _, kwargs = p._client.store.call_args
        assert kwargs["source"] == "user-99"

    def test_search_passes_source(self):
        p = Mem9MemoryProvider()
        p._client = MagicMock(spec=_Mem9Client)
        p._client.search.return_value = {"memories": [], "total": 0}
        p._user_id = "user-99"
        p.handle_tool_call("mem9_search", {"query": "test"})
        _, kwargs = p._client.search.call_args
        assert kwargs["source"] == "user-99"


# ---------------------------------------------------------------------------
# Safe JSON parsing (202/204 handling)
# ---------------------------------------------------------------------------

class TestSafeJson:
    def test_202_empty_body(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 202
        mock_resp.content = b""
        assert _Mem9Client._safe_json(mock_resp) == {}

    def test_204_empty_body(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_resp.content = b""
        assert _Mem9Client._safe_json(mock_resp) == {}

    def test_200_with_json(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b'{"id": "m1"}'
        mock_resp.json.return_value = {"id": "m1"}
        assert _Mem9Client._safe_json(mock_resp) == {"id": "m1"}

    def test_202_with_json_body(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 202
        mock_resp.content = b'{"id": "m1"}'
        mock_resp.json.return_value = {"id": "m1"}
        assert _Mem9Client._safe_json(mock_resp) == {"id": "m1"}

    def test_malformed_json_returns_empty(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"not json"
        mock_resp.json.side_effect = ValueError("bad json")
        assert _Mem9Client._safe_json(mock_resp) == {}
