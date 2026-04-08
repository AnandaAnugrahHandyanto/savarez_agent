"""Tests for the dedicated Brave Search tool.

Coverage:
  check_brave_api_key() — API key availability detection.
  _brave_request() — auth header handling and HTTP request shape.
  _normalize_brave_search_results() — Brave response normalization.
  brave_search_tool() — end-to-end dispatch.
  registry/toolset wiring — brave_search is exposed through enabled Hermes toolsets.
"""

import json
import os
from unittest.mock import MagicMock, patch

import pytest


class TestCheckBraveApiKey:
    def test_false_when_missing(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("BRAVE_API_KEY", None)
            from tools.web_tools import check_brave_api_key

            assert check_brave_api_key() is False

    def test_true_when_present(self):
        with patch.dict(os.environ, {"BRAVE_API_KEY": "brv-test"}, clear=False):
            from tools.web_tools import check_brave_api_key

            assert check_brave_api_key() is True


class TestBraveRequest:
    def test_raises_without_api_key(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("BRAVE_API_KEY", None)
            from tools.web_tools import _brave_request

            with pytest.raises(ValueError, match="BRAVE_API_KEY"):
                _brave_request("test", count=3)

    def test_sends_subscription_token_header(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"web": {"results": []}}
        mock_response.raise_for_status = MagicMock()

        with patch.dict(os.environ, {"BRAVE_API_KEY": "brv-test-key"}, clear=False):
            with patch("tools.web_tools.httpx.get", return_value=mock_response) as mock_get:
                from tools.web_tools import _brave_request

                result = _brave_request("hello world", count=7)

                assert result == {"web": {"results": []}}
                mock_get.assert_called_once()
                _, kwargs = mock_get.call_args
                assert kwargs["headers"]["X-Subscription-Token"] == "brv-test-key"
                assert kwargs["headers"]["Accept"] == "application/json"
                assert kwargs["params"]["q"] == "hello world"
                assert kwargs["params"]["count"] == 7
                assert kwargs["timeout"] == 30


class TestNormalizeBraveSearchResults:
    def test_basic_normalization(self):
        from tools.web_tools import _normalize_brave_search_results

        raw = {
            "web": {
                "results": [
                    {
                        "title": "Python Docs",
                        "url": "https://docs.python.org",
                        "description": "Official Python documentation",
                    },
                    {
                        "title": "Example",
                        "url": "https://example.com",
                        "description": "Example site",
                    },
                ]
            }
        }

        result = _normalize_brave_search_results(raw)

        assert result["success"] is True
        web = result["data"]["web"]
        assert len(web) == 2
        assert web[0] == {
            "title": "Python Docs",
            "url": "https://docs.python.org",
            "description": "Official Python documentation",
            "position": 1,
        }
        assert web[1]["position"] == 2

    def test_missing_fields_become_empty_strings(self):
        from tools.web_tools import _normalize_brave_search_results

        result = _normalize_brave_search_results({"web": {"results": [{}]}})

        assert result["data"]["web"][0] == {
            "title": "",
            "url": "",
            "description": "",
            "position": 1,
        }


class TestBraveSearchTool:
    def test_dispatches_to_brave_api(self):
        with patch("tools.web_tools._brave_request", return_value={
            "web": {
                "results": [
                    {"title": "Result", "url": "https://r.com", "description": "desc"}
                ]
            }
        }), patch("tools.interrupt.is_interrupted", return_value=False):
            from tools.web_tools import brave_search_tool

            result = json.loads(brave_search_tool("test query", count=4))

            assert result["success"] is True
            assert result["data"]["web"][0]["title"] == "Result"
            assert result["data"]["web"][0]["position"] == 1


class TestRegistryAndToolsets:
    def test_brave_search_registered(self):
        from tools.registry import registry

        entry = registry._tools["brave_search"]
        assert entry.toolset == "web"
        assert entry.requires_env == ["BRAVE_API_KEY"]
        assert entry.check_fn is not None

    def test_web_toolset_and_core_toolset_include_brave_search(self):
        from toolsets import resolve_toolset

        assert "brave_search" in resolve_toolset("web")
        assert "brave_search" in resolve_toolset("hermes-cli")
        assert "brave_search" in resolve_toolset("hermes-acp")
        assert "brave_search" in resolve_toolset("hermes-api-server")
