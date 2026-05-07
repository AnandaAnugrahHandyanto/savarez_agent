"""Tests for the TinyFish Search + Fetch web provider."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock, patch


class TestTinyFishProvider:
    def test_configured_when_key_set(self, monkeypatch):
        monkeypatch.setenv("TINYFISH_API_KEY", "tf-key")
        from tools.web_providers.tinyfish import TinyFishProvider

        assert TinyFishProvider().is_configured() is True
        assert TinyFishProvider().provider_name() == "tinyfish"

    def test_not_configured_when_key_missing(self, monkeypatch):
        monkeypatch.delenv("TINYFISH_API_KEY", raising=False)
        from tools.web_providers.tinyfish import TinyFishProvider

        assert TinyFishProvider().is_configured() is False

    def test_implements_search_and_extract_interfaces(self):
        from tools.web_providers.base import WebExtractProvider, WebSearchProvider
        from tools.web_providers.tinyfish import TinyFishProvider

        assert issubclass(TinyFishProvider, WebSearchProvider)
        assert issubclass(TinyFishProvider, WebExtractProvider)


class TestTinyFishSearch:
    @staticmethod
    def _mock_resp(json_data):
        response = MagicMock()
        response.json.return_value = json_data
        response.raise_for_status = MagicMock()
        return response

    def test_search_normalizes_results_and_headers(self, monkeypatch):
        monkeypatch.setenv("TINYFISH_API_KEY", "tf-key")
        monkeypatch.setenv("TINYFISH_SEARCH_LOCATION", "GB")
        monkeypatch.setenv("TINYFISH_SEARCH_LANGUAGE", "en")
        from tools.web_providers.tinyfish import TinyFishProvider

        captured = {}

        def fake_get(url, **kwargs):
            captured.update({"url": url, **kwargs})
            return self._mock_resp({
                "results": [
                    {"position": 1, "site_name": "example.com", "title": "A", "snippet": "Desc", "url": "https://example.com/a"},
                    {"position": 2, "title": "B", "snippet": "Desc B", "url": "https://example.com/b"},
                ],
                "total_results": 2,
            })

        with patch("httpx.get", side_effect=fake_get):
            result = TinyFishProvider().search("agent research", limit=1)

        assert captured["url"] == "https://api.search.tinyfish.ai"
        assert captured["headers"]["X-API-Key"] == "tf-key"
        assert captured["params"] == {"query": "agent research", "location": "GB", "language": "en"}
        assert result == {
            "success": True,
            "data": {"web": [{"title": "A", "url": "https://example.com/a", "description": "Desc", "position": 1, "site_name": "example.com"}]},
        }

    def test_search_http_error_returns_failure(self, monkeypatch):
        import httpx
        monkeypatch.setenv("TINYFISH_API_KEY", "tf-key")
        from tools.web_providers.tinyfish import TinyFishProvider

        bad = MagicMock(status_code=429)
        err = httpx.HTTPStatusError("429", request=MagicMock(), response=bad)
        with patch("httpx.get", side_effect=err):
            result = TinyFishProvider().search("q")

        assert result["success"] is False
        assert "429" in result["error"]


class TestTinyFishFetch:
    @staticmethod
    def _mock_resp(json_data):
        response = MagicMock()
        response.json.return_value = json_data
        response.raise_for_status = MagicMock()
        return response

    def test_extract_normalizes_results_errors_and_headers(self, monkeypatch):
        monkeypatch.setenv("TINYFISH_API_KEY", "tf-key")
        from tools.web_providers.tinyfish import TinyFishProvider

        captured = {}

        def fake_post(url, **kwargs):
            captured.update({"url": url, **kwargs})
            return self._mock_resp({
                "results": [{
                    "url": "https://example.com",
                    "final_url": "https://example.com/",
                    "title": "Example",
                    "description": "Demo",
                    "language": "en",
                    "text": "# Example\nContent",
                    "format": "markdown",
                    "latency_ms": 123,
                }],
                "errors": [{"url": "https://bad.invalid", "error": "fetch_error"}],
            })

        with patch("httpx.post", side_effect=fake_post):
            result = TinyFishProvider().extract(["https://example.com", "https://bad.invalid"], format="markdown")

        assert captured["url"] == "https://api.fetch.tinyfish.ai"
        assert captured["headers"]["X-API-Key"] == "tf-key"
        assert captured["json"] == {"urls": ["https://example.com", "https://bad.invalid"], "format": "markdown"}
        assert result["success"] is True
        assert result["data"][0]["url"] == "https://example.com/"
        assert result["data"][0]["content"] == "# Example\nContent"
        assert result["data"][0]["metadata"]["description"] == "Demo"
        assert result["data"][1]["error"] == "fetch_error"

    def test_extract_converts_json_text_to_string(self, monkeypatch):
        monkeypatch.setenv("TINYFISH_API_KEY", "tf-key")
        from tools.web_providers.tinyfish import TinyFishProvider

        with patch("httpx.post", return_value=self._mock_resp({
            "results": [{"url": "https://example.com", "text": {"type": "document"}}],
            "errors": [],
        })):
            result = TinyFishProvider().extract(["https://example.com"], format="json")

        assert json.loads(result["data"][0]["content"]) == {"type": "document"}


class TestTinyFishBackendWiring:
    def test_backend_available_and_auto_detect(self, monkeypatch):
        from tools import web_tools

        monkeypatch.setattr(web_tools, "_load_web_config", lambda: {})
        monkeypatch.setattr(web_tools, "_is_tool_gateway_ready", lambda: False)
        monkeypatch.setattr(web_tools, "_ddgs_package_importable", lambda: False)
        for key in (
            "FIRECRAWL_API_KEY", "FIRECRAWL_API_URL", "PARALLEL_API_KEY",
            "TAVILY_API_KEY", "EXA_API_KEY", "SEARXNG_URL", "BRAVE_SEARCH_API_KEY",
        ):
            monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv("TINYFISH_API_KEY", "tf-key")

        assert web_tools._is_backend_available("tinyfish") is True
        assert web_tools._get_backend() == "tinyfish"
        assert web_tools.check_web_api_key() is True

    def test_web_search_dispatches_to_tinyfish(self, monkeypatch):
        from tools import web_tools

        monkeypatch.setattr(web_tools, "_get_search_backend", lambda: "tinyfish")
        monkeypatch.setattr("tools.interrupt.is_interrupted", lambda: False, raising=False)
        with patch("tools.web_providers.tinyfish.TinyFishProvider.search", return_value={"success": True, "data": {"web": []}}) as mock_search:
            result = json.loads(web_tools.web_search_tool("docs", limit=3))

        assert result == {"success": True, "data": {"web": []}}
        mock_search.assert_called_once_with("docs", 3)

    def test_web_extract_dispatches_to_tinyfish(self, monkeypatch):
        from tools import web_tools

        monkeypatch.setattr(web_tools, "_get_extract_backend", lambda: "tinyfish")
        monkeypatch.setattr(web_tools, "check_auxiliary_model", lambda: False)
        monkeypatch.setattr("tools.interrupt.is_interrupted", lambda: False, raising=False)
        with patch("tools.web_providers.tinyfish.TinyFishProvider.extract", return_value={
            "success": True,
            "data": [{"url": "https://example.com", "title": "Example", "content": "Text", "raw_content": "Text", "metadata": {}}],
        }) as mock_extract:
            result = json.loads(asyncio.get_event_loop().run_until_complete(web_tools.web_extract_tool(["https://example.com"])))

        assert result["results"][0]["content"] == "Text"
        mock_extract.assert_called_once_with(["https://example.com"], format="markdown")

    def test_web_crawl_returns_tinyfish_no_crawl_error(self, monkeypatch):
        from tools import web_tools

        monkeypatch.setattr(web_tools, "_get_backend", lambda: "tinyfish")
        result = json.loads(asyncio.get_event_loop().run_until_complete(web_tools.web_crawl_tool("https://example.com")))

        assert result["success"] is False
        assert "tinyfish" in result["error"].lower()
        assert "crawl" in result["error"].lower()
