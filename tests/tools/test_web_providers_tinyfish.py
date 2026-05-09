from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from tools import web_tools


class _FakeEntry:
    def __init__(self, *, handler=None, check_fn=None):
        self.handler = handler
        self.check_fn = check_fn


class TestTinyFishBackendWiring:
    def test_is_backend_available_true_when_mcp_tools_present(self, monkeypatch):
        entries = {
            "mcp_tinyfish_search": _FakeEntry(check_fn=lambda: True),
            "mcp_tinyfish_fetch_content": _FakeEntry(check_fn=lambda: True),
        }
        monkeypatch.setattr(web_tools.registry, "get_entry", lambda name: entries.get(name))

        assert web_tools._is_backend_available("tinyfish") is True

    def test_tinyfish_not_available_when_registered_but_disconnected(self, monkeypatch):
        entries = {
            "mcp_tinyfish_search": _FakeEntry(check_fn=lambda: False),
            "mcp_tinyfish_fetch_content": _FakeEntry(check_fn=lambda: False),
        }
        monkeypatch.setattr(web_tools.registry, "get_entry", lambda name: entries.get(name))

        assert web_tools._is_backend_available("tinyfish") is False

    def test_check_web_api_key_true_when_tinyfish_is_configured(self, monkeypatch):
        monkeypatch.setattr(web_tools, "_load_web_config", lambda: {"backend": "tinyfish"})
        monkeypatch.setattr(web_tools, "_is_tinyfish_available", lambda: True)

        assert web_tools.check_web_api_key() is True


class TestTinyFishSearch:
    def test_web_search_tool_normalizes_tinyfish_results(self, monkeypatch):
        monkeypatch.setattr(web_tools, "_get_search_backend", lambda: "tinyfish")
        monkeypatch.setattr("tools.interrupt.is_interrupted", lambda: False, raising=False)

        payload = {
            "results": [
                {
                    "title": "TinyFish docs",
                    "url": "https://docs.tinyfish.ai/",
                    "snippet": "Agent docs",
                    "position": 1,
                    "site_name": "docs.tinyfish.ai",
                }
            ]
        }
        entry = SimpleNamespace(handler=lambda args: json.dumps({"result": json.dumps(payload)}))
        monkeypatch.setattr(web_tools.registry, "get_entry", lambda name: entry if name == "mcp_tinyfish_search" else None)

        result = json.loads(web_tools.web_search_tool("tinyfish", limit=3))

        assert result["success"] is True
        assert result["data"]["web"] == [
            {
                "title": "TinyFish docs",
                "url": "https://docs.tinyfish.ai/",
                "description": "Agent docs",
                "position": 1,
            }
        ]

    def test_web_search_tool_uses_structured_content_when_present(self, monkeypatch):
        monkeypatch.setattr(web_tools, "_get_search_backend", lambda: "tinyfish")
        monkeypatch.setattr("tools.interrupt.is_interrupted", lambda: False, raising=False)

        payload = {
            "results": [
                {
                    "title": "Structured TinyFish docs",
                    "url": "https://docs.tinyfish.ai/structured",
                    "snippet": "Structured payload",
                    "position": 1,
                }
            ]
        }
        entry = SimpleNamespace(handler=lambda args: json.dumps({"result": "OK", "structuredContent": payload}))
        monkeypatch.setattr(web_tools.registry, "get_entry", lambda name: entry if name == "mcp_tinyfish_search" else None)

        result = json.loads(web_tools.web_search_tool("tinyfish", limit=3))

        assert result["success"] is True
        assert result["data"]["web"][0]["title"] == "Structured TinyFish docs"


class TestTinyFishExtract:
    @pytest.mark.asyncio
    async def test_web_extract_tool_normalizes_tinyfish_results(self, monkeypatch):
        monkeypatch.setattr(web_tools, "_get_extract_backend", lambda: "tinyfish")
        monkeypatch.setattr(web_tools, "check_auxiliary_model", lambda: False)
        monkeypatch.setattr(web_tools, "check_website_access", lambda url: None)
        monkeypatch.setattr(web_tools, "is_safe_url", lambda url: True)

        payload = {
            "results": [
                {
                    "url": "https://docs.tinyfish.ai/",
                    "final_url": "https://docs.tinyfish.ai/",
                    "title": "TinyFish Developer Documentation",
                    "text": "Full extracted content",
                }
            ],
            "errors": [],
        }
        entry = SimpleNamespace(handler=lambda args: json.dumps({"result": json.dumps(payload)}))
        monkeypatch.setattr(web_tools.registry, "get_entry", lambda name: entry if name == "mcp_tinyfish_fetch_content" else None)

        result = json.loads(
            await web_tools.web_extract_tool(["https://docs.tinyfish.ai/"], use_llm_processing=False)
        )

        assert result["results"] == [
            {
                "url": "https://docs.tinyfish.ai/",
                "title": "TinyFish Developer Documentation",
                "content": "Full extracted content",
                "error": None,
            }
        ]

    @pytest.mark.asyncio
    async def test_web_extract_tool_uses_structured_content_when_present(self, monkeypatch):
        monkeypatch.setattr(web_tools, "_get_extract_backend", lambda: "tinyfish")
        monkeypatch.setattr(web_tools, "check_auxiliary_model", lambda: False)
        monkeypatch.setattr(web_tools, "check_website_access", lambda url: None)
        monkeypatch.setattr(web_tools, "is_safe_url", lambda url: True)

        payload = {
            "results": [
                {
                    "url": "https://docs.tinyfish.ai/structured",
                    "final_url": "https://docs.tinyfish.ai/structured",
                    "title": "Structured TinyFish Developer Documentation",
                    "text": "Structured extracted content",
                }
            ],
            "errors": [],
        }
        entry = SimpleNamespace(handler=lambda args: json.dumps({"result": "OK", "structuredContent": payload}))
        monkeypatch.setattr(web_tools.registry, "get_entry", lambda name: entry if name == "mcp_tinyfish_fetch_content" else None)

        result = json.loads(
            await web_tools.web_extract_tool(["https://docs.tinyfish.ai/structured"], use_llm_processing=False)
        )

        assert result["results"][0]["title"] == "Structured TinyFish Developer Documentation"
        assert result["results"][0]["content"] == "Structured extracted content"

    @pytest.mark.asyncio
    async def test_web_extract_tool_blocks_redirected_final_url(self, monkeypatch):
        monkeypatch.setattr(web_tools, "_get_extract_backend", lambda: "tinyfish")
        monkeypatch.setattr(web_tools, "check_auxiliary_model", lambda: False)
        monkeypatch.setattr(web_tools, "is_safe_url", lambda url: True)

        def fake_check(url):
            if url == "https://allowed.test":
                return None
            if url == "https://blocked.test/final":
                return {
                    "host": "blocked.test",
                    "rule": "blocked.test",
                    "source": "config",
                    "message": "Blocked by website policy",
                }
            pytest.fail(f"unexpected URL checked: {url}")

        payload = {
            "results": [
                {
                    "url": "https://allowed.test",
                    "final_url": "https://blocked.test/final",
                    "title": "Redirected TinyFish page",
                    "text": "secret content",
                }
            ],
            "errors": [],
        }
        entry = SimpleNamespace(handler=lambda args: json.dumps({"result": json.dumps(payload)}))
        monkeypatch.setattr(web_tools, "check_website_access", fake_check)
        monkeypatch.setattr(web_tools.registry, "get_entry", lambda name: entry if name == "mcp_tinyfish_fetch_content" else None)

        result = json.loads(await web_tools.web_extract_tool(["https://allowed.test"], use_llm_processing=False))

        assert result["results"][0]["url"] == "https://blocked.test/final"
        assert result["results"][0]["content"] == ""
        assert result["results"][0]["blocked_by_policy"]["rule"] == "blocked.test"

    @pytest.mark.asyncio
    async def test_web_extract_tool_short_circuits_blocked_input_url(self, monkeypatch):
        monkeypatch.setattr(web_tools, "_get_extract_backend", lambda: "tinyfish")
        monkeypatch.setattr(web_tools, "check_auxiliary_model", lambda: False)
        monkeypatch.setattr(web_tools, "is_safe_url", lambda url: True)
        monkeypatch.setattr(
            web_tools,
            "check_website_access",
            lambda url: {
                "host": "blocked.test",
                "rule": "blocked.test",
                "source": "config",
                "message": "Blocked by website policy",
            },
        )
        monkeypatch.setattr(
            web_tools.registry,
            "get_entry",
            lambda name: pytest.fail("TinyFish MCP fetch should not be called for blocked URL"),
        )

        result = json.loads(await web_tools.web_extract_tool(["https://blocked.test"], use_llm_processing=False))

        assert result["results"][0]["url"] == "https://blocked.test"
        assert "Blocked by website policy" in result["results"][0]["error"]
