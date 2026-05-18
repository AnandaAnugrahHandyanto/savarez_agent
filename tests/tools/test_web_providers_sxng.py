"""Tests for the local sxng-search wrapper web search provider.

Covers:
- command discovery via PATH or SXNG_SEARCH_COMMAND
- JSON result normalization from the sxng-search wrapper
- backend wiring as an optional search-only provider
- web_search_tool dispatch when web.search_backend is sxng / searxng-wrapper
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch


class TestSxngProviderIsConfigured:
    def test_configured_when_command_on_path(self, monkeypatch):
        monkeypatch.delenv("SXNG_SEARCH_COMMAND", raising=False)
        monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/sxng-search" if name == "sxng-search" else None)
        from tools.web_providers.sxng import SxngSearchProvider
        assert SxngSearchProvider().is_configured() is True

    def test_configured_when_explicit_command_set(self, monkeypatch):
        monkeypatch.setenv("SXNG_SEARCH_COMMAND", "/opt/bin/sxng-search")
        from tools.web_providers.sxng import SxngSearchProvider
        assert SxngSearchProvider().is_configured() is True

    def test_not_configured_without_command(self, monkeypatch):
        monkeypatch.delenv("SXNG_SEARCH_COMMAND", raising=False)
        monkeypatch.setattr("shutil.which", lambda name: None)
        from tools.web_providers.sxng import SxngSearchProvider
        assert SxngSearchProvider().is_configured() is False

    def test_provider_name(self):
        from tools.web_providers.sxng import SxngSearchProvider
        assert SxngSearchProvider().provider_name() == "sxng"

    def test_implements_web_search_provider(self):
        from tools.web_providers.base import WebSearchProvider
        from tools.web_providers.sxng import SxngSearchProvider
        assert issubclass(SxngSearchProvider, WebSearchProvider)


class TestSxngProviderSearch:
    def test_happy_path_normalizes_results(self, monkeypatch):
        monkeypatch.setenv("SXNG_SEARCH_COMMAND", "/opt/bin/sxng-search")
        from tools.web_providers.sxng import SxngSearchProvider

        completed = MagicMock()
        completed.stdout = json.dumps({
            "results": [
                {"title": "A", "url": "https://a.example.com", "content": "desc A", "engine": "bing"},
                {"title": "B", "url": "https://b.example.com", "description": "desc B", "source": "google news rss"},
            ]
        })
        completed.stderr = ""
        completed.returncode = 0

        with patch("subprocess.run", return_value=completed) as run:
            result = SxngSearchProvider().search("test query", limit=5)

        assert result["success"] is True
        assert result["data"]["web"] == [
            {"title": "A", "url": "https://a.example.com", "description": "desc A", "position": 1},
            {"title": "B", "url": "https://b.example.com", "description": "desc B", "position": 2},
        ]
        args = run.call_args.args[0]
        assert args[:2] == ["/opt/bin/sxng-search", "test query"]
        assert "--json" in args
        assert args[args.index("--limit") + 1] == "5"

    def test_accepts_web_field_shape_and_respects_limit(self, monkeypatch):
        monkeypatch.setenv("SXNG_SEARCH_COMMAND", "/opt/bin/sxng-search")
        from tools.web_providers.sxng import SxngSearchProvider

        completed = MagicMock()
        completed.stdout = json.dumps({
            "web": [
                {"title": "A", "url": "https://a.example.com", "snippet": "desc A"},
                {"title": "B", "url": "https://b.example.com", "snippet": "desc B"},
                {"title": "C", "url": "https://c.example.com", "snippet": "desc C"},
            ]
        })
        completed.stderr = ""
        completed.returncode = 0

        with patch("subprocess.run", return_value=completed):
            result = SxngSearchProvider().search("q", limit=2)

        assert result["success"] is True
        assert len(result["data"]["web"]) == 2
        assert result["data"]["web"][1]["position"] == 2

    def test_nonzero_exit_returns_failure(self, monkeypatch):
        monkeypatch.setenv("SXNG_SEARCH_COMMAND", "/opt/bin/sxng-search")
        from tools.web_providers.sxng import SxngSearchProvider

        completed = MagicMock()
        completed.stdout = ""
        completed.stderr = "backend unavailable"
        completed.returncode = 2

        with patch("subprocess.run", return_value=completed):
            result = SxngSearchProvider().search("q", limit=5)

        assert result["success"] is False
        assert "backend unavailable" in result["error"]

    def test_bad_json_returns_failure(self, monkeypatch):
        monkeypatch.setenv("SXNG_SEARCH_COMMAND", "/opt/bin/sxng-search")
        from tools.web_providers.sxng import SxngSearchProvider

        completed = MagicMock()
        completed.stdout = "not json"
        completed.stderr = ""
        completed.returncode = 0

        with patch("subprocess.run", return_value=completed):
            result = SxngSearchProvider().search("q", limit=5)

        assert result["success"] is False
        assert "parse" in result["error"].lower() or "json" in result["error"].lower()


class TestSxngBackendWiring:
    def test_is_backend_available_true_when_command_exists(self, monkeypatch):
        monkeypatch.setenv("SXNG_SEARCH_COMMAND", "/opt/bin/sxng-search")
        from tools.web_tools import _is_backend_available
        assert _is_backend_available("sxng") is True
        assert _is_backend_available("searxng-wrapper") is True

    def test_configured_backend_accepted(self, monkeypatch):
        from tools import web_tools
        monkeypatch.setattr(web_tools, "_load_web_config", lambda: {"backend": "sxng"})
        monkeypatch.setenv("SXNG_SEARCH_COMMAND", "/opt/bin/sxng-search")
        assert web_tools._get_backend() == "sxng"

    def test_search_backend_alias_accepted(self, monkeypatch):
        from tools import web_tools
        monkeypatch.setattr(web_tools, "_load_web_config", lambda: {"search_backend": "searxng-wrapper"})
        monkeypatch.setenv("SXNG_SEARCH_COMMAND", "/opt/bin/sxng-search")
        assert web_tools._get_search_backend() == "sxng"

    def test_auto_detect_picks_sxng_only_after_paid_and_searxng_backends(self, monkeypatch):
        from tools import web_tools
        monkeypatch.setattr(web_tools, "_load_web_config", lambda: {})
        for key in ("FIRECRAWL_API_KEY", "FIRECRAWL_API_URL", "PARALLEL_API_KEY", "EXA_API_KEY", "TAVILY_API_KEY", "SEARXNG_URL", "BRAVE_SEARCH_API_KEY"):
            monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv("SXNG_SEARCH_COMMAND", "/opt/bin/sxng-search")
        monkeypatch.setattr(web_tools, "_is_tool_gateway_ready", lambda: False)
        monkeypatch.setattr(web_tools, "_ddgs_package_importable", lambda: False)
        assert web_tools._get_backend() == "sxng"

    def test_web_search_tool_dispatches_to_sxng(self, monkeypatch):
        from tools import web_tools
        monkeypatch.setattr(web_tools, "_load_web_config", lambda: {"search_backend": "sxng"})
        monkeypatch.setenv("SXNG_SEARCH_COMMAND", "/opt/bin/sxng-search")
        monkeypatch.setattr("tools.interrupt.is_interrupted", lambda: False, raising=False)

        class FakeProvider:
            def is_configured(self):
                return True

            def search(self, query, limit):
                return {"success": True, "data": {"web": [{"title": query, "url": "https://example.com", "description": "ok", "position": 1}]}}

        with patch("tools.web_providers.sxng.SxngSearchProvider", return_value=FakeProvider()):
            result = json.loads(web_tools.web_search_tool("hello", limit=1))

        assert result["success"] is True
        assert result["data"]["web"][0]["title"] == "hello"


class TestSxngSearchOnlyErrors:
    def test_web_extract_returns_search_only_error(self, monkeypatch):
        import asyncio
        from tools import web_tools

        monkeypatch.setattr(web_tools, "_load_web_config", lambda: {"backend": "sxng"})
        monkeypatch.setenv("SXNG_SEARCH_COMMAND", "/opt/bin/sxng-search")
        monkeypatch.setattr(web_tools, "_is_tool_gateway_ready", lambda: False)
        monkeypatch.setattr("tools.interrupt.is_interrupted", lambda: False, raising=False)

        result_str = asyncio.get_event_loop().run_until_complete(
            web_tools.web_extract_tool(["https://example.com"])
        )
        result = json.loads(result_str)
        assert result["success"] is False
        assert "search-only" in result["error"].lower()
        assert "sxng" in result["error"].lower() or "searxng" in result["error"].lower()
