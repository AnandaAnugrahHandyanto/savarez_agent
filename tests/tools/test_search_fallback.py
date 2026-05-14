"""Tests for the web_search fallback chain.

Covers:
- ``_get_search_fallback_backends`` config parsing + availability filtering
- ``_dispatch_search_backend`` returns provider response unchanged on success
- ``_dispatch_search_backend`` converts provider exceptions to a
  ``{"success": False, "error": ...}`` dict
- ``web_search_tool`` falls back from a failing primary to the next backend
- ``web_search_tool`` is unchanged when no fallbacks are configured
- ``web_search_tool`` returns the last failure when all backends fail
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# _get_search_fallback_backends
# ---------------------------------------------------------------------------


class TestGetSearchFallbackBackends:
    def test_empty_when_unconfigured(self, monkeypatch):
        from tools import web_tools
        monkeypatch.setattr(web_tools, "_load_web_config", lambda: {})
        assert web_tools._get_search_fallback_backends(exclude="brave-free") == []

    def test_filters_unavailable_backends(self, monkeypatch):
        from tools import web_tools
        monkeypatch.setattr(
            web_tools,
            "_load_web_config",
            lambda: {"search_fallback_backends": ["ddgs", "tavily"]},
        )
        # Tavily unconfigured, ddgs present
        monkeypatch.setattr(web_tools, "_ddgs_package_importable", lambda: True)
        monkeypatch.delenv("TAVILY_API_KEY", raising=False)
        assert web_tools._get_search_fallback_backends(exclude="brave-free") == ["ddgs"]

    def test_excludes_primary(self, monkeypatch):
        from tools import web_tools
        monkeypatch.setattr(
            web_tools,
            "_load_web_config",
            lambda: {"search_fallback_backends": ["brave-free", "ddgs"]},
        )
        monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "k")
        monkeypatch.setattr(web_tools, "_ddgs_package_importable", lambda: True)
        # Even though brave-free is listed and available, it is the primary
        # so we should skip it and only return ddgs.
        assert web_tools._get_search_fallback_backends(exclude="brave-free") == ["ddgs"]

    def test_dedupes(self, monkeypatch):
        from tools import web_tools
        monkeypatch.setattr(
            web_tools,
            "_load_web_config",
            lambda: {"search_fallback_backends": ["ddgs", "ddgs", "DDGS"]},
        )
        monkeypatch.setattr(web_tools, "_ddgs_package_importable", lambda: True)
        assert web_tools._get_search_fallback_backends(exclude="brave-free") == ["ddgs"]

    def test_non_list_value_returns_empty(self, monkeypatch):
        from tools import web_tools
        monkeypatch.setattr(
            web_tools,
            "_load_web_config",
            lambda: {"search_fallback_backends": "ddgs"},
        )
        assert web_tools._get_search_fallback_backends(exclude="brave-free") == []

    def test_preserves_order(self, monkeypatch):
        from tools import web_tools
        monkeypatch.setattr(
            web_tools,
            "_load_web_config",
            lambda: {"search_fallback_backends": ["ddgs", "searxng"]},
        )
        monkeypatch.setattr(web_tools, "_ddgs_package_importable", lambda: True)
        monkeypatch.setenv("SEARXNG_URL", "http://localhost:8080")
        assert web_tools._get_search_fallback_backends(exclude="brave-free") == [
            "ddgs",
            "searxng",
        ]


# ---------------------------------------------------------------------------
# _dispatch_search_backend
# ---------------------------------------------------------------------------


class TestDispatchSearchBackend:
    def test_returns_provider_response_on_success(self, monkeypatch):
        from tools import web_tools
        sentinel = {"success": True, "data": {"web": [{"title": "ok", "url": "https://x", "description": "", "position": 1}]}}

        class FakeBrave:
            def search(self, query, limit=5):
                return sentinel

        monkeypatch.setattr(
            "tools.web_providers.brave_free.BraveFreeSearchProvider",
            lambda: FakeBrave(),
        )
        out = web_tools._dispatch_search_backend("brave-free", "q", 5)
        assert out is sentinel

    def test_converts_exception_to_failure_dict(self, monkeypatch):
        from tools import web_tools

        class Boom:
            def search(self, query, limit=5):
                raise RuntimeError("boom")

        monkeypatch.setattr(
            "tools.web_providers.brave_free.BraveFreeSearchProvider",
            lambda: Boom(),
        )
        out = web_tools._dispatch_search_backend("brave-free", "q", 5)
        assert out["success"] is False
        assert "Backend brave-free failed" in out["error"]
        assert "boom" in out["error"]


# ---------------------------------------------------------------------------
# web_search_tool fallback behavior
# ---------------------------------------------------------------------------


class TestWebSearchToolFallback:
    _OK_RESPONSE = {
        "success": True,
        "data": {
            "web": [
                {"title": "T", "url": "https://example.com", "description": "D", "position": 1},
            ]
        },
    }
    _FAIL_RESPONSE = {"success": False, "error": "rate limited"}

    def test_no_fallback_returns_primary_response(self, monkeypatch):
        from tools import web_tools
        monkeypatch.setattr(web_tools, "_get_search_backend", lambda: "brave-free")
        monkeypatch.setattr(web_tools, "_get_search_fallback_backends", lambda exclude: [])
        with patch.object(
            web_tools,
            "_dispatch_search_backend",
            return_value=self._OK_RESPONSE,
        ) as mock_dispatch:
            out = json.loads(web_tools.web_search_tool("q", 3))
        assert out == self._OK_RESPONSE
        mock_dispatch.assert_called_once_with("brave-free", "q", 3)

    def test_falls_back_when_primary_fails(self, monkeypatch):
        from tools import web_tools
        monkeypatch.setattr(web_tools, "_get_search_backend", lambda: "brave-free")
        monkeypatch.setattr(
            web_tools,
            "_get_search_fallback_backends",
            lambda exclude: ["ddgs"],
        )
        responses = [self._FAIL_RESPONSE, self._OK_RESPONSE]

        def fake_dispatch(backend, query, limit):
            return responses.pop(0)

        monkeypatch.setattr(web_tools, "_dispatch_search_backend", fake_dispatch)
        out = json.loads(web_tools.web_search_tool("q", 3))
        assert out["success"] is True
        assert out["data"]["web"][0]["url"] == "https://example.com"
        # Both backends consumed (primary + ddgs)
        assert responses == []

    def test_returns_last_failure_when_all_fail(self, monkeypatch):
        from tools import web_tools
        monkeypatch.setattr(web_tools, "_get_search_backend", lambda: "brave-free")
        monkeypatch.setattr(
            web_tools,
            "_get_search_fallback_backends",
            lambda exclude: ["ddgs"],
        )
        last_fail = {"success": False, "error": "ddgs no results"}
        responses = [self._FAIL_RESPONSE, last_fail]

        def fake_dispatch(backend, query, limit):
            return responses.pop(0)

        monkeypatch.setattr(web_tools, "_dispatch_search_backend", fake_dispatch)
        out = json.loads(web_tools.web_search_tool("q", 3))
        assert out["success"] is False
        assert out["error"] == "ddgs no results"

    def test_skips_fallback_when_primary_succeeds(self, monkeypatch):
        from tools import web_tools
        monkeypatch.setattr(web_tools, "_get_search_backend", lambda: "brave-free")
        monkeypatch.setattr(
            web_tools,
            "_get_search_fallback_backends",
            lambda exclude: ["ddgs"],
        )
        call_log = []

        def fake_dispatch(backend, query, limit):
            call_log.append(backend)
            return self._OK_RESPONSE

        monkeypatch.setattr(web_tools, "_dispatch_search_backend", fake_dispatch)
        web_tools.web_search_tool("q", 3)
        assert call_log == ["brave-free"]
