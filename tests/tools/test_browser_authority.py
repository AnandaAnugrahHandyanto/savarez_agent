import importlib
import json

import pytest

from tools.browser_authority import (
    BrowserAuthorityError,
    clear_browser_authority,
    normalize_browser_authority,
    require_browser_capability,
    set_browser_authority,
)


def test_normalize_browser_authority_remote_payload():
    authority = normalize_browser_authority({
        "source": "remote",
        "owner_id": "user-123",
        "owner_type": "api_key",
        "capabilities": ["read", "interact", "metadata"],
        "session_id": "sess-1",
    })

    assert authority.remote is True
    assert authority.owner_key == "remote:api_key:user-123"
    assert authority.has("read") is True
    assert authority.has("interact") is True
    assert authority.has("admin") is False


def test_require_browser_capability_blocks_remote_interaction_without_scope():
    token = set_browser_authority({
        "source": "remote",
        "owner_id": "reader",
        "capabilities": ["read"],
    })
    try:
        with pytest.raises(BrowserAuthorityError):
            require_browser_capability("click")
    finally:
        clear_browser_authority(token)


def test_get_session_info_persists_metadata_and_enforces_owner(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    import tools.browser_tool as browser_tool

    browser_tool = importlib.reload(browser_tool)
    monkeypatch.setattr(browser_tool, "_start_browser_cleanup_thread", lambda: None)
    monkeypatch.setattr(browser_tool, "_update_session_activity", lambda task_id: None)
    monkeypatch.setattr(browser_tool, "_get_cdp_override", lambda: "")
    monkeypatch.setattr(browser_tool, "_get_cloud_provider", lambda: None)
    browser_tool._active_sessions.clear()
    browser_tool._session_last_activity.clear()

    token = set_browser_authority({
        "source": "remote",
        "owner_id": "owner-a",
        "capabilities": ["read", "interact", "metadata"],
        "session_id": "sess-a",
    })
    try:
        session_info = browser_tool._get_session_info("shared-task")
    finally:
        clear_browser_authority(token)

    metadata = json.loads(open(session_info["metadata_path"], encoding="utf-8").read())
    assert metadata["authority"]["owner_id"] == "owner-a"
    assert metadata["owner_key"] == session_info["owner_key"]
    assert open(session_info["audit_log_path"], encoding="utf-8").read().strip()

    token = set_browser_authority({
        "source": "remote",
        "owner_id": "owner-b",
        "capabilities": ["read", "interact", "metadata"],
    })
    try:
        with pytest.raises(BrowserAuthorityError):
            browser_tool._get_session_info("shared-task")
    finally:
        clear_browser_authority(token)


def test_browser_navigate_local_flow_still_succeeds(monkeypatch):
    import tools.browser_tool as browser_tool

    session_info = {
        "session_name": "local-session",
        "owner_key": "local:session:local",
        "features": {"local": True},
    }

    monkeypatch.setattr(browser_tool, "_is_local_backend", lambda: True)
    monkeypatch.setattr(browser_tool, "_is_safe_url", lambda url: True)
    monkeypatch.setattr(browser_tool, "check_website_access", lambda url: None)
    monkeypatch.setattr(browser_tool, "_is_camofox_mode", lambda: False)
    monkeypatch.setattr(browser_tool, "_get_session_info", lambda task_id: session_info)
    monkeypatch.setattr(browser_tool, "_get_command_timeout", lambda: 30)
    monkeypatch.setattr(browser_tool, "_maybe_start_recording", lambda task_id: None)

    def fake_run(task_id, command, args=None, timeout=None):
        if command == "open":
            return {"success": True, "data": {"title": "Example", "url": "https://example.com"}}
        if command == "snapshot":
            return {"success": True, "data": {"snapshot": "hello", "refs": {"@e1": {}}}}
        raise AssertionError(command)

    monkeypatch.setattr(browser_tool, "_run_browser_command", fake_run)

    result = json.loads(browser_tool.browser_navigate("https://example.com", task_id="task-local"))
    assert result["success"] is True
    assert result["url"] == "https://example.com"
    assert result["browser_session"]["session_name"] == "local-session"
