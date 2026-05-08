"""Tests for TinyFish web backend integration."""

import asyncio
import json
import os
from unittest.mock import MagicMock, patch

import pytest


class TestTinyFishAuth:
    def test_raises_without_api_key(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TINYFISH_API_KEY", None)
            from tools.web_tools import _tinyfish_search

            with pytest.raises(ValueError, match="TINYFISH_API_KEY"):
                _tinyfish_search("test")


class TestTinyFishSearch:
    def test_search_normalises_results(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "query": "web automation tools",
            "results": [
                {
                    "position": 1,
                    "site_name": "tinyfish.ai",
                    "title": "TinyFish",
                    "snippet": "Agent-ready web tools",
                    "url": "https://tinyfish.ai",
                }
            ],
            "total_results": 1,
        }
        mock_response.raise_for_status = MagicMock()

        with patch.dict(os.environ, {"TINYFISH_API_KEY": "tf-test"}), \
             patch("tools.web_tools.httpx.get", return_value=mock_response) as mock_get:
            from tools.web_tools import _tinyfish_search

            result = _tinyfish_search("web automation tools", limit=5)

            assert result["success"] is True
            assert result["data"]["web"][0]["title"] == "TinyFish"
            assert result["data"]["web"][0]["description"] == "Agent-ready web tools"
            assert result["data"]["web"][0]["url"] == "https://tinyfish.ai"
            headers = mock_get.call_args.kwargs["headers"]
            assert headers["X-API-Key"] == "tf-test"

    def test_web_search_dispatches_to_tinyfish(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [{"title": "Result", "url": "https://r.com", "snippet": "desc"}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("tools.web_tools._get_search_backend", return_value="tinyfish"), \
             patch.dict(os.environ, {"TINYFISH_API_KEY": "tf-test"}), \
             patch("tools.web_tools.httpx.get", return_value=mock_response), \
             patch("tools.interrupt.is_interrupted", return_value=False):
            from tools.web_tools import web_search_tool

            result = json.loads(web_search_tool("test query", limit=3))
            assert result["success"] is True
            assert result["data"]["web"][0]["title"] == "Result"


class TestTinyFishExtract:
    def test_extract_normalises_results_and_errors(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {
                    "url": "https://example.com",
                    "final_url": "https://example.com/final",
                    "title": "Example",
                    "description": "Example page",
                    "language": "en",
                    "text": "# Example\n\nContent",
                }
            ],
            "errors": [{"url": "https://bad.example", "error": "timeout"}],
        }
        mock_response.raise_for_status = MagicMock()

        with patch.dict(os.environ, {"TINYFISH_API_KEY": "tf-test"}), \
             patch("tools.web_tools.httpx.post", return_value=mock_response) as mock_post:
            from tools.web_tools import _tinyfish_extract

            docs = _tinyfish_extract(["https://example.com", "https://bad.example"], format="markdown")

            assert docs[0]["url"] == "https://example.com/final"
            assert docs[0]["title"] == "Example"
            assert docs[0]["content"] == "# Example\n\nContent"
            assert docs[1]["url"] == "https://bad.example"
            assert docs[1]["error"] == "timeout"
            headers = mock_post.call_args.kwargs["headers"]
            assert headers["X-API-Key"] == "tf-test"
            assert mock_post.call_args.kwargs["json"]["format"] == "markdown"

    def test_web_extract_dispatches_to_tinyfish(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [{"url": "https://example.com", "title": "Page", "text": "Extracted content"}],
            "errors": [],
        }
        mock_response.raise_for_status = MagicMock()

        with patch("tools.web_tools._get_extract_backend", return_value="tinyfish"), \
             patch.dict(os.environ, {"TINYFISH_API_KEY": "tf-test"}), \
             patch("tools.web_tools.httpx.post", return_value=mock_response), \
             patch("tools.web_tools.check_auxiliary_model", return_value=False):
            from tools.web_tools import web_extract_tool

            result = json.loads(asyncio.get_event_loop().run_until_complete(
                web_extract_tool(["https://example.com"], use_llm_processing=False)
            ))
            assert result["results"][0]["url"] == "https://example.com"
            assert result["results"][0]["content"] == "Extracted content"
