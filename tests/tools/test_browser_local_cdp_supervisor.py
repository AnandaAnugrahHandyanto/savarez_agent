"""Tests for local agent-browser CDP supervisor discovery."""

import json
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def test_browser_navigate_discovers_local_cdp_url_for_supervisor(monkeypatch):
    from tools import browser_tool

    monkeypatch.setattr(browser_tool, "_active_sessions", {})
    monkeypatch.setattr(browser_tool, "_last_active_session_key", {})
    monkeypatch.setattr(browser_tool, "_session_last_activity", {})
    monkeypatch.setattr(browser_tool, "_get_cdp_override", lambda: "")
    monkeypatch.setattr(browser_tool, "_get_cloud_provider", lambda: None)
    monkeypatch.setattr(browser_tool, "_start_browser_cleanup_thread", lambda: None)

    open_response = {
        "success": True,
        "data": {"title": "Example", "url": "https://example.com/"},
    }
    cdp_response = {
        "success": True,
        "data": {"cdpUrl": "ws://127.0.0.1:9222/devtools/browser/local"},
    }
    snapshot_response = {
        "success": True,
        "data": {"snapshot": "- heading Example [ref=e1]", "refs": {"e1": {}}},
    }

    with (
        patch("tools.browser_tool.check_website_access", return_value=None),
        patch("tools.browser_tool._run_browser_command") as run_cmd,
        patch("tools.browser_tool._ensure_cdp_supervisor") as ensure_supervisor,
    ):
        run_cmd.side_effect = [open_response, cdp_response, snapshot_response]
        result = json.loads(browser_tool.browser_navigate("https://example.com/", task_id="qa"))

    assert result["success"] is True
    assert browser_tool._active_sessions["qa"]["cdp_url"] is None
    assert browser_tool._active_sessions["qa"]["supervisor_cdp_url"] == "ws://127.0.0.1:9222/devtools/browser/local"
    assert ensure_supervisor.call_args_list[-1].args == ("qa",)
    assert run_cmd.call_args_list[0].args[:3] == ("qa", "open", ["https://example.com/"])
    assert run_cmd.call_args_list[1].args[:3] == ("qa", "get", ["cdp-url"])
    assert run_cmd.call_args_list[2].args[:3] == ("qa", "snapshot", ["-c"])


def test_discover_local_supervisor_cdp_url_ignores_cloud_sessions(monkeypatch):
    from tools import browser_tool

    monkeypatch.setattr(
        browser_tool,
        "_active_sessions",
        {"qa": {"session_name": "remote", "cdp_url": "ws://remote/devtools/browser/1", "features": {"local": False}}},
    )

    with patch("tools.browser_tool._run_browser_command") as run_cmd:
        assert browser_tool._discover_local_supervisor_cdp_url("qa") == "ws://remote/devtools/browser/1"

    run_cmd.assert_not_called()


def test_discover_local_supervisor_cdp_url_rejects_unusable_output(monkeypatch):
    from tools import browser_tool

    monkeypatch.setattr(
        browser_tool,
        "_active_sessions",
        {"qa": {"session_name": "local", "cdp_url": None, "features": {"local": True}}},
    )

    with patch(
        "tools.browser_tool._run_browser_command",
        return_value={"success": True, "data": {"cdpUrl": "http://127.0.0.1:9222"}},
    ):
        assert browser_tool._discover_local_supervisor_cdp_url("qa") is None

    assert "supervisor_cdp_url" not in browser_tool._active_sessions["qa"]
