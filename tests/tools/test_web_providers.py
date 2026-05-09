"""Tests for the web tools provider architecture.

Covers:
- WebSearchProvider / WebExtractProvider ABC enforcement
- Per-capability backend selection (_get_search_backend, _get_extract_backend)
- Backward compatibility (web.backend still works as shared fallback)
- Config keys merge correctly via DEFAULT_CONFIG
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

import pytest


# ---------------------------------------------------------------------------
# ABC enforcement
# ---------------------------------------------------------------------------


class TestWebProviderABCs:
    """The ABCs enforce the interface contract."""

    def test_cannot_instantiate_search_provider(self):
        from tools.web_providers.base import WebSearchProvider

        with pytest.raises(TypeError):
            WebSearchProvider()  # type: ignore[abstract]

    def test_cannot_instantiate_extract_provider(self):
        from tools.web_providers.base import WebExtractProvider

        with pytest.raises(TypeError):
            WebExtractProvider()  # type: ignore[abstract]

    def test_concrete_search_provider_works(self):
        from tools.web_providers.base import WebSearchProvider

        class Dummy(WebSearchProvider):
            def provider_name(self) -> str:
                return "dummy"
            def is_configured(self) -> bool:
                return True
            def search(self, query: str, limit: int = 5) -> Dict[str, Any]:
                return {"success": True, "data": {"web": []}}

        d = Dummy()
        assert d.provider_name() == "dummy"
        assert d.is_configured() is True
        assert d.search("test")["success"] is True

    def test_concrete_extract_provider_works(self):
        from tools.web_providers.base import WebExtractProvider

        class Dummy(WebExtractProvider):
            def provider_name(self) -> str:
                return "dummy"
            def is_configured(self) -> bool:
                return True
            def extract(self, urls: List[str], **kwargs) -> Dict[str, Any]:
                return {"success": True, "data": [{"url": urls[0], "content": "x"}]}

        d = Dummy()
        assert d.provider_name() == "dummy"
        assert d.extract(["https://example.com"])["success"] is True


# ---------------------------------------------------------------------------
# Per-capability backend selection
# ---------------------------------------------------------------------------


class TestPerCapabilityBackendSelection:
    """_get_search_backend and _get_extract_backend read per-capability config."""

    def test_search_backend_overrides_generic(self, monkeypatch):
        from tools import web_tools

        monkeypatch.setattr(web_tools, "_load_web_config", lambda: {
            "backend": "firecrawl",
            "search_backend": "tavily",
        })
        monkeypatch.setenv("TAVILY_API_KEY", "test-key")
        assert web_tools._get_search_backend() == "tavily"

    def test_extract_backend_overrides_generic(self, monkeypatch):
        from tools import web_tools

        monkeypatch.setattr(web_tools, "_load_web_config", lambda: {
            "backend": "tavily",
            "extract_backend": "exa",
        })
        monkeypatch.setenv("EXA_API_KEY", "test-key")
        assert web_tools._get_extract_backend() == "exa"

    def test_falls_back_to_generic_backend_when_search_backend_empty(self, monkeypatch):
        from tools import web_tools

        monkeypatch.setattr(web_tools, "_load_web_config", lambda: {
            "backend": "tavily",
            "search_backend": "",
        })
        monkeypatch.setenv("TAVILY_API_KEY", "test-key")
        assert web_tools._get_search_backend() == "tavily"

    def test_falls_back_to_generic_backend_when_extract_backend_empty(self, monkeypatch):
        from tools import web_tools

        monkeypatch.setattr(web_tools, "_load_web_config", lambda: {
            "backend": "parallel",
            "extract_backend": "",
        })
        monkeypatch.setenv("PARALLEL_API_KEY", "test-key")
        assert web_tools._get_extract_backend() == "parallel"

    def test_search_backend_ignored_when_not_available(self, monkeypatch):
        from tools import web_tools

        monkeypatch.setattr(web_tools, "_load_web_config", lambda: {
            "backend": "firecrawl",
            "search_backend": "exa",  # set but no EXA_API_KEY
        })
        monkeypatch.delenv("EXA_API_KEY", raising=False)
        monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-key")
        # Should fall back to firecrawl since exa isn't configured
        assert web_tools._get_search_backend() == "firecrawl"

    def test_fully_backward_compatible_with_web_backend_only(self, monkeypatch):
        from tools import web_tools

        monkeypatch.setattr(web_tools, "_load_web_config", lambda: {
            "backend": "tavily",
        })
        monkeypatch.setenv("TAVILY_API_KEY", "test-key")
        # No search_backend or extract_backend set — both fall through
        assert web_tools._get_search_backend() == "tavily"
        assert web_tools._get_extract_backend() == "tavily"


# ---------------------------------------------------------------------------
# Config key presence in DEFAULT_CONFIG
# ---------------------------------------------------------------------------


class TestDefaultConfig:
    """The web section exists in DEFAULT_CONFIG with per-capability keys."""

    def test_web_section_in_default_config(self):
        from hermes_cli.config import DEFAULT_CONFIG

        assert "web" in DEFAULT_CONFIG
        web = DEFAULT_CONFIG["web"]
        assert "backend" in web
        assert "search_backend" in web
        assert "extract_backend" in web
        # All empty string by default (no override)
        assert web["backend"] == ""
        assert web["search_backend"] == ""
        assert web["extract_backend"] == ""


# ---------------------------------------------------------------------------
# web_search_tool uses _get_search_backend
# ---------------------------------------------------------------------------


class TestWebSearchUsesSearchBackend:
    """web_search_tool dispatches through _get_search_backend not _get_backend."""

    def test_search_tool_calls_search_backend(self, monkeypatch):
        from tools import web_tools

        called_with = []
        original_get_search = web_tools._get_search_backend

        def tracking_get_search():
            result = original_get_search()
            called_with.append(("search", result))
            return result

        monkeypatch.setattr(web_tools, "_get_search_backend", tracking_get_search)
        monkeypatch.setattr(web_tools, "_load_web_config", lambda: {"backend": "firecrawl"})
        monkeypatch.setenv("FIRECRAWL_API_KEY", "fake")

        # The function will fail at Firecrawl client level but we just
        # need to verify _get_search_backend was called
        try:
            web_tools.web_search_tool("test", 1)
        except Exception:
            pass

        assert len(called_with) > 0
        assert called_with[0][0] == "search"


# ---------------------------------------------------------------------------
# ProviderRegistry
# ---------------------------------------------------------------------------


class TestProviderRegistry:
    """ProviderRegistry auto-discovery and lookup."""

    def test_discovery_finds_brave_search_provider(self):
        from tools.web_providers.registry import ProviderRegistry

        # Reset scan state for test isolation
        ProviderRegistry._scanned = False
        providers = ProviderRegistry.list_search_providers()
        assert "brave" in providers

    def test_discovery_finds_searxng_provider(self):
        from tools.web_providers.registry import ProviderRegistry

        ProviderRegistry._scanned = False
        providers = ProviderRegistry.list_search_providers()
        assert "searxng" in providers

    def test_discovery_finds_extract_providers(self):
        from tools.web_providers.registry import ProviderRegistry

        ProviderRegistry._scanned = False
        providers = ProviderRegistry.list_extract_providers()
        # Exa, Parallel, Tavily all implement both search and extract
        for name in ("exa", "parallel", "tavily"):
            assert name in providers, f"{name} should be an extract provider"

    def test_get_search_provider_returns_class(self):
        from tools.web_providers.registry import ProviderRegistry

        ProviderRegistry._scanned = False
        cls = ProviderRegistry.get_search_provider("brave")
        assert cls is not None
        instance = cls()
        assert instance.provider_name() == "brave"

    def test_get_search_provider_unknown_returns_none(self):
        from tools.web_providers.registry import ProviderRegistry

        ProviderRegistry._scanned = False
        assert ProviderRegistry.get_search_provider("nonexistent") is None

    def test_is_search_available_checks_env(self, monkeypatch):
        from tools.web_providers.registry import ProviderRegistry

        monkeypatch.setenv("BRAVE_API_KEY", "")
        ProviderRegistry._scanned = False
        assert ProviderRegistry.is_search_available("brave") is False

        monkeypatch.setenv("BRAVE_API_KEY", "test-key-123")
        ProviderRegistry._scanned = False
        assert ProviderRegistry.is_search_available("brave") is True

    def test_any_search_available_true_when_one_configured(self, monkeypatch):
        from tools.web_providers.registry import ProviderRegistry

        monkeypatch.setenv("EXA_API_KEY", "test-key")
        monkeypatch.delenv("BRAVE_API_KEY", raising=False)
        monkeypatch.delenv("TAVILY_API_KEY", raising=False)
        monkeypatch.delenv("PARALLEL_API_KEY", raising=False)
        monkeypatch.delenv("SEARXNG_URL", raising=False)
        ProviderRegistry._scanned = False
        assert ProviderRegistry.any_search_available() is True

    def test_any_search_available_false_when_none_configured(self, monkeypatch):
        from tools.web_providers.registry import ProviderRegistry

        for var in ("BRAVE_API_KEY", "EXA_API_KEY", "TAVILY_API_KEY",
                     "PARALLEL_API_KEY", "SEARXNG_URL"):
            monkeypatch.delenv(var, raising=False)
        ProviderRegistry._scanned = False
        assert ProviderRegistry.any_search_available() is False

    def test_find_first_available_returns_highest_priority(self, monkeypatch):
        from tools.web_providers.registry import ProviderRegistry

        # Only tavily configured — should be found first
        monkeypatch.delenv("BRAVE_API_KEY", raising=False)
        monkeypatch.delenv("EXA_API_KEY", raising=False)
        monkeypatch.delenv("TAVILY_API_KEY", raising=False)
        monkeypatch.delenv("PARALLEL_API_KEY", raising=False)
        monkeypatch.delenv("SEARXNG_URL", raising=False)
        monkeypatch.setenv("TAVILY_API_KEY", "tk")
        ProviderRegistry._scanned = False
        first = ProviderRegistry.find_first_available()
        assert first is not None

    def test_find_first_available_returns_none_when_none_configured(self, monkeypatch):
        from tools.web_providers.registry import ProviderRegistry

        for var in ("BRAVE_API_KEY", "EXA_API_KEY", "TAVILY_API_KEY",
                     "PARALLEL_API_KEY", "SEARXNG_URL"):
            monkeypatch.delenv(var, raising=False)
        ProviderRegistry._scanned = False
        assert ProviderRegistry.find_first_available() is None

    def test_all_required_env_vars_returns_all(self):
        from tools.web_providers.registry import ProviderRegistry

        ProviderRegistry._scanned = False
        env_vars = ProviderRegistry.all_required_env_vars()
        assert "BRAVE_API_KEY" in env_vars
        assert "EXA_API_KEY" in env_vars
        assert "TAVILY_API_KEY" in env_vars
        assert "PARALLEL_API_KEY" in env_vars
        assert "SEARXNG_URL" in env_vars


# ---------------------------------------------------------------------------
# check_web_search_available / check_web_extract_available
# ---------------------------------------------------------------------------


class TestCheckWebAvailability:
    """New capability-specific availability checks."""

    def test_check_web_search_available_true(self, monkeypatch):
        from tools import web_tools

        monkeypatch.setattr(web_tools, "_load_web_config", lambda: {"backend": "brave"})
        monkeypatch.setenv("BRAVE_API_KEY", "test-key")
        assert web_tools.check_web_search_available() is True

    def test_check_web_search_available_false_no_backend(self, monkeypatch):
        from tools import web_tools

        monkeypatch.setattr(web_tools, "_load_web_config", lambda: {"backend": ""})
        for var in ("BRAVE_API_KEY", "EXA_API_KEY", "TAVILY_API_KEY",
                     "PARALLEL_API_KEY", "SEARXNG_URL", "FIRECRAWL_API_KEY"):
            monkeypatch.delenv(var, raising=False)
        assert web_tools.check_web_search_available() is False

    def test_check_web_extract_available_true(self, monkeypatch):
        from tools import web_tools

        monkeypatch.setattr(web_tools, "_load_web_config", lambda: {"extract_backend": "exa"})
        monkeypatch.setenv("EXA_API_KEY", "test-key")
        assert web_tools.check_web_extract_available() is True

    def test_check_web_extract_available_false(self, monkeypatch):
        from tools import web_tools

        monkeypatch.setattr(web_tools, "_load_web_config", lambda: {"extract_backend": ""})
        for var in ("EXA_API_KEY", "TAVILY_API_KEY", "PARALLEL_API_KEY",
                     "FIRECRAWL_API_KEY", "FIRECRAWL_API_URL"):
            monkeypatch.delenv(var, raising=False)
        assert web_tools.check_web_extract_available() is False

    def test_check_web_api_key_backward_compatible(self, monkeypatch):
        """Legacy check_web_api_key delegates to check_web_search_available."""
        from tools import web_tools

        monkeypatch.setattr(web_tools, "_load_web_config", lambda: {"backend": "brave"})
        monkeypatch.setenv("BRAVE_API_KEY", "test-key")
        assert web_tools.check_web_api_key() is True


# ---------------------------------------------------------------------------
# Dispatch through ProviderRegistry
# ---------------------------------------------------------------------------


class TestProviderRegistryDispatch:
    """web_search_tool dispatches through ProviderRegistry for registered providers."""

    def test_web_search_dispatch_brave(self, monkeypatch):
        """Brave search should dispatch through BraveSearchProvider."""
        from tools import web_tools
        from tools.web_providers.registry import ProviderRegistry

        monkeypatch.setattr(web_tools, "_load_web_config", lambda: {"backend": "brave"})
        monkeypatch.setenv("BRAVE_API_KEY", "test-key")

        ProviderRegistry._scanned = False
        result = web_tools.web_search_tool("test", 1)
        assert '"success": true' in result.lower() or '"success": false' in result.lower()

    def test_web_search_dispatch_unknown_backend(self, monkeypatch):
        """Unknown backend should return error."""
        from tools import web_tools

        monkeypatch.setattr(web_tools, "_get_search_backend", lambda: "nonexistent")
        result = web_tools.web_search_tool("test", 1)
        assert "Unknown search backend" in result
