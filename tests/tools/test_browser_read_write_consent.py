"""Browser read/write contract, action broker execution, and session consent."""

from __future__ import annotations

import json

import pytest


@pytest.fixture(autouse=True)
def clean_browser_runtime():
    from tools import browser_runtime

    browser_runtime.BROWSER_SESSION_CONSENTS.clear()
    yield
    browser_runtime.BROWSER_SESSION_CONSENTS.clear()


def test_browser_session_api_inspects_grants_and_revokes_write_consent():
    from tools.browser_tool import browser_session

    initial = json.loads(browser_session(action="status", task_id="s1"))
    assert initial["success"] is True
    assert initial["consent"]["write"] is False

    granted = json.loads(browser_session(action="grant", task_id="s1", reason="QA run"))
    assert granted["success"] is True
    assert granted["consent"]["write"] is True
    assert granted["consent"]["reason"] == "QA run"

    revoked = json.loads(browser_session(action="revoke", task_id="s1"))
    assert revoked["success"] is True
    assert revoked["consent"]["write"] is False


def test_browser_write_is_blocked_until_session_consent_is_granted(monkeypatch):
    from tools.browser_tool import browser_session, browser_write
    from tools import browser_runtime

    calls = []

    def fake_execute(self, request):
        calls.append(request)
        return {"success": True, "action": request.action}

    monkeypatch.setattr(browser_runtime.ActionBroker, "execute", fake_execute)

    blocked = json.loads(
        browser_write(action="click", parameters={"ref": "@e1"}, task_id="session-a")
    )
    assert blocked["success"] is False
    assert blocked["error_code"] == "browser_session_consent_required"
    assert calls == []

    browser_session(action="grant", task_id="session-a")
    allowed = json.loads(
        browser_write(action="click", parameters={"ref": "@e1"}, task_id="session-a")
    )
    assert allowed == {"success": True, "action": "click"}
    assert calls[0].kind == "write"
    assert calls[0].action == "click"


def test_browser_read_executes_through_action_broker_without_write_consent(monkeypatch):
    from tools.browser_tool import browser_read
    from tools import browser_runtime

    calls = []

    def fake_execute(self, request):
        calls.append(request)
        return {"success": True, "snapshot": "ok"}

    monkeypatch.setattr(browser_runtime.ActionBroker, "execute", fake_execute)

    result = json.loads(browser_read(action="snapshot", parameters={"full": True}, task_id="r1"))

    assert result == {"success": True, "snapshot": "ok"}
    assert calls[0].kind == "read"
    assert calls[0].action == "snapshot"
    assert calls[0].parameters == {"full": True}


def test_browser_read_console_rejects_javascript_expression(monkeypatch):
    from tools.browser_tool import browser_read
    from tools import browser_runtime

    calls = []

    def fake_console(*_args, **_kwargs):
        calls.append((_args, _kwargs))
        return json.dumps({"success": True})

    import tools.browser_tool as bt
    monkeypatch.setattr(bt, "browser_console", fake_console)

    result = json.loads(browser_read(action="console", parameters={"expression": "document.body.click()"}, task_id="r2"))

    assert result["success"] is False
    assert result["error_code"] == "browser_read_expression_forbidden"
    assert calls == []


def test_browser_runtime_broker_dispatches_to_live_browser_operations(monkeypatch):
    from tools.browser_runtime import ActionBroker, BrowserActionRequest
    import tools.browser_tool as bt

    monkeypatch.setattr(bt, "browser_click", lambda ref, task_id=None: json.dumps({"clicked": ref, "task_id": task_id}))

    result = ActionBroker().execute(
        BrowserActionRequest(kind="write", action="click", parameters={"ref": "@e7"}, task_id="live")
    )

    assert result == {"clicked": "@e7", "task_id": "live"}
