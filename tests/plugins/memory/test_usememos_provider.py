"""Tests for the usememos memory provider plugin."""

import json
import os
import stat
from unittest.mock import patch, MagicMock

import pytest

from plugins.memory.usememos import MemosMemoryProvider, _load_config, _api_request


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_MEMOS = [
    {
        "name": "memos/1",
        "uid": "memo-1",
        "content": "User prefers dark mode",
        "createTime": "2026-06-09T00:00:00Z",
        "visibility": "PRIVATE",
    },
    {
        "name": "memos/2",
        "uid": "memo-2",
        "content": "Project uses pytest with xdist",
        "createTime": "2026-06-08T00:00:00Z",
        "visibility": "PRIVATE",
    },
    {
        "name": "memos/3",
        "uid": "memo-3",
        "content": "Meeting notes from standup",
        "createTime": "2026-06-07T00:00:00Z",
        "visibility": "PROTECTED",
    },
]


def _make_provider(monkeypatch, tmp_path, api_url="https://memos.example.com", token="test-token"):
    """Create an initialized provider with mocked env."""
    monkeypatch.setenv("MEMOS_API_URL", api_url)
    monkeypatch.setenv("MEMOS_ACCESS_TOKEN", token)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    provider = MemosMemoryProvider()
    provider.initialize("test-session")
    return provider


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


class TestMemosConfig:
    """Config loading from env vars and JSON file."""

    def test_config_from_env(self, monkeypatch, tmp_path):
        monkeypatch.setenv("MEMOS_API_URL", "https://my-memos.com")
        monkeypatch.setenv("MEMOS_ACCESS_TOKEN", "tok123")
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))

        cfg = _load_config()
        assert cfg["api_url"] == "https://my-memos.com"
        assert cfg["access_token"] == "tok123"
        assert cfg["default_visibility"] == "PRIVATE"

    def test_config_file_overrides_env(self, monkeypatch, tmp_path):
        monkeypatch.setenv("MEMOS_API_URL", "https://env-url.com")
        monkeypatch.setenv("MEMOS_ACCESS_TOKEN", "env-token")
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))

        config_file = tmp_path / "usememos.json"
        config_file.write_text(json.dumps({
            "api_url": "https://file-url.com",
            "default_visibility": "PUBLIC",
        }))

        cfg = _load_config()
        assert cfg["api_url"] == "https://file-url.com"  # file overrides env
        assert cfg["access_token"] == "env-token"  # env still used for missing keys
        assert cfg["default_visibility"] == "PUBLIC"

    def test_is_available_with_config(self, monkeypatch, tmp_path):
        provider = _make_provider(monkeypatch, tmp_path)
        assert provider.is_available() is True

    def test_is_available_without_token(self, monkeypatch, tmp_path):
        monkeypatch.setenv("MEMOS_API_URL", "https://memos.example.com")
        monkeypatch.delenv("MEMOS_ACCESS_TOKEN", raising=False)
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        provider = MemosMemoryProvider()
        assert provider.is_available() is False

    def test_is_available_without_url(self, monkeypatch, tmp_path):
        monkeypatch.delenv("MEMOS_API_URL", raising=False)
        monkeypatch.setenv("MEMOS_ACCESS_TOKEN", "tok")
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        provider = MemosMemoryProvider()
        assert provider.is_available() is False


# ---------------------------------------------------------------------------
# Provider basics
# ---------------------------------------------------------------------------


class TestMemosProviderBasics:
    """Basic provider properties and initialization."""

    def test_name(self):
        provider = MemosMemoryProvider()
        assert provider.name == "usememos"

    def test_tool_schemas(self):
        provider = MemosMemoryProvider()
        schemas = provider.get_tool_schemas()
        names = {s["name"] for s in schemas}
        assert names == {"memos_list", "memos_search", "memos_add"}

    def test_system_prompt_block(self, monkeypatch, tmp_path):
        provider = _make_provider(monkeypatch, tmp_path)
        block = provider.system_prompt_block()
        assert "Memos" in block
        assert "memos_list" in block
        assert "memos_search" in block
        assert "memos_add" in block

    def test_initialize_sets_config(self, monkeypatch, tmp_path):
        provider = _make_provider(monkeypatch, tmp_path, api_url="https://test.com", token="abc")
        assert provider._api_url == "https://test.com"
        assert provider._access_token == "abc"
        assert provider._default_visibility == "PRIVATE"


# ---------------------------------------------------------------------------
# Tool calls: memos_list
# ---------------------------------------------------------------------------


class TestMemosList:
    """memos_list tool call."""

    def test_list_returns_memos(self, monkeypatch, tmp_path):
        provider = _make_provider(monkeypatch, tmp_path)

        with patch("plugins.memory.usememos._api_request", return_value={"memos": SAMPLE_MEMOS}):
            result = json.loads(provider.handle_tool_call("memos_list", {"limit": 20}))

        assert result["count"] == 3
        assert result["results"][0]["content"] == "User prefers dark mode"
        assert result["results"][0]["visibility"] == "PRIVATE"

    def test_list_empty(self, monkeypatch, tmp_path):
        provider = _make_provider(monkeypatch, tmp_path)

        with patch("plugins.memory.usememos._api_request", return_value={"memos": []}):
            result = json.loads(provider.handle_tool_call("memos_list", {}))

        assert "No memos" in result["result"]

    def test_list_limit_clamped(self, monkeypatch, tmp_path):
        provider = _make_provider(monkeypatch, tmp_path)

        with patch("plugins.memory.usememos._api_request", return_value={"memos": []}) as mock_req:
            provider.handle_tool_call("memos_list", {"limit": 100})

        # limit should be clamped to 50
        call_params = mock_req.call_args
        assert call_params[1]["params"]["pageSize"] == "50"

    def test_list_api_error(self, monkeypatch, tmp_path):
        provider = _make_provider(monkeypatch, tmp_path)

        with patch("plugins.memory.usememos._api_request", side_effect=RuntimeError("HTTP 500")):
            result = json.loads(provider.handle_tool_call("memos_list", {}))

        assert "error" in result


# ---------------------------------------------------------------------------
# Tool calls: memos_search
# ---------------------------------------------------------------------------


class TestMemosSearch:
    """memos_search tool call."""

    def test_search_finds_match(self, monkeypatch, tmp_path):
        provider = _make_provider(monkeypatch, tmp_path)

        with patch("plugins.memory.usememos._api_request", return_value={"memos": SAMPLE_MEMOS}):
            result = json.loads(provider.handle_tool_call("memos_search", {"query": "dark mode"}))

        assert result["count"] == 1
        assert "dark mode" in result["results"][0]["content"]

    def test_search_case_insensitive(self, monkeypatch, tmp_path):
        provider = _make_provider(monkeypatch, tmp_path)

        with patch("plugins.memory.usememos._api_request", return_value={"memos": SAMPLE_MEMOS}):
            result = json.loads(provider.handle_tool_call("memos_search", {"query": "PYTEST"}))

        assert result["count"] == 1
        assert "pytest" in result["results"][0]["content"].lower()

    def test_search_no_match(self, monkeypatch, tmp_path):
        provider = _make_provider(monkeypatch, tmp_path)

        with patch("plugins.memory.usememos._api_request", return_value={"memos": SAMPLE_MEMOS}):
            result = json.loads(provider.handle_tool_call("memos_search", {"query": "nonexistent"}))

        assert "No matching" in result["result"]

    def test_search_missing_query(self, monkeypatch, tmp_path):
        provider = _make_provider(monkeypatch, tmp_path)
        result = json.loads(provider.handle_tool_call("memos_search", {}))
        assert "error" in result


# ---------------------------------------------------------------------------
# Tool calls: memos_add
# ---------------------------------------------------------------------------


class TestMemosAdd:
    """memos_add tool call."""

    def test_add_creates_memo(self, monkeypatch, tmp_path):
        provider = _make_provider(monkeypatch, tmp_path)

        mock_response = {"name": "memos/99", "content": "new fact", "visibility": "PRIVATE"}
        with patch("plugins.memory.usememos._api_request", return_value=mock_response) as mock_req:
            result = json.loads(provider.handle_tool_call("memos_add", {"content": "new fact"}))

        assert result["result"] == "Memo stored."
        assert result["id"] == "memos/99"

        # Verify API call
        call_args = mock_req.call_args
        assert call_args[0] == ("https://memos.example.com", "test-token", "POST", "/memos")
        assert call_args[1]["body"]["content"] == "new fact"
        assert call_args[1]["body"]["visibility"] == "PRIVATE"

    def test_add_custom_visibility(self, monkeypatch, tmp_path):
        provider = _make_provider(monkeypatch, tmp_path)

        with patch("plugins.memory.usememos._api_request", return_value={"name": "memos/1"}) as mock_req:
            provider.handle_tool_call("memos_add", {"content": "public note", "visibility": "PUBLIC"})

        assert mock_req.call_args[1]["body"]["visibility"] == "PUBLIC"

    def test_add_missing_content(self, monkeypatch, tmp_path):
        provider = _make_provider(monkeypatch, tmp_path)
        result = json.loads(provider.handle_tool_call("memos_add", {}))
        assert "error" in result

    def test_add_api_error(self, monkeypatch, tmp_path):
        provider = _make_provider(monkeypatch, tmp_path)

        with patch("plugins.memory.usememos._api_request", side_effect=RuntimeError("HTTP 401")):
            result = json.loads(provider.handle_tool_call("memos_add", {"content": "test"}))

        assert "error" in result


# ---------------------------------------------------------------------------
# Unknown tool
# ---------------------------------------------------------------------------


def test_unknown_tool(monkeypatch, tmp_path):
    provider = _make_provider(monkeypatch, tmp_path)
    result = json.loads(provider.handle_tool_call("memos_unknown", {}))
    assert "error" in result


# ---------------------------------------------------------------------------
# Prefetch
# ---------------------------------------------------------------------------


class TestMemosPrefetch:
    """Prefetch behavior."""

    def test_prefetch_returns_recent_memos(self, monkeypatch, tmp_path):
        provider = _make_provider(monkeypatch, tmp_path)

        with patch("plugins.memory.usememos._api_request", return_value={"memos": SAMPLE_MEMOS[:2]}):
            provider.queue_prefetch("test query")
            provider._prefetch_thread.join(timeout=2)

        result = provider.prefetch("test query")
        assert "dark mode" in result
        assert "pytest" in result

    def test_prefetch_empty(self, monkeypatch, tmp_path):
        provider = _make_provider(monkeypatch, tmp_path)

        with patch("plugins.memory.usememos._api_request", return_value={"memos": []}):
            provider.queue_prefetch("test")
            provider._prefetch_thread.join(timeout=2)

        result = provider.prefetch("test")
        assert result == ""

    def test_prefetch_failure_graceful(self, monkeypatch, tmp_path):
        provider = _make_provider(monkeypatch, tmp_path)

        with patch("plugins.memory.usememos._api_request", side_effect=RuntimeError("down")):
            provider.queue_prefetch("test")
            provider._prefetch_thread.join(timeout=2)

        result = provider.prefetch("test")
        assert result == ""


# ---------------------------------------------------------------------------
# Shutdown
# ---------------------------------------------------------------------------


def test_shutdown_joins_thread(monkeypatch, tmp_path):
    provider = _make_provider(monkeypatch, tmp_path)

    with patch("plugins.memory.usememos._api_request", return_value={"memos": []}):
        provider.queue_prefetch("test")

    provider.shutdown()  # should not hang or raise


# ---------------------------------------------------------------------------
# Config file permissions
# ---------------------------------------------------------------------------


@pytest.mark.skipif(os.name == "nt", reason="POSIX mode bits not enforced on Windows")
def test_save_config_sets_owner_only_permissions(tmp_path):
    """usememos.json must be written with 0o600 so access token is not world-readable."""
    provider = MemosMemoryProvider()
    provider.save_config({"access_token": "secret"}, str(tmp_path))
    config_file = tmp_path / "usememos.json"
    assert config_file.exists()
    mode = stat.S_IMODE(config_file.stat().st_mode)
    assert mode == 0o600, f"Expected 0o600 (owner-only), got {oct(mode)}"


# ---------------------------------------------------------------------------
# Default visibility
# ---------------------------------------------------------------------------


class TestMemosDefaults:
    """Default config values."""

    def test_default_visibility_private(self, monkeypatch, tmp_path):
        monkeypatch.setenv("MEMOS_API_URL", "https://memos.example.com")
        monkeypatch.setenv("MEMOS_ACCESS_TOKEN", "tok")
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        provider = MemosMemoryProvider()
        provider.initialize("test")
        assert provider._default_visibility == "PRIVATE"

    def test_custom_default_visibility(self, monkeypatch, tmp_path):
        monkeypatch.setenv("MEMOS_API_URL", "https://memos.example.com")
        monkeypatch.setenv("MEMOS_ACCESS_TOKEN", "tok")
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        config_file = tmp_path / "usememos.json"
        config_file.write_text(json.dumps({"default_visibility": "PUBLIC"}))
        provider = MemosMemoryProvider()
        provider.initialize("test")
        assert provider._default_visibility == "PUBLIC"
