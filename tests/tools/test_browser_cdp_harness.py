"""Unit tests for read-only CDP harness tool."""
from __future__ import annotations

import asyncio
import json
import threading
from typing import Any, Dict, List

import importlib

import pytest
import websockets
from websockets.asyncio.server import serve


class _CDPServer:
    def __init__(self) -> None:
        self._handlers: Dict[str, Any] = {}
        self._received: List[Dict[str, Any]] = []
        self._loop: asyncio.AbstractEventLoop | None = None
        self._server: Any = None
        self._thread: threading.Thread | None = None
        self._host = "127.0.0.1"
        self._port = 0

    def on(self, method: str, handler):
        self._handlers[method] = handler

    def start(self) -> str:
        ready = threading.Event()

        def _run() -> None:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

            async def _handler(ws):
                try:
                    async for raw in ws:
                        msg = json.loads(raw)
                        self._received.append(msg)
                        method = msg.get("method", "")
                        call_id = msg.get("id")
                        session_id = msg.get("sessionId")
                        fn = self._handlers.get(method)
                        if fn is None:
                            reply = {
                                "id": call_id,
                                "error": {"code": -32601, "message": f"No handler for {method}"},
                            }
                        else:
                            result = fn(msg.get("params", {}) or {}, session_id)
                            reply = {"id": call_id, "result": result}
                        if session_id:
                            reply["sessionId"] = session_id
                        await ws.send(json.dumps(reply))
                except websockets.exceptions.ConnectionClosed:
                    pass

            async def _serve() -> None:
                self._server = await serve(_handler, self._host, 0)
                sock = next(iter(self._server.sockets))
                self._port = sock.getsockname()[1]
                ready.set()
                await self._server.wait_closed()

            try:
                self._loop.run_until_complete(_serve())
            finally:
                self._loop.close()

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()
        if not ready.wait(timeout=5.0):
            raise RuntimeError("CDP mock server failed to start")
        return f"ws://{self._host}:{self._port}/devtools/browser/mock"

    def stop(self) -> None:
        if self._loop and self._server:
            self._loop.call_soon_threadsafe(self._server.close)
        if self._thread:
            self._thread.join(timeout=3.0)

    def received(self) -> List[Dict[str, Any]]:
        return list(self._received)


@pytest.fixture
def cdp_server(monkeypatch):
    browser_cdp_harness = importlib.import_module("tools.browser_cdp_harness")

    server = _CDPServer()
    ws_url = server.start()
    monkeypatch.setattr(browser_cdp_harness, "_resolve_cdp_endpoint", lambda: ws_url)
    try:
        yield server
    finally:
        server.stop()


@pytest.fixture
def browser_cdp_harness_module():
    return importlib.import_module("tools.browser_cdp_harness")


def test_missing_endpoint_returns_clear_error_without_cdp_call(monkeypatch, browser_cdp_harness_module):
    monkeypatch.setattr(browser_cdp_harness_module, "_resolve_cdp_endpoint", lambda: "")

    result = json.loads(browser_cdp_harness_module.browser_cdp_harness(action="list_targets"))

    assert "error" in result
    assert "No CDP endpoint" in result["error"]
    assert "/browser connect" in result["error"]


def test_invalid_endpoint_returns_clear_error_without_cdp_call(monkeypatch, browser_cdp_harness_module):
    monkeypatch.setattr(browser_cdp_harness_module, "_resolve_cdp_endpoint", lambda: "http://127.0.0.1:9222")

    result = json.loads(browser_cdp_harness_module.browser_cdp_harness(action="get_version"))

    assert "error" in result
    assert "not a WebSocket URL" in result["error"]


def test_timeout_is_clamped_before_cdp_call(cdp_server):
    browser_cdp_harness = importlib.import_module("tools.browser_cdp_harness")

    cdp_server.on("Browser.getVersion", lambda params, sid: {"product": "MockChrome"})

    result = json.loads(browser_cdp_harness.browser_cdp_harness(action="get_version", timeout=9999))

    assert result["success"] is True
    assert result["result"]["product"] == "MockChrome"


def test_safe_timeout_bounds_and_invalid_values(browser_cdp_harness_module):
    assert browser_cdp_harness_module._safe_timeout(0) == 1.0
    assert browser_cdp_harness_module._safe_timeout(-10) == 1.0
    assert browser_cdp_harness_module._safe_timeout(9999) == 120.0
    assert browser_cdp_harness_module._safe_timeout("bad") == 30.0


def test_list_targets_uses_read_only_target_method(cdp_server):
    browser_cdp_harness = importlib.import_module("tools.browser_cdp_harness")

    cdp_server.on(
        "Target.getTargets",
        lambda params, sid: {"targetInfos": [{"targetId": "tab-1", "type": "page", "url": "https://example.test"}]},
    )

    result = json.loads(browser_cdp_harness.browser_cdp_harness(action="list_targets"))

    assert result["success"] is True
    assert result["action"] == "list_targets"
    assert result["result"]["targetInfos"][0]["targetId"] == "tab-1"
    assert [call["method"] for call in cdp_server.received()] == ["Target.getTargets"]


def test_evaluate_sets_throw_on_side_effect_and_attaches_to_target(cdp_server):
    browser_cdp_harness = importlib.import_module("tools.browser_cdp_harness")

    cdp_server.on("Target.attachToTarget", lambda params, sid: {"sessionId": f"sess-{params['targetId']}"})
    cdp_server.on(
        "Runtime.evaluate",
        lambda params, sid: {"result": {"type": "string", "value": "Example"}},
    )

    result = json.loads(
        browser_cdp_harness.browser_cdp_harness(
            action="evaluate",
            target_id="tab-1",
            expression="document.title",
        )
    )

    assert result["success"] is True
    assert result["result"]["result"]["value"] == "Example"
    calls = cdp_server.received()
    assert calls[0]["method"] == "Target.attachToTarget"
    assert calls[1]["method"] == "Runtime.evaluate"
    assert calls[1]["sessionId"] == "sess-tab-1"
    assert calls[1]["params"]["expression"] == "document.title"
    assert calls[1]["params"]["returnByValue"] is True
    assert calls[1]["params"]["throwOnSideEffect"] is True


def test_evaluate_can_select_target_by_url_or_title(cdp_server):
    browser_cdp_harness = importlib.import_module("tools.browser_cdp_harness")

    cdp_server.on(
        "Target.getTargets",
        lambda params, sid: {
            "targetInfos": [
                {
                    "targetId": "tab-1",
                    "type": "page",
                    "url": "https://example.test/home",
                    "title": "Home",
                },
                {
                    "targetId": "tab-2",
                    "type": "page",
                    "url": "https://example.test/dashboard",
                    "title": "Dashboard",
                },
            ]
        },
    )
    cdp_server.on("Target.attachToTarget", lambda params, sid: {"sessionId": f"sess-{params['targetId']}"})
    cdp_server.on(
        "Runtime.evaluate",
        lambda params, sid: {"result": {"type": "string", "value": "Dashboard"}},
    )

    result = json.loads(
        browser_cdp_harness.browser_cdp_harness(
            action="evaluate",
            target_url="/dashboard",
            expression="document.title",
        )
    )

    assert result["success"] is True
    assert result["target_id"] == "tab-2"
    calls = cdp_server.received()
    assert [call["method"] for call in calls] == [
        "Target.getTargets",
        "Target.attachToTarget",
        "Runtime.evaluate",
    ]
    assert calls[1]["params"]["targetId"] == "tab-2"


def test_ambiguous_target_selector_returns_error_without_evaluate(cdp_server):
    browser_cdp_harness = importlib.import_module("tools.browser_cdp_harness")

    cdp_server.on(
        "Target.getTargets",
        lambda params, sid: {
            "targetInfos": [
                {"targetId": "tab-1", "type": "page", "url": "https://a.test/app", "title": "App"},
                {"targetId": "tab-2", "type": "page", "url": "https://b.test/app", "title": "App"},
            ]
        },
    )
    cdp_server.on("Runtime.evaluate", lambda params, sid: {"result": {"value": "should-not-run"}})

    result = json.loads(
        browser_cdp_harness.browser_cdp_harness(
            action="evaluate",
            target_title="App",
            expression="document.title",
        )
    )

    assert "error" in result
    assert "matched multiple" in result["error"]
    assert [call["method"] for call in cdp_server.received()] == ["Target.getTargets"]


def test_evaluate_rejects_obvious_mutating_expressions_without_cdp_call(cdp_server):
    browser_cdp_harness = importlib.import_module("tools.browser_cdp_harness")

    result = json.loads(
        browser_cdp_harness.browser_cdp_harness(
            action="evaluate",
            target_id="tab-1",
            expression="document.body.innerHTML = 'owned'",
        )
    )

    assert "error" in result
    assert "mutating" in result["error"]
    assert cdp_server.received() == []


def test_mutating_or_unknown_action_is_rejected_without_cdp_call(cdp_server):
    browser_cdp_harness = importlib.import_module("tools.browser_cdp_harness")

    result = json.loads(browser_cdp_harness.browser_cdp_harness(action="Page.navigate"))

    assert "error" in result
    assert "Unsupported" in result["error"]
    assert cdp_server.received() == []


def test_registered_and_in_browser_toolset():
    import toolsets
    from tools.registry import registry
    import tools.browser_cdp_harness  # noqa: F401 - trigger module registration

    entry = registry.get_entry("browser_cdp_harness")
    assert entry is not None
    assert entry.toolset == "browser-cdp-harness"
    assert entry.schema["name"] == "browser_cdp_harness"
    assert "browser_cdp_harness" in toolsets.TOOLSETS["browser"]["tools"]
