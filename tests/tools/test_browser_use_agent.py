import json
from unittest.mock import patch

import pytest


class _Response:
    def __init__(self, payload, *, status_code=200, text="", headers=None):
        self._payload = payload
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self.text = text
        self.headers = headers or {}

    def json(self):
        return self._payload


def test_browser_use_agent_posts_task_and_polls_until_success(monkeypatch):
    from plugins.browser.browser_use.provider import BrowserUseBrowserProvider

    monkeypatch.setenv("BROWSER_USE_API_KEY", "direct-key")
    monkeypatch.delenv("TOOL_GATEWAY_USER_TOKEN", raising=False)
    monkeypatch.delenv("BROWSER_USE_GATEWAY_URL", raising=False)
    monkeypatch.setattr("tools.tool_backend_helpers.prefers_gateway", lambda _tool: False)

    post_response = _Response({"id": "session-1", "status": "running"})
    poll_response = _Response({
        "id": "session-1",
        "status": "idle",
        "output": "Found the invoice total.",
        "isTaskSuccessful": True,
        "liveUrl": "https://browser-use.example/live/session-1",
        "recordingUrls": ["https://browser-use.example/recording/session-1.mp4"],
    })

    with (
        patch("plugins.browser.browser_use.provider.requests.post", return_value=post_response) as post,
        patch("plugins.browser.browser_use.provider.requests.get", return_value=poll_response) as get,
        patch("plugins.browser.browser_use.provider.time.sleep") as sleep,
    ):
        result = BrowserUseBrowserProvider().run_agent_task(
            "Find the invoice total",
            task_id="task-1",
            poll_interval_seconds=0.1,
            timeout_seconds=5,
        )

    assert result["session_id"] == "session-1"
    assert result["status"] == "idle"
    assert result["output"] == "Found the invoice total."
    assert result["is_task_successful"] is True
    assert result["live_url"] == "https://browser-use.example/live/session-1"
    assert result["recording_urls"] == ["https://browser-use.example/recording/session-1.mp4"]
    post.assert_called_once()
    assert post.call_args.args[0] == "https://api.browser-use.com/api/v3/sessions"
    assert post.call_args.kwargs["headers"] == {
        "Content-Type": "application/json",
        "X-Browser-Use-API-Key": "direct-key",
    }
    assert post.call_args.kwargs["json"] == {"task": "Find the invoice total"}
    get.assert_called_once_with(
        "https://api.browser-use.com/api/v3/sessions/session-1",
        headers={
            "Content-Type": "application/json",
            "X-Browser-Use-API-Key": "direct-key",
        },
        timeout=30,
    )
    sleep.assert_called_once_with(0.1)


def test_browser_use_agent_uses_managed_gateway_auth(monkeypatch):
    from plugins.browser.browser_use.provider import BrowserUseBrowserProvider

    monkeypatch.delenv("BROWSER_USE_API_KEY", raising=False)
    monkeypatch.setenv("TOOL_GATEWAY_USER_TOKEN", "nous-token")
    monkeypatch.setenv("BROWSER_USE_GATEWAY_URL", "http://127.0.0.1:3009/")
    monkeypatch.setattr(
        "tools.managed_tool_gateway.managed_nous_tools_enabled",
        lambda: True,
    )

    post_response = _Response({"id": "session-2", "status": "stopped", "output": "Done"})

    with patch("plugins.browser.browser_use.provider.requests.post", return_value=post_response) as post:
        result = BrowserUseBrowserProvider().run_agent_task("Summarize the page", task_id="abc123")

    assert result["status"] == "stopped"
    assert result["output"] == "Done"
    assert post.call_args.args[0] == "http://127.0.0.1:3009/sessions"
    headers = post.call_args.kwargs["headers"]
    assert headers["X-Browser-Use-API-Key"] == "nous-token"
    assert headers["X-Idempotency-Key"].startswith("browser-use-agent-task:")


def test_browser_use_agent_terminal_failure_raises(monkeypatch):
    from plugins.browser.browser_use.provider import BrowserUseBrowserProvider

    monkeypatch.setenv("BROWSER_USE_API_KEY", "direct-key")
    monkeypatch.setattr("tools.tool_backend_helpers.prefers_gateway", lambda _tool: False)

    post_response = _Response({"id": "session-3", "status": "running"})
    poll_response = _Response({
        "id": "session-3",
        "status": "error",
        "error": "Navigation failed",
        "output": "Partial output",
    })

    with (
        patch("plugins.browser.browser_use.provider.requests.post", return_value=post_response),
        patch("plugins.browser.browser_use.provider.requests.get", return_value=poll_response),
        patch("plugins.browser.browser_use.provider.time.sleep"),
    ):
        with pytest.raises(RuntimeError, match="Navigation failed"):
            BrowserUseBrowserProvider().run_agent_task("Open a broken URL", timeout_seconds=5)


def test_browser_use_agent_unsuccessful_stopped_session_raises(monkeypatch):
    from plugins.browser.browser_use.provider import BrowserUseBrowserProvider

    monkeypatch.setenv("BROWSER_USE_API_KEY", "direct-key")
    monkeypatch.setattr("tools.tool_backend_helpers.prefers_gateway", lambda _tool: False)

    post_response = _Response({
        "id": "session-4",
        "status": "stopped",
        "output": "I could not find the requested account.",
        "isTaskSuccessful": False,
    })

    with patch("plugins.browser.browser_use.provider.requests.post", return_value=post_response):
        with pytest.raises(RuntimeError, match="could not find"):
            BrowserUseBrowserProvider().run_agent_task("Find a missing account")


def test_browser_use_agent_auth_availability(monkeypatch):
    from tools import browser_tool

    monkeypatch.setattr(
        browser_tool.BrowserUseProvider,
        "is_configured",
        lambda _self: False,
    )
    assert browser_tool.check_browser_use_agent_requirements() is False

    monkeypatch.setattr(
        browser_tool.BrowserUseProvider,
        "is_configured",
        lambda _self: True,
    )
    assert browser_tool.check_browser_use_agent_requirements() is True


def test_browser_use_agent_tool_returns_json(monkeypatch):
    from tools.browser_tool import browser_use_agent

    class _Provider:
        def run_agent_task(self, task, *, task_id=None, timeout_seconds=600):
            return {
                "session_id": "session-tool",
                "status": "idle",
                "output": f"done: {task}",
            }

    monkeypatch.setattr("tools.browser_tool.BrowserUseProvider", _Provider)

    result = json.loads(browser_use_agent("Check the dashboard", task_id="task-tool"))

    assert result == {
        "success": True,
        "session_id": "session-tool",
        "status": "idle",
        "output": "done: Check the dashboard",
    }


def test_browser_use_agent_registration_and_schema():
    from model_tools import _LEGACY_TOOLSET_MAP
    from toolsets import TOOLSETS, _HERMES_CORE_TOOLS
    from tools.browser_tool import BROWSER_TOOL_SCHEMAS
    from tools.registry import registry
    from tools import browser_tool  # noqa: F401

    schema = next(s for s in BROWSER_TOOL_SCHEMAS if s["name"] == "browser_use_agent")
    assert schema["parameters"]["required"] == ["task"]
    assert "timeout_seconds" in schema["parameters"]["properties"]
    assert "browser_use_agent" in TOOLSETS["browser"]["tools"]
    assert "browser_use_agent" in _HERMES_CORE_TOOLS
    assert "browser_use_agent" in _LEGACY_TOOLSET_MAP["browser_tools"]
    assert "browser_use_agent" in registry._tools
