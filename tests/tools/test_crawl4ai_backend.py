"""Tests for the Crawl4AI backend.

Covers:
- Response normalization (dict vs string markdown)
- Error handling (network failures, invalid responses)
- Batch extraction with missing results
"""
from __future__ import annotations

import json
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest


class TestCrawl4AiExtractSingle:
    """crawl4ai_extract_single parses /md responses correctly."""

    def test_successful_single_extraction(self):
        from tools.crawl4ai_backend import crawl4ai_extract_single

        mock_response = {
            "markdown": "# Test Title\n\nSome content here.",
            "success": True,
        }

        with patch("tools.crawl4ai_backend._crawl4ai_request", return_value=mock_response):
            result = crawl4ai_extract_single("https://example.com")

        assert result["success"] is True
        assert result["data"]["markdown"] == "# Test Title\n\nSome content here."
        assert result["data"]["metadata"]["title"] == "Test Title"
        assert result["data"]["metadata"]["sourceURL"] == "https://example.com"

    def test_empty_markdown(self):
        from tools.crawl4ai_backend import crawl4ai_extract_single

        mock_response = {
            "markdown": "",
            "success": True,
        }

        with patch("tools.crawl4ai_backend._crawl4ai_request", return_value=mock_response):
            result = crawl4ai_extract_single("https://example.com")

        assert result["success"] is True
        assert result["data"]["markdown"] == ""
        assert result["data"]["metadata"]["title"] == ""

    def test_request_failure(self):
        from tools.crawl4ai_backend import crawl4ai_extract_single

        with patch(
            "tools.crawl4ai_backend._crawl4ai_request",
            side_effect=Exception("Connection refused"),
        ):
            result = crawl4ai_extract_single("https://example.com")

        assert result["success"] is False
        assert "Connection refused" in result["error"]


class TestCrawl4AiExtractBatch:
    """crawl4ai_extract_batch handles /crawl responses with multiple results."""

    def test_successful_batch_extraction(self):
        from tools.crawl4ai_backend import crawl4ai_extract_batch

        mock_response = {
            "results": [
                {
                    "url": "https://example.com",
                    "success": True,
                    "markdown": {
                        "raw_markdown": "# Example\nContent",
                        "markdown_with_citations": "# Example\nContent [1]",
                    },
                    "metadata": {"title": "Example Page"},
                },
                {
                    "url": "https://test.com",
                    "success": True,
                    "markdown": {
                        "raw_markdown": "# Test\nMore content",
                    },
                    "metadata": {"title": "Test Page"},
                },
            ]
        }

        with patch("tools.crawl4ai_backend._crawl4ai_request", return_value=mock_response):
            results = crawl4ai_extract_batch(["https://example.com", "https://test.com"])

        assert len(results) == 2
        assert results[0]["url"] == "https://example.com"
        assert results[0]["title"] == "Example Page"
        assert results[0]["content"] == "# Example\nContent"
        assert results[1]["url"] == "https://test.com"
        assert results[1]["title"] == "Test Page"

    def test_markdown_as_string(self):
        """Some Crawl4AI versions return markdown as a string instead of dict."""
        from tools.crawl4ai_backend import crawl4ai_extract_batch

        mock_response = {
            "results": [
                {
                    "url": "https://example.com",
                    "success": True,
                    "markdown": "Plain string markdown",
                    "metadata": {"title": "Example"},
                }
            ]
        }

        with patch("tools.crawl4ai_backend._crawl4ai_request", return_value=mock_response):
            results = crawl4ai_extract_batch(["https://example.com"])

        assert results[0]["content"] == "Plain string markdown"

    def test_fallback_to_html(self):
        """When markdown is empty, falls back to cleaned_html or html."""
        from tools.crawl4ai_backend import crawl4ai_extract_batch

        mock_response = {
            "results": [
                {
                    "url": "https://example.com",
                    "success": True,
                    "markdown": {"raw_markdown": "", "markdown_with_citations": ""},
                    "cleaned_html": "<h1>Title</h1><p>Content</p>",
                    "html": "<html><body>Original</body></html>",
                    "metadata": {},
                }
            ]
        }

        with patch("tools.crawl4ai_backend._crawl4ai_request", return_value=mock_response):
            results = crawl4ai_extract_batch(["https://example.com"])

        assert results[0]["content"] == "<h1>Title</h1><p>Content</p>"

    def test_failed_url(self):
        """URLs that fail return error entries."""
        from tools.crawl4ai_backend import crawl4ai_extract_batch

        mock_response = {
            "results": [
                {
                    "url": "https://fail.com",
                    "success": False,
                    "error_message": "Timeout after 30s",
                }
            ]
        }

        with patch("tools.crawl4ai_backend._crawl4ai_request", return_value=mock_response):
            results = crawl4ai_extract_batch(["https://fail.com"])

        assert results[0]["error"] == "Timeout after 30s"
        assert results[0]["content"] == ""

    def test_missing_result(self):
        """URLs not returned in results get error entries."""
        from tools.crawl4ai_backend import crawl4ai_extract_batch

        mock_response = {
            "results": [
                {
                    "url": "https://present.com",
                    "success": True,
                    "markdown": {"raw_markdown": "Content"},
                    "metadata": {"title": "Present"},
                }
                # https://missing.com is not in results
            ]
        }

        with patch("tools.crawl4ai_backend._crawl4ai_request", return_value=mock_response):
            results = crawl4ai_extract_batch(["https://present.com", "https://missing.com"])

        assert len(results) == 2
        assert results[0]["url"] == "https://present.com"
        assert results[1]["url"] == "https://missing.com"
        assert results[1]["error"] == "No response from Crawl4AI"

    def test_batch_request_failure(self):
        """When the entire batch request fails, all URLs get error entries."""
        from tools.crawl4ai_backend import crawl4ai_extract_batch

        with patch(
            "tools.crawl4ai_backend._crawl4ai_request",
            side_effect=Exception("Service unavailable"),
        ):
            results = crawl4ai_extract_batch(["https://a.com", "https://b.com"])

        assert len(results) == 2
        assert results[0]["error"] == "Service unavailable"
        assert results[1]["error"] == "Service unavailable"


class TestCheckCrawl4AiAvailable:
    """check_crawl4ai_available probes the /health endpoint."""

    def test_available(self):
        from tools.crawl4ai_backend import check_crawl4ai_available

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.get", return_value=mock_response):
            assert check_crawl4ai_available() is True

    def test_unavailable(self):
        from tools.crawl4ai_backend import check_crawl4ai_available

        with patch("httpx.get", side_effect=Exception("Connection refused")):
            assert check_crawl4ai_available() is False
