"""Tests for the Brave Search (free tier) web search provider.

Covers:
- BraveFreeSearchProvider.is_configured() env var gating
- BraveFreeSearchProvider.search() — happy path, HTTP error, request error, bad JSON
- Result normalization (title, url, description, position)
- Limit truncation + Brave's count cap (20)
- _is_backend_available("brave-free") integration
- _get_backend() recognizes "brave-free" as a valid configured backend
- check_web_api_key() includes brave-free in availability check
- web_extract / web_crawl return search-only errors when brave-free is active
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# BraveFreeSearchProvider unit tests
# ---------------------------------------------------------------------------


class TestBraveFreeProviderIsConfigured:
    def test_configured_when_key_set(self, monkeypatch):
        monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "BSAkey123")
        from tools.web_providers.brave_free import BraveFreeSearchProvider
        assert BraveFreeSearchProvider().is_configured() is True

    def test_not_configured_when_key_missing(self, monkeypatch):
        monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
        from tools.web_providers.brave_free import BraveFreeSearchProvider
        assert BraveFreeSearchProvider().is_configured() is False

    def test_not_configured_when_key_whitespace(self, monkeypatch):
        monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "   ")
        from tools.web_providers.brave_free import BraveFreeSearchProvider
        assert BraveFreeSearchProvider().is_configured() is False

    def test_provider_name(self):
        from tools.web_providers.brave_free import BraveFreeSearchProvider
        assert BraveFreeSearchProvider().provider_name() == "brave-free"

    def test_implements_web_search_provider(self):
        from tools.web_providers.base import WebSearchProvider
        from tools.web_providers.brave_free import BraveFreeSearchProvider
        assert issubclass(BraveFreeSearchProvider, WebSearchProvider)


class TestBraveFreeProviderSearch:
    _SAMPLE_RESPONSE = {
        "web": {
            "results": [
                {"title": "A", "url": "https://a.example.com", "description": "desc A"},
                {"title": "B", "url": "https://b.example.com", "description": "desc B"},
                {"title": "C", "url": "https://c.example.com", "description": "desc C"},
            ]
        }
    }

    @staticmethod
    def _mock_resp(json_data, status_code=200):
        m = MagicMock()
        m.status_code = status_code
        m.json.return_value = json_data
        m.raise_for_status = MagicMock()
        return m

    def test_happy_path_normalizes_results(self, monkeypatch):
        monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "BSAkey123")
        from tools.web_providers.brave_free import BraveFreeSearchProvider

        with patch("httpx.get", return_value=self._mock_resp(self._SAMPLE_RESPONSE)):
            result = BraveFreeSearchProvider().search("test query", limit=5)

        assert result["success"] is True
        web = result["data"]["web"]
        assert len(web) == 3
        assert web[0] == {"title": "A", "url": "https://a.example.com", "description": "desc A", "position": 1}
        assert web[2]["position"] == 3

    def test_sends_subscription_token_header_and_count(self, monkeypatch):
        """Brave uses X-Subscription-Token; count maps from limit."""
        monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "BSAkey123")
        from tools.web_providers.brave_free import BraveFreeSearchProvider

        captured = {}

        def fake_get(url, **kwargs):
            captured["url"] = url
            captured["headers"] = kwargs.get("headers", {})
            captured["params"] = kwargs.get("params", {})
            return self._mock_resp({"web": {"results": []}})

        with patch("httpx.get", side_effect=fake_get):
            BraveFreeSearchProvider().search("q", limit=5)

        assert captured["url"] == "https://api.search.brave.com/res/v1/web/search"
        assert captured["headers"].get("X-Subscription-Token") == "BSAkey123"
        assert captured["params"].get("q") == "q"
        assert captured["params"].get("count") == 5

    def test_count_is_capped_at_20(self, monkeypatch):
        """Brave caps count at 20 — limit above that clamps."""
        monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "BSAkey123")
        from tools.web_providers.brave_free import BraveFreeSearchProvider

        captured = {}

        def fake_get(url, **kwargs):
            captured["params"] = kwargs.get("params", {})
            return self._mock_resp({"web": {"results": []}})

        with patch("httpx.get", side_effect=fake_get):
            BraveFreeSearchProvider().search("q", limit=100)

        assert captured["params"].get("count") == 20

    def test_limit_is_respected_client_side(self, monkeypatch):
        monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "BSAkey123")
        from tools.web_providers.brave_free import BraveFreeSearchProvider

        with patch("httpx.get", return_value=self._mock_resp(self._SAMPLE_RESPONSE)):
            result = BraveFreeSearchProvider().search("q", limit=2)

        assert result["success"] is True
        assert len(result["data"]["web"]) == 2

    def test_empty_results(self, monkeypatch):
        monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "BSAkey123")
        from tools.web_providers.brave_free import BraveFreeSearchProvider

        with patch("httpx.get", return_value=self._mock_resp({"web": {"results": []}})):
            result = BraveFreeSearchProvider().search("nothing", limit=5)

        assert result["success"] is True
        assert result["data"]["web"] == []

    def test_missing_web_key_returns_empty(self, monkeypatch):
        """Responses without a ``web`` block should produce an empty result set, not crash."""
        monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "BSAkey123")
        from tools.web_providers.brave_free import BraveFreeSearchProvider

        with patch("httpx.get", return_value=self._mock_resp({})):
            result = BraveFreeSearchProvider().search("q", limit=5)

        assert result["success"] is True
        assert result["data"]["web"] == []

    def test_non_dict_web_value_returns_empty_not_crash(self, monkeypatch):
        """A 200 body shaped like ``{"web": <non-dict>}`` must not AttributeError.

        Regression for ``(data.get("web") or {}).get("results", [])`` —
        if ``data["web"]`` is a non-dict truthy value (e.g. an error
        envelope coerced to a string by a permissive proxy, or an HTML
        snippet a tolerant JSON decoder reduced to a literal), the legacy
        code raised ``AttributeError`` and aborted the tool with no
        graceful failure. The provider must instead surface an empty
        result set so the caller can fall back.
        """
        monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "BSAkey123")
        from tools.web_providers.brave_free import BraveFreeSearchProvider

        for malformed in ({"web": "rate-limited"}, {"web": 0xdead}, {"web": ["a", "b"]}):
            with patch("httpx.get", return_value=self._mock_resp(malformed)):
                result = BraveFreeSearchProvider().search("q", limit=5)
            assert result["success"] is True, f"crashed on {malformed!r}: {result}"
            assert result["data"]["web"] == [], f"non-empty for {malformed!r}: {result}"

    def test_non_dict_results_items_are_skipped(self, monkeypatch):
        """``data["web"]["results"]`` items that aren't dicts must be skipped, not crash.

        Same defensive concern as
        ``test_non_dict_web_value_returns_empty_not_crash`` but one level
        down: if Brave (or a proxy) returns a list mixing dict and
        non-dict items, the per-item ``r.get(...)`` calls crash. The
        provider should drop the bad items and keep the good ones.
        """
        monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "BSAkey123")
        from tools.web_providers.brave_free import BraveFreeSearchProvider

        body = {
            "web": {
                "results": [
                    {"title": "Real", "url": "https://real.example.com", "description": "ok"},
                    "https://stringified-url.example.com",  # non-dict, must be skipped
                    None,                                    # non-dict, must be skipped
                    {"title": "Also real", "url": "https://other.example.com", "description": "ok"},
                ]
            }
        }
        with patch("httpx.get", return_value=self._mock_resp(body)):
            result = BraveFreeSearchProvider().search("q", limit=5)

        assert result["success"] is True
        web = result["data"]["web"]
        assert len(web) == 2
        assert [r["title"] for r in web] == ["Real", "Also real"]
        # Position must reflect post-filter index, not original list index.
        assert web[0]["position"] == 1
        assert web[1]["position"] == 2

    def test_non_list_results_value_returns_empty(self, monkeypatch):
        """``data["web"]["results"]`` that isn't a list must produce an empty
        result set instead of raising ``TypeError`` on the slice.
        """
        monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "BSAkey123")
        from tools.web_providers.brave_free import BraveFreeSearchProvider

        with patch("httpx.get", return_value=self._mock_resp({"web": {"results": "not-a-list"}})):
            result = BraveFreeSearchProvider().search("q", limit=5)

        assert result["success"] is True
        assert result["data"]["web"] == []

    def test_top_level_non_dict_response_returns_empty(self, monkeypatch):
        """A ``resp.json()`` that returns something that isn't a dict at all
        (e.g. ``[]`` or ``"string"``) must not AttributeError on
        ``data.get(...)``.
        """
        monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "BSAkey123")
        from tools.web_providers.brave_free import BraveFreeSearchProvider

        for malformed in ([], "plain-string", 42, None):
            with patch("httpx.get", return_value=self._mock_resp(malformed)):
                result = BraveFreeSearchProvider().search("q", limit=5)
            assert result["success"] is True, f"crashed on {malformed!r}: {result}"
            assert result["data"]["web"] == [], f"non-empty for {malformed!r}: {result}"

    def test_http_error_returns_failure(self, monkeypatch):
        import httpx
        monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "BSAkey123")
        from tools.web_providers.brave_free import BraveFreeSearchProvider

        bad = MagicMock()
        bad.status_code = 429
        err = httpx.HTTPStatusError("429", request=MagicMock(), response=bad)

        with patch("httpx.get", side_effect=err):
            result = BraveFreeSearchProvider().search("q", limit=5)

        assert result["success"] is False
        assert "429" in result["error"]

    def test_request_error_returns_failure(self, monkeypatch):
        import httpx
        monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "BSAkey123")
        from tools.web_providers.brave_free import BraveFreeSearchProvider

        with patch("httpx.get", side_effect=httpx.RequestError("boom")):
            result = BraveFreeSearchProvider().search("q", limit=5)

        assert result["success"] is False
        assert "boom" in result["error"] or "Brave" in result["error"]

    def test_missing_key_returns_failure(self, monkeypatch):
        monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
        from tools.web_providers.brave_free import BraveFreeSearchProvider

        result = BraveFreeSearchProvider().search("q", limit=5)
        assert result["success"] is False
        assert "BRAVE_SEARCH_API_KEY" in result["error"]


# ---------------------------------------------------------------------------
# Integration: _is_backend_available / _get_backend / check_web_api_key
# ---------------------------------------------------------------------------


class TestBraveFreeBackendWiring:
    def test_is_backend_available_true_when_key_set(self, monkeypatch):
        monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "BSAkey123")
        from tools.web_tools import _is_backend_available
        assert _is_backend_available("brave-free") is True

    def test_is_backend_available_false_when_key_missing(self, monkeypatch):
        monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
        from tools.web_tools import _is_backend_available
        assert _is_backend_available("brave-free") is False

    def test_configured_backend_accepted(self, monkeypatch):
        from tools import web_tools
        monkeypatch.setattr(web_tools, "_load_web_config", lambda: {"backend": "brave-free"})
        monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "BSAkey123")
        assert web_tools._get_backend() == "brave-free"

    def test_auto_detect_picks_brave_free_when_only_key_set(self, monkeypatch):
        from tools import web_tools
        monkeypatch.setattr(web_tools, "_load_web_config", lambda: {})
        for key in ("FIRECRAWL_API_KEY", "FIRECRAWL_API_URL", "PARALLEL_API_KEY",
                    "TAVILY_API_KEY", "EXA_API_KEY", "SEARXNG_URL"):
            monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "BSAkey123")
        monkeypatch.setattr(web_tools, "_is_tool_gateway_ready", lambda: False)
        monkeypatch.setattr(web_tools, "_ddgs_package_importable", lambda: False)
        assert web_tools._get_backend() == "brave-free"

    def test_brave_free_does_not_override_paid_provider(self, monkeypatch):
        """Tavily (higher priority) should win in auto-detect."""
        from tools import web_tools
        monkeypatch.setattr(web_tools, "_load_web_config", lambda: {})
        for key in ("FIRECRAWL_API_KEY", "FIRECRAWL_API_URL", "PARALLEL_API_KEY", "EXA_API_KEY", "SEARXNG_URL"):
            monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv("TAVILY_API_KEY", "tvly")
        monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "BSAkey123")
        monkeypatch.setattr(web_tools, "_is_tool_gateway_ready", lambda: False)
        assert web_tools._get_backend() == "tavily"

    def test_check_web_api_key_true_when_brave_free_configured(self, monkeypatch):
        from tools import web_tools
        monkeypatch.setattr(web_tools, "_load_web_config", lambda: {"backend": "brave-free"})
        monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "BSAkey123")
        assert web_tools.check_web_api_key() is True


# ---------------------------------------------------------------------------
# brave-free is search-only: web_extract / web_crawl return clear errors
# ---------------------------------------------------------------------------


class TestBraveFreeSearchOnlyErrors:
    def test_web_extract_returns_search_only_error(self, monkeypatch):
        import asyncio
        from tools import web_tools

        monkeypatch.setattr(web_tools, "_load_web_config", lambda: {"backend": "brave-free"})
        monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "BSAkey123")
        monkeypatch.setattr(web_tools, "_is_tool_gateway_ready", lambda: False)
        monkeypatch.setattr("tools.interrupt.is_interrupted", lambda: False, raising=False)

        result_str = asyncio.get_event_loop().run_until_complete(
            web_tools.web_extract_tool(["https://example.com"])
        )
        result = json.loads(result_str)
        assert result["success"] is False
        assert "search-only" in result["error"].lower()
        assert "brave" in result["error"].lower()

    def test_web_crawl_returns_search_only_error(self, monkeypatch):
        import asyncio
        from tools import web_tools

        monkeypatch.setattr(web_tools, "_load_web_config", lambda: {"backend": "brave-free"})
        monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "BSAkey123")
        monkeypatch.setattr(web_tools, "_is_tool_gateway_ready", lambda: False)
        monkeypatch.setattr(web_tools, "check_firecrawl_api_key", lambda: False)
        monkeypatch.setattr("tools.interrupt.is_interrupted", lambda: False, raising=False)

        result_str = asyncio.get_event_loop().run_until_complete(
            web_tools.web_crawl_tool("https://example.com")
        )
        result = json.loads(result_str)
        assert result["success"] is False
        assert "search-only" in result["error"].lower()
        assert "brave" in result["error"].lower()
