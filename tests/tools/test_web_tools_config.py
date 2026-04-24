"""Tests for web backend client configuration and singleton behavior.

Coverage:
  _get_firecrawl_client() — configuration matrix, singleton caching,
  constructor failure recovery, return value verification, edge cases.
  _get_backend() — backend selection logic with env var combinations.
  _get_parallel_client() — Parallel client configuration, singleton caching.
  check_web_api_key() — unified availability check across all web backends.
"""

import importlib
import json
import os
import sys
import types
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


class TestFirecrawlClientConfig:
    """Test suite for Firecrawl client initialization."""

    def setup_method(self):
        """Reset client and env vars before each test."""
        import tools.web_tools
        tools.web_tools._firecrawl_client = None
        tools.web_tools._firecrawl_client_config = None
        for key in (
            "FIRECRAWL_API_KEY",
            "FIRECRAWL_API_URL",
            "FIRECRAWL_GATEWAY_URL",
            "TOOL_GATEWAY_DOMAIN",
            "TOOL_GATEWAY_SCHEME",
            "TOOL_GATEWAY_USER_TOKEN",
        ):
            os.environ.pop(key, None)
        # Enable managed tools by default for these tests — patch both the
        # local web_tools import and the managed_tool_gateway import so the
        # full firecrawl client init path sees True.
        self._managed_patchers = [
            patch("tools.web_tools.managed_nous_tools_enabled", return_value=True),
            patch("tools.managed_tool_gateway.managed_nous_tools_enabled", return_value=True),
        ]
        for p in self._managed_patchers:
            p.start()

    def teardown_method(self):
        """Reset client after each test."""
        import tools.web_tools
        tools.web_tools._firecrawl_client = None
        tools.web_tools._firecrawl_client_config = None
        for key in (
            "FIRECRAWL_API_KEY",
            "FIRECRAWL_API_URL",
            "FIRECRAWL_GATEWAY_URL",
            "TOOL_GATEWAY_DOMAIN",
            "TOOL_GATEWAY_SCHEME",
            "TOOL_GATEWAY_USER_TOKEN",
        ):
            os.environ.pop(key, None)
        for p in self._managed_patchers:
            p.stop()

    # ── Configuration matrix ─────────────────────────────────────────

    def test_no_config_raises_with_helpful_message(self):
        """Neither key nor URL → ValueError with guidance."""
        with patch("tools.web_tools.Firecrawl"):
            with patch("tools.web_tools._read_nous_access_token", return_value=None):
                from tools.web_tools import _get_firecrawl_client
                with pytest.raises(ValueError, match="FIRECRAWL_API_KEY"):
                    _get_firecrawl_client()

    def test_tool_gateway_domain_builds_firecrawl_gateway_origin(self):
        """Shared gateway domain should derive the Firecrawl vendor hostname."""
        with patch.dict(os.environ, {"TOOL_GATEWAY_DOMAIN": "nousresearch.com"}):
            with patch("tools.web_tools._read_nous_access_token", return_value="nous-token"):
                with patch("tools.web_tools.Firecrawl") as mock_fc:
                    from tools.web_tools import _get_firecrawl_client
                    result = _get_firecrawl_client()
                    mock_fc.assert_called_once_with(
                        api_key="nous-token",
                        api_url="https://firecrawl-gateway.nousresearch.com",
                    )
                    assert result is mock_fc.return_value

    def test_tool_gateway_scheme_can_switch_derived_gateway_origin_to_http(self):
        """Shared gateway scheme should allow local plain-http vendor hosts."""
        with patch.dict(os.environ, {
            "TOOL_GATEWAY_DOMAIN": "nousresearch.com",
            "TOOL_GATEWAY_SCHEME": "http",
        }):
            with patch("tools.web_tools._read_nous_access_token", return_value="nous-token"):
                with patch("tools.web_tools.Firecrawl") as mock_fc:
                    from tools.web_tools import _get_firecrawl_client
                    result = _get_firecrawl_client()
                    mock_fc.assert_called_once_with(
                        api_key="nous-token",
                        api_url="http://firecrawl-gateway.nousresearch.com",
                    )
                    assert result is mock_fc.return_value

    def test_invalid_tool_gateway_scheme_raises(self):
        """Unexpected shared gateway schemes should fail fast."""
        with patch.dict(os.environ, {
            "TOOL_GATEWAY_DOMAIN": "nousresearch.com",
            "TOOL_GATEWAY_SCHEME": "ftp",
        }):
            with patch("tools.web_tools._read_nous_access_token", return_value="nous-token"):
                from tools.web_tools import _get_firecrawl_client
                with pytest.raises(ValueError, match="TOOL_GATEWAY_SCHEME"):
                    _get_firecrawl_client()

    def test_explicit_firecrawl_gateway_url_takes_precedence(self):
        """An explicit Firecrawl gateway origin should override the shared domain."""
        with patch.dict(os.environ, {
            "FIRECRAWL_GATEWAY_URL": "https://firecrawl-gateway.localhost:3009/",
            "TOOL_GATEWAY_DOMAIN": "nousresearch.com",
        }):
            with patch("tools.web_tools._read_nous_access_token", return_value="nous-token"):
                with patch("tools.web_tools.Firecrawl") as mock_fc:
                    from tools.web_tools import _get_firecrawl_client
                    _get_firecrawl_client()
                    mock_fc.assert_called_once_with(
                        api_key="nous-token",
                        api_url="https://firecrawl-gateway.localhost:3009",
                    )

    def test_default_gateway_domain_targets_nous_production_origin(self):
        """Default gateway origin should point at the Firecrawl vendor hostname."""
        with patch("tools.web_tools._read_nous_access_token", return_value="nous-token"):
            with patch("tools.web_tools.Firecrawl") as mock_fc:
                from tools.web_tools import _get_firecrawl_client
                _get_firecrawl_client()
                mock_fc.assert_called_once_with(
                    api_key="nous-token",
                    api_url="https://firecrawl-gateway.nousresearch.com",
                )

    def test_nous_auth_token_respects_hermes_home_override(self, tmp_path):
        """Auth lookup should read from HERMES_HOME/auth.json, not ~/.hermes/auth.json."""
        real_home = tmp_path / "real-home"
        (real_home / ".hermes").mkdir(parents=True)

        hermes_home = tmp_path / "hermes-home"
        hermes_home.mkdir()
        (hermes_home / "auth.json").write_text(json.dumps({
            "providers": {
                "nous": {
                    "access_token": "nous-token",
                }
            }
        }))

        with patch.dict(os.environ, {
            "HOME": str(real_home),
            "HERMES_HOME": str(hermes_home),
        }, clear=False):
            import tools.web_tools
            importlib.reload(tools.web_tools)
            assert tools.web_tools._read_nous_access_token() == "nous-token"

    def test_check_auxiliary_model_re_resolves_backend_each_call(self):
        """Availability checks should not be pinned to module import state."""
        import tools.web_tools

        # Simulate the pre-fix import-time cache slot for regression coverage.
        tools.web_tools.__dict__["_aux_async_client"] = None

        with patch(
            "tools.web_tools.get_async_text_auxiliary_client",
            side_effect=[(None, None), (MagicMock(base_url="https://api.openrouter.ai/v1"), "test-model")],
        ):
            assert tools.web_tools.check_auxiliary_model() is False
            assert tools.web_tools.check_auxiliary_model() is True

    @pytest.mark.asyncio
    async def test_summarizer_re_resolves_backend_after_initial_unavailable_state(self):
        """Summarization should pick up a backend that becomes available later in-process."""
        import tools.web_tools

        tools.web_tools.__dict__["_aux_async_client"] = None

        response = MagicMock()
        response.choices = [MagicMock(message=MagicMock(content="summary text"))]

        with patch(
            "tools.web_tools._resolve_web_extract_auxiliary",
            side_effect=[(None, None, {}), (MagicMock(base_url="https://api.openrouter.ai/v1"), "test-model", {})],
        ), patch(
            "tools.web_tools.async_call_llm",
            new=AsyncMock(return_value=response),
        ) as mock_async_call:
            assert tools.web_tools.check_auxiliary_model() is False
            result = await tools.web_tools._call_summarizer_llm(
                "Some content worth summarizing",
                "Source: https://example.com\n\n",
                None,
            )

        assert result == "summary text"
        mock_async_call.assert_awaited_once()

    # ── Singleton caching ────────────────────────────────────────────

    def test_singleton_returns_same_instance(self):
        """Second call returns cached client without re-constructing."""
        with patch.dict(os.environ, {"FIRECRAWL_API_KEY": "fc-test"}):
            with patch("tools.web_tools.Firecrawl") as mock_fc:
                from tools.web_tools import _get_firecrawl_client
                client1 = _get_firecrawl_client()
                client2 = _get_firecrawl_client()
                assert client1 is client2
                mock_fc.assert_called_once()  # constructed only once

    def test_constructor_failure_allows_retry(self):
        """If Firecrawl() raises, next call should retry (not return None)."""
        import tools.web_tools
        with patch.dict(os.environ, {"FIRECRAWL_API_KEY": "fc-test"}):
            with patch("tools.web_tools.Firecrawl") as mock_fc:
                mock_fc.side_effect = [RuntimeError("init failed"), MagicMock()]
                from tools.web_tools import _get_firecrawl_client

                with pytest.raises(RuntimeError):
                    _get_firecrawl_client()

                # Client stayed None, so retry should work
                assert tools.web_tools._firecrawl_client is None
                result = _get_firecrawl_client()
                assert result is not None

    # ── Edge cases ───────────────────────────────────────────────────

    def test_empty_string_key_no_url_raises(self):
        """FIRECRAWL_API_KEY='' with no URL → should raise."""
        with patch.dict(os.environ, {"FIRECRAWL_API_KEY": ""}):
            with patch("tools.web_tools.Firecrawl"):
                with patch("tools.web_tools._read_nous_access_token", return_value=None):
                    from tools.web_tools import _get_firecrawl_client
                    with pytest.raises(ValueError):
                        _get_firecrawl_client()


class TestBackendSelection:
    """Test suite for _get_backend() backend selection logic.

    The backend is configured via config.yaml (web.backend), set by
    ``hermes tools``.  Falls back to key-based detection for legacy/manual
    setups.
    """

    _ENV_KEYS = (
        "EXA_API_KEY",
        "PARALLEL_API_KEY",
        "FIRECRAWL_API_KEY",
        "FIRECRAWL_API_URL",
        "FIRECRAWL_GATEWAY_URL",
        "TOOL_GATEWAY_DOMAIN",
        "TOOL_GATEWAY_SCHEME",
        "TOOL_GATEWAY_USER_TOKEN",
        "TAVILY_API_KEY",
    )

    def setup_method(self):
        for key in self._ENV_KEYS:
            os.environ.pop(key, None)
        self._managed_patchers = [
            patch("tools.web_tools.managed_nous_tools_enabled", return_value=True),
            patch("tools.managed_tool_gateway.managed_nous_tools_enabled", return_value=True),
        ]
        for p in self._managed_patchers:
            p.start()

    def teardown_method(self):
        for key in self._ENV_KEYS:
            os.environ.pop(key, None)
        for p in self._managed_patchers:
            p.stop()

    # ── Config-based selection (web.backend in config.yaml) ───────────

    def test_config_parallel(self):
        """web.backend=parallel in config → 'parallel' regardless of keys."""
        from tools.web_tools import _get_backend
        with patch("tools.web_tools._load_web_config", return_value={"backend": "parallel"}):
            assert _get_backend() == "parallel"

    def test_config_exa(self):
        """web.backend=exa in config → 'exa' regardless of other keys."""
        from tools.web_tools import _get_backend
        with patch("tools.web_tools._load_web_config", return_value={"backend": "exa"}), \
             patch.dict(os.environ, {"PARALLEL_API_KEY": "test-key"}):
            assert _get_backend() == "exa"

    def test_config_firecrawl(self):
        """web.backend=firecrawl in config → 'firecrawl' even if Parallel key set."""
        from tools.web_tools import _get_backend
        with patch("tools.web_tools._load_web_config", return_value={"backend": "firecrawl"}), \
             patch.dict(os.environ, {"PARALLEL_API_KEY": "test-key"}):
            assert _get_backend() == "firecrawl"

    def test_config_tavily(self):
        """web.backend=tavily in config → 'tavily' regardless of other keys."""
        from tools.web_tools import _get_backend
        with patch("tools.web_tools._load_web_config", return_value={"backend": "tavily"}):
            assert _get_backend() == "tavily"

    def test_config_tavily_overrides_env_keys(self):
        """web.backend=tavily in config → 'tavily' even if Firecrawl key set."""
        from tools.web_tools import _get_backend
        with patch("tools.web_tools._load_web_config", return_value={"backend": "tavily"}), \
             patch.dict(os.environ, {"FIRECRAWL_API_KEY": "fc-test"}):
            assert _get_backend() == "tavily"

    def test_config_case_insensitive(self):
        """web.backend=Parallel (mixed case) → 'parallel'."""
        from tools.web_tools import _get_backend
        with patch("tools.web_tools._load_web_config", return_value={"backend": "Parallel"}):
            assert _get_backend() == "parallel"

    def test_config_tavily_case_insensitive(self):
        """web.backend=Tavily (mixed case) → 'tavily'."""
        from tools.web_tools import _get_backend
        with patch("tools.web_tools._load_web_config", return_value={"backend": "Tavily"}):
            assert _get_backend() == "tavily"

    # ── Fallback (no web.backend in config) ───────────────────────────

    def test_fallback_parallel_only_key(self):
        """Only PARALLEL_API_KEY set → 'parallel'."""
        from tools.web_tools import _get_backend
        with patch("tools.web_tools._load_web_config", return_value={}), \
             patch.dict(os.environ, {"PARALLEL_API_KEY": "test-key"}):
            assert _get_backend() == "parallel"

    def test_fallback_exa_only_key(self):
        """Only EXA_API_KEY set → 'exa'."""
        from tools.web_tools import _get_backend
        with patch("tools.web_tools._load_web_config", return_value={}), \
             patch.dict(os.environ, {"EXA_API_KEY": "exa-test"}):
            assert _get_backend() == "exa"

    def test_fallback_parallel_takes_priority_over_exa(self):
        """Exa should only win the fallback path when it is the only configured backend."""
        from tools.web_tools import _get_backend
        with patch("tools.web_tools._load_web_config", return_value={}), \
             patch.dict(os.environ, {"EXA_API_KEY": "exa-test", "PARALLEL_API_KEY": "par-test"}):
            assert _get_backend() == "parallel"

    def test_fallback_tavily_only_key(self):
        """Only TAVILY_API_KEY set → 'tavily'."""
        from tools.web_tools import _get_backend
        with patch("tools.web_tools._load_web_config", return_value={}), \
             patch.dict(os.environ, {"TAVILY_API_KEY": "tvly-test"}):
            assert _get_backend() == "tavily"

    def test_fallback_tavily_with_firecrawl_prefers_firecrawl(self):
        """Tavily + Firecrawl keys, no config → 'firecrawl' (backward compat)."""
        from tools.web_tools import _get_backend
        with patch("tools.web_tools._load_web_config", return_value={}), \
             patch.dict(os.environ, {"TAVILY_API_KEY": "tvly-test", "FIRECRAWL_API_KEY": "fc-test"}):
            assert _get_backend() == "firecrawl"

    def test_fallback_tavily_with_parallel_prefers_parallel(self):
        """Tavily + Parallel keys, no config → 'parallel' (Parallel takes priority over Tavily)."""
        from tools.web_tools import _get_backend
        with patch("tools.web_tools._load_web_config", return_value={}), \
             patch.dict(os.environ, {"TAVILY_API_KEY": "tvly-test", "PARALLEL_API_KEY": "par-test"}):
            # Parallel + no Firecrawl → parallel
            assert _get_backend() == "parallel"

    def test_fallback_both_keys_defaults_to_firecrawl(self):
        """Both keys set, no config → 'firecrawl' (backward compat)."""
        from tools.web_tools import _get_backend
        with patch("tools.web_tools._load_web_config", return_value={}), \
             patch.dict(os.environ, {"PARALLEL_API_KEY": "test-key", "FIRECRAWL_API_KEY": "fc-test"}):
            assert _get_backend() == "firecrawl"

    def test_fallback_firecrawl_only_key(self):
        """Only FIRECRAWL_API_KEY set → 'firecrawl'."""
        from tools.web_tools import _get_backend
        with patch("tools.web_tools._load_web_config", return_value={}), \
             patch.dict(os.environ, {"FIRECRAWL_API_KEY": "fc-test"}):
            assert _get_backend() == "firecrawl"

    def test_fallback_no_keys_defaults_to_firecrawl(self):
        """No keys, no config → 'firecrawl' (will fail at client init)."""
        from tools.web_tools import _get_backend
        with patch("tools.web_tools._load_web_config", return_value={}):
            assert _get_backend() == "firecrawl"

    def test_invalid_config_falls_through_to_fallback(self):
        """web.backend=invalid → ignored, uses key-based fallback."""
        from tools.web_tools import _get_backend
        with patch("tools.web_tools._load_web_config", return_value={"backend": "nonexistent"}), \
             patch.dict(os.environ, {"PARALLEL_API_KEY": "test-key"}):
            assert _get_backend() == "parallel"


class TestParallelClientConfig:
    """Test suite for Parallel client initialization."""

    def setup_method(self):
        import tools.web_tools
        tools.web_tools._parallel_client = None
        os.environ.pop("PARALLEL_API_KEY", None)
        fake_parallel = types.ModuleType("parallel")

        class Parallel:
            def __init__(self, api_key):
                self.api_key = api_key

        class AsyncParallel:
            def __init__(self, api_key):
                self.api_key = api_key

        fake_parallel.Parallel = Parallel
        fake_parallel.AsyncParallel = AsyncParallel
        sys.modules["parallel"] = fake_parallel

    def teardown_method(self):
        import tools.web_tools
        tools.web_tools._parallel_client = None
        os.environ.pop("PARALLEL_API_KEY", None)
        sys.modules.pop("parallel", None)

    def test_creates_client_with_key(self):
        """PARALLEL_API_KEY set → creates Parallel client."""
        with patch.dict(os.environ, {"PARALLEL_API_KEY": "test-key"}):
            from tools.web_tools import _get_parallel_client
            from parallel import Parallel
            client = _get_parallel_client()
            assert client is not None
            assert isinstance(client, Parallel)

    def test_no_key_raises_with_helpful_message(self):
        """No PARALLEL_API_KEY → ValueError with guidance."""
        from tools.web_tools import _get_parallel_client
        with pytest.raises(ValueError, match="PARALLEL_API_KEY"):
            _get_parallel_client()

    def test_singleton_returns_same_instance(self):
        """Second call returns cached client."""
        with patch.dict(os.environ, {"PARALLEL_API_KEY": "test-key"}):
            from tools.web_tools import _get_parallel_client
            client1 = _get_parallel_client()
            client2 = _get_parallel_client()
            assert client1 is client2


class TestWebSearchErrorHandling:
    """Test suite for web_search_tool() error responses."""

    def test_search_error_response_does_not_expose_diagnostics(self):
        import tools.web_tools

        firecrawl_client = MagicMock()
        firecrawl_client.search.side_effect = RuntimeError("boom")

        with patch("tools.web_tools._get_backend", return_value="firecrawl"), \
             patch("tools.web_tools._get_firecrawl_client", return_value=firecrawl_client), \
             patch("tools.interrupt.is_interrupted", return_value=False), \
             patch.object(tools.web_tools._debug, "log_call") as mock_log_call, \
             patch.object(tools.web_tools._debug, "save"):
            result = json.loads(tools.web_tools.web_search_tool("test query", limit=3))

        assert result == {"error": "Error searching web: boom"}

        debug_payload = mock_log_call.call_args.args[1]
        assert debug_payload["error"] == "Error searching web: boom"
        assert "traceback" not in debug_payload["error"]
        assert "exception_type" not in debug_payload["error"]
        assert "config" not in result
        assert "exception_type" not in result
        assert "exception_chain" not in result
        assert "traceback" not in result


class TestExaConfig:
    """Test suite for Exa client configuration and highlights."""

    _ENV_KEYS = (
        "EXA_API_KEY",
    )

    def setup_method(self):
        """Reset client and env vars before each test."""
        import tools.web_tools
        tools.web_tools._exa_client = None
        for key in self._ENV_KEYS:
            os.environ.pop(key, None)

    def teardown_method(self):
        """Reset client after each test."""
        import tools.web_tools
        tools.web_tools._exa_client = None
        for key in self._ENV_KEYS:
            os.environ.pop(key, None)

    def test_get_exa_config_defaults(self):
        """_get_exa_config() returns correct default values."""
        from tools.web_tools import _get_exa_config

        config = _get_exa_config()

        assert isinstance(config["highlights_max_characters"], int)
        assert config["highlights_max_characters"] == 2000  # Default per PRD
        assert isinstance(config["highlights_enabled"], bool)
        assert config["highlights_enabled"] is True
        assert isinstance(config["full_text_fallback"], bool)
        assert config["full_text_fallback"] is True

    def test_get_exa_config_from_config_yaml(self):
        """_get_exa_config() reads from web.exa in config.yaml."""
        from tools.web_tools import _get_exa_config

        with patch("tools.web_tools._load_web_config", return_value={
            "exa": {
                "highlights_max_characters": 1500,
                "highlights_enabled": False,
                "full_text_fallback": False,
            }
        }):
            config = _get_exa_config()
            assert config["highlights_max_characters"] == 1500
            assert config["highlights_enabled"] is False
            assert config["full_text_fallback"] is False

    def test_exa_client_no_key_raises(self):
        """No EXA_API_KEY → ValueError with guidance."""
        from tools.web_tools import _get_exa_client

        with pytest.raises(ValueError, match="EXA_API_KEY"):
            _get_exa_client()

    def test_exa_client_creates_with_key(self):
        """EXA_API_KEY set → creates Exa client."""
        with patch.dict(os.environ, {"EXA_API_KEY": "exa-test-key"}):
            with patch("exa_py.Exa") as mock_exa:
                from tools.web_tools import _get_exa_client

                client = _get_exa_client()

                mock_exa.assert_called_once_with(api_key="exa-test-key")
                assert client is mock_exa.return_value

    def test_exa_search_result_structure(self):
        """_exa_search returns proper result structure with highlights."""
        from tools.web_tools import _exa_search

        # Mock Exa client and response
        mock_response = MagicMock()
        mock_result = MagicMock()
        mock_result.url = "https://example.com/article"
        mock_result.title = "Test Article"
        mock_result.highlights = ["Highlight 1 content", "Highlight 2 content"]
        mock_result.published_date = "2024-01-15"
        mock_response.results = [mock_result]

        with patch.dict(os.environ, {"EXA_API_KEY": "exa-test-key"}):
            with patch("tools.web_tools._get_exa_client") as mock_get_client:
                mock_client = MagicMock()
                mock_client.search.return_value = mock_response
                mock_get_client.return_value = mock_client

                result = _exa_search("test query", limit=1)

                assert result["success"] is True
                assert "data" in result
                assert "web" in result["data"]
                assert len(result["data"]["web"]) == 1

                web_result = result["data"]["web"][0]
                assert web_result["url"] == "https://example.com/article"
                assert web_result["title"] == "Test Article"
                assert web_result["description"] == "Highlight 1 content\n\nHighlight 2 content"
                assert web_result["highlights"] == ["Highlight 1 content", "Highlight 2 content"]
                assert web_result["published_date"] == "2024-01-15"
                assert web_result["position"] == 1

    def test_exa_search_uses_search_api(self):
        """_exa_search uses search() with contents.highlights - the modern Exa API."""
        from tools.web_tools import _exa_search

        mock_response = MagicMock()
        mock_response.results = []

        with patch.dict(os.environ, {"EXA_API_KEY": "exa-test-key"}):
            with patch("tools.web_tools._get_exa_client") as mock_get_client:
                mock_client = MagicMock()
                mock_client.search.return_value = mock_response
                mock_get_client.return_value = mock_client

                _exa_search("python async patterns", limit=5)

                # Verify search was called (not deprecated search_and_contents)
                mock_client.search.assert_called_once()
                call_args = mock_client.search.call_args

                # Verify query and limit
                assert call_args[0][0] == "python async patterns"
                assert call_args[1]["num_results"] == 5

                # Verify contents wrapper with highlights nested
                assert "contents" in call_args[1]
                contents = call_args[1]["contents"]
                assert "highlights" in contents
                assert contents["highlights"]["max_characters"] == 2000  # default
                assert contents["highlights"]["query"] == "python async patterns"
                # num_highlights should NOT be present (deprecated parameter)
                assert "num_highlights" not in contents["highlights"]
                # search_and_contents should not be called
                mock_client.search_and_contents.assert_not_called()

    def test_exa_search_with_fallback_disabled(self):
        """_exa_search_with_fallback respects config to disable fallback."""
        from tools.web_tools import _exa_search_with_fallback

        with patch("tools.web_tools._get_exa_config", return_value={
            "highlights_max_characters": 2000,
            "highlights_enabled": True,
            "full_text_fallback": False,  # Disabled
        }):
            with patch("tools.web_tools._exa_search", return_value={
                "success": True,
                "data": {"web": [{"url": "https://example.com", "title": "Test", "highlights": [], "position": 1}]}
            }):
                result = _exa_search_with_fallback("test", limit=1)

                # Should use _exa_search directly since fallback is disabled
                assert result["success"] is True

    def test_exa_search_with_fallback_empty_highlights(self):
        """_exa_search_with_fallback fetches full text only for empty highlights."""
        from tools.web_tools import _exa_search_with_fallback

        # Mock search results with EMPTY highlights (should trigger fallback)
        mock_search_response = {
            "success": True,
            "data": {
                "web": [
                    {
                        "url": "https://example.com",
                        "title": "Test",
                        "highlights": [],  # Empty - should trigger fallback
                        "position": 1,
                    }
                ]
            }
        }

        mock_extract_result = {
            "url": "https://example.com",
            "title": "Test",
            "content": "Full page content here...",
        }

        with patch("tools.web_tools._get_exa_config", return_value={
            "highlights_max_characters": 2000,
            "highlights_enabled": True,
            "full_text_fallback": True,  # Enabled
        }):
            with patch("tools.web_tools._exa_search", return_value=mock_search_response):
                with patch("tools.web_tools._exa_extract", return_value=[mock_extract_result]):
                    result = _exa_search_with_fallback("test", limit=1)

                    assert result["success"] is True
                    web_results = result["data"]["web"]
                    assert len(web_results) == 1
                    # Should have full_text field added for empty highlights
                    assert "full_text" in web_results[0]
                    assert web_results[0]["full_text"] == "Full page content here..."
                    # Description should NOT be replaced with full text
                    assert web_results[0].get("description", "") != "Full page content here..."

    def test_exa_search_with_fallback_short_highlights_not_triggered(self):
        """_exa_search_with_fallback does NOT fetch full text for short highlights."""
        from tools.web_tools import _exa_search_with_fallback

        # Mock search results with SHORT but non-empty highlights
        # Per Exa research, short highlights are still efficient - don't fall back
        mock_search_response = {
            "success": True,
            "data": {
                "web": [
                    {
                        "url": "https://example.com",
                        "title": "Test",
                        "highlights": ["short highlight"],  # Short but NOT empty
                        "position": 1,
                    }
                ]
            }
        }

        with patch("tools.web_tools._get_exa_config", return_value={
            "highlights_max_characters": 2000,
            "highlights_enabled": True,
            "full_text_fallback": True,  # Enabled
        }):
            with patch("tools.web_tools._exa_search", return_value=mock_search_response):
                with patch("tools.web_tools._exa_extract") as mock_extract:
                    result = _exa_search_with_fallback("test", limit=1)

                    assert result["success"] is True
                    web_results = result["data"]["web"]
                    assert len(web_results) == 1
                    # Should NOT have fetched full text for short highlights
                    mock_extract.assert_not_called()
                    # Should NOT have full_text field
                    assert "full_text" not in web_results[0]

    def test_exa_search_with_fallback_explicit_urls(self):
        """_exa_search_with_fallback fetches full text for explicitly requested URLs."""
        from tools.web_tools import _exa_search_with_fallback

        mock_search_response = {
            "success": True,
            "data": {
                "web": [
                    {
                        "url": "https://example.com",
                        "title": "Test",
                        "highlights": ["normal highlight content"],
                        "position": 1,
                    }
                ]
            }
        }

        mock_extract_result = {
            "url": "https://example.com",
            "title": "Test",
            "content": "Explicitly requested full text...",
        }

        with patch("tools.web_tools._get_exa_config", return_value={
            "highlights_max_characters": 2000,
            "highlights_enabled": True,
            "full_text_fallback": True,
        }):
            with patch("tools.web_tools._exa_search", return_value=mock_search_response):
                with patch("tools.web_tools._exa_extract", return_value=[mock_extract_result]) as mock_extract:
                    result = _exa_search_with_fallback(
                        "test",
                        limit=1,
                        urls_to_fallback=["https://example.com"]  # Explicit request
                    )

                    assert result["success"] is True
                    # Should have fetched full text for explicitly requested URL
                    mock_extract.assert_called_once()
                    web_results = result["data"]["web"]
                    assert "full_text" in web_results[0]


class TestCheckWebApiKey:
    """Test suite for check_web_api_key() unified availability check."""

    _ENV_KEYS = (
        "EXA_API_KEY",
        "PARALLEL_API_KEY",
        "FIRECRAWL_API_KEY",
        "FIRECRAWL_API_URL",
        "FIRECRAWL_GATEWAY_URL",
        "TOOL_GATEWAY_DOMAIN",
        "TOOL_GATEWAY_SCHEME",
        "TOOL_GATEWAY_USER_TOKEN",
        "TAVILY_API_KEY",
    )

    def setup_method(self):
        for key in self._ENV_KEYS:
            os.environ.pop(key, None)
        self._managed_patchers = [
            patch("tools.web_tools.managed_nous_tools_enabled", return_value=True),
            patch("tools.managed_tool_gateway.managed_nous_tools_enabled", return_value=True),
        ]
        for p in self._managed_patchers:
            p.start()

    def teardown_method(self):
        for key in self._ENV_KEYS:
            os.environ.pop(key, None)
        for p in self._managed_patchers:
            p.stop()

    def test_parallel_key_only(self):
        with patch.dict(os.environ, {"PARALLEL_API_KEY": "test-key"}):
            from tools.web_tools import check_web_api_key
            assert check_web_api_key() is True

    def test_exa_key_only(self):
        with patch.dict(os.environ, {"EXA_API_KEY": "exa-test"}):
            from tools.web_tools import check_web_api_key
            assert check_web_api_key() is True

    def test_firecrawl_key_only(self):
        with patch.dict(os.environ, {"FIRECRAWL_API_KEY": "fc-test"}):
            from tools.web_tools import check_web_api_key
            assert check_web_api_key() is True

    def test_firecrawl_url_only(self):
        with patch.dict(os.environ, {"FIRECRAWL_API_URL": "http://localhost:3002"}):
            from tools.web_tools import check_web_api_key
            assert check_web_api_key() is True

    def test_tavily_key_only(self):
        with patch.dict(os.environ, {"TAVILY_API_KEY": "tvly-test"}):
            from tools.web_tools import check_web_api_key
            assert check_web_api_key() is True

    def test_no_keys_returns_false(self):
        from tools.web_tools import check_web_api_key
        assert check_web_api_key() is False

    def test_both_keys_returns_true(self):
        with patch.dict(os.environ, {
            "PARALLEL_API_KEY": "test-key",
            "FIRECRAWL_API_KEY": "fc-test",
        }):
            from tools.web_tools import check_web_api_key
            assert check_web_api_key() is True

    def test_all_three_keys_returns_true(self):
        with patch.dict(os.environ, {
            "PARALLEL_API_KEY": "test-key",
            "FIRECRAWL_API_KEY": "fc-test",
            "TAVILY_API_KEY": "tvly-test",
        }):
            from tools.web_tools import check_web_api_key
            assert check_web_api_key() is True

    def test_tool_gateway_returns_true(self):
        with patch("tools.web_tools._read_nous_access_token", return_value="nous-token"):
            from tools.web_tools import check_web_api_key
            assert check_web_api_key() is True

    def test_configured_backend_must_match_available_provider(self):
        with patch("tools.web_tools._load_web_config", return_value={"backend": "parallel"}):
            with patch("tools.web_tools._read_nous_access_token", return_value="nous-token"):
                with patch.dict(os.environ, {"FIRECRAWL_GATEWAY_URL": "http://127.0.0.1:3002"}, clear=False):
                    from tools.web_tools import check_web_api_key
                    assert check_web_api_key() is False

    def test_configured_firecrawl_backend_accepts_managed_gateway(self):
        with patch("tools.web_tools._load_web_config", return_value={"backend": "firecrawl"}):
            with patch("tools.web_tools._read_nous_access_token", return_value="nous-token"):
                with patch.dict(os.environ, {"FIRECRAWL_GATEWAY_URL": "http://127.0.0.1:3002"}, clear=False):
                    from tools.web_tools import check_web_api_key
                    assert check_web_api_key() is True


def test_web_requires_env_includes_exa_key():
    from tools.web_tools import _web_requires_env

    assert "EXA_API_KEY" in _web_requires_env()


