"""Tests for deterministic webhook handler routes.

Deterministic handlers are operator-configured webhook routes that receive the
exact raw request bytes and return an HTTP response without prompt rendering,
direct delivery, or agent execution.
"""

import hashlib
import hmac
import json
import logging
import sys
import types

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from gateway.config import PlatformConfig
from gateway.platforms.webhook import WebhookAdapter, _DYNAMIC_ROUTES_FILENAME, _INSECURE_NO_AUTH


def _make_adapter(routes, **extra_kw) -> WebhookAdapter:
    extra = {"host": "0.0.0.0", "port": 0, "routes": routes}
    extra.update(extra_kw)
    config = PlatformConfig(enabled=True, extra=extra)
    return WebhookAdapter(config)


def _create_app(adapter: WebhookAdapter) -> web.Application:
    app = web.Application()
    app.router.add_get("/health", adapter._handle_health)
    app.router.add_post("/webhooks/{route_name}", adapter._handle_webhook)
    return app


def _install_handler_module(monkeypatch, name="webhook_test_handlers", **handlers):
    module = types.ModuleType(name)
    for attr, value in handlers.items():
        setattr(module, attr, value)
    monkeypatch.setitem(sys.modules, name, module)
    return name


@pytest.mark.asyncio
async def test_deterministic_handler_receives_exact_raw_body_without_agent_or_parse(monkeypatch):
    calls = []

    def handle(**kwargs):
        calls.append(kwargs)
        return {
            "status_code": 202,
            "body": {
                "status": "handled",
                "raw_body_text": kwargs["raw_body"].decode("latin1"),
                "config": kwargs["config"],
                "secret": kwargs["webhook_secret"],
            },
        }

    module_name = _install_handler_module(monkeypatch, handle=handle)
    routes = {
        "deterministic": {
            "secret": _INSECURE_NO_AUTH,
            "deterministic_handler": {
                "import": f"{module_name}:handle",
                "config": {"mode": "repo-local"},
            },
        }
    }
    adapter = _make_adapter(routes)
    handled_events = []

    async def _capture(event):
        handled_events.append(event)

    adapter.handle_message = _capture
    raw_body = b"not-json=and-not-form-\xff&keep=exact"

    async with TestClient(TestServer(_create_app(adapter))) as cli:
        resp = await cli.post(
            "/webhooks/deterministic",
            data=raw_body,
            headers={"X-GitHub-Delivery": "det-1"},
        )
        assert resp.status == 202
        data = await resp.json()

    assert data == {
        "status": "handled",
        "raw_body_text": "not-json=and-not-form-ÿ&keep=exact",
        "config": {"mode": "repo-local"},
        "secret": None,
    }
    assert handled_events == []
    assert len(calls) == 1
    assert calls[0]["method"] == "POST"
    assert calls[0]["path"] == "/webhooks/deterministic"
    assert calls[0]["route_name"] == "deterministic"
    assert calls[0]["raw_body"] == raw_body
    assert calls[0]["headers"]["X-GitHub-Delivery"] == "det-1"
    assert isinstance(calls[0]["now"], str)


@pytest.mark.asyncio
async def test_deterministic_handler_gets_route_secret_after_gateway_hmac(monkeypatch):
    calls = []

    def handle(**kwargs):
        calls.append(kwargs)
        return {"status_code": 200, "body": {"status": "ok"}}

    module_name = _install_handler_module(monkeypatch, handle=handle)
    routes = {
        "deterministic": {
            "secret": "route-secret",
            "deterministic_handler": {"import": f"{module_name}:handle"},
        }
    }
    adapter = _make_adapter(routes)
    raw_body = json.dumps({"ok": True}).encode()
    valid_sig = "sha256=" + hmac.new(b"route-secret", raw_body, hashlib.sha256).hexdigest()

    async with TestClient(TestServer(_create_app(adapter))) as cli:
        resp = await cli.post(
            "/webhooks/deterministic",
            data=raw_body,
            headers={"X-GitHub-Delivery": "missing-signature"},
        )
        assert resp.status == 401
        assert calls == []

        resp = await cli.post(
            "/webhooks/deterministic",
            data=raw_body,
            headers={
                "X-GitHub-Delivery": "valid-signature",
                "X-Hub-Signature-256": valid_sig,
            },
        )
        assert resp.status == 200

    assert len(calls) == 1
    assert calls[0]["webhook_secret"] == "route-secret"


@pytest.mark.asyncio
async def test_deterministic_handler_can_disable_secret_injection(monkeypatch):
    calls = []

    def handle(**kwargs):
        calls.append(kwargs)
        return {"status_code": 200, "body": {"status": "ok"}}

    module_name = _install_handler_module(monkeypatch, handle=handle)
    routes = {
        "deterministic": {
            "secret": "route-secret",
            "deterministic_handler": {
                "import": f"{module_name}:handle",
                "pass_secret": False,
            },
        }
    }
    adapter = _make_adapter(routes)
    raw_body = b"{}"
    valid_sig = "sha256=" + hmac.new(b"route-secret", raw_body, hashlib.sha256).hexdigest()

    async with TestClient(TestServer(_create_app(adapter))) as cli:
        resp = await cli.post(
            "/webhooks/deterministic",
            data=raw_body,
            headers={
                "X-GitHub-Delivery": "no-secret-injection",
                "X-Hub-Signature-256": valid_sig,
            },
        )
        assert resp.status == 200

    assert len(calls) == 1
    assert calls[0]["webhook_secret"] is None


@pytest.mark.asyncio
async def test_deterministic_handler_exception_returns_generic_502(monkeypatch):
    def handle(**kwargs):
        raise RuntimeError("boom route-secret should not leak")

    module_name = _install_handler_module(monkeypatch, handle=handle)
    routes = {
        "deterministic": {
            "secret": _INSECURE_NO_AUTH,
            "deterministic_handler": {"import": f"{module_name}:handle"},
        }
    }
    adapter = _make_adapter(routes)

    async with TestClient(TestServer(_create_app(adapter))) as cli:
        resp = await cli.post(
            "/webhooks/deterministic",
            data=b"{}",
            headers={"X-GitHub-Delivery": "det-error"},
        )
        assert resp.status == 502
        data = await resp.json()

    rendered = json.dumps(data)
    assert data == {"status": "error", "error": "Deterministic handler failed"}
    assert "boom" not in rendered
    assert "route-secret" not in rendered


@pytest.mark.asyncio
async def test_deterministic_handler_exception_does_not_log_sensitive_exception_text(
    monkeypatch, caplog
):
    def handle(**kwargs):
        raise RuntimeError("boom route-secret should not leak")

    module_name = _install_handler_module(monkeypatch, handle=handle)
    routes = {
        "deterministic": {
            "secret": _INSECURE_NO_AUTH,
            "deterministic_handler": {"import": f"{module_name}:handle"},
        }
    }
    adapter = _make_adapter(routes)

    with caplog.at_level(logging.ERROR, logger="gateway.platforms.webhook"):
        async with TestClient(TestServer(_create_app(adapter))) as cli:
            resp = await cli.post(
                "/webhooks/deterministic",
                data=b"{}",
                headers={"X-GitHub-Delivery": "det-log-error"},
            )
            assert resp.status == 502

    rendered_logs = caplog.text
    assert "deterministic handler failed route=deterministic" in rendered_logs
    assert "RuntimeError" in rendered_logs
    assert "boom" not in rendered_logs
    assert "route-secret" not in rendered_logs


@pytest.mark.asyncio
async def test_deterministic_handler_rejects_oversized_body_without_content_length(
    monkeypatch,
):
    calls = []

    def handle(**kwargs):
        calls.append(kwargs)
        return {"status_code": 200, "body": {"status": "should-not-run"}}

    module_name = _install_handler_module(monkeypatch, handle=handle)
    adapter = _make_adapter(
        {
            "deterministic": {
                "secret": _INSECURE_NO_AUTH,
                "deterministic_handler": {"import": f"{module_name}:handle"},
            }
        },
        max_body_bytes=4,
    )

    class RequestWithoutContentLength:
        match_info = {"route_name": "deterministic"}
        content_length = None
        headers = {"X-GitHub-Delivery": "oversized-no-length"}
        method = "POST"
        path = "/webhooks/deterministic"

        async def read(self):
            return b"12345"

    resp = await adapter._handle_webhook(RequestWithoutContentLength())

    assert resp.status == 413
    assert calls == []


def test_dynamic_subscriptions_cannot_install_deterministic_handlers(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    (tmp_path / _DYNAMIC_ROUTES_FILENAME).write_text(
        json.dumps(
            {
                "unsafe": {
                    "secret": _INSECURE_NO_AUTH,
                    "deterministic_handler": {"import": "os:system"},
                }
            }
        ),
        encoding="utf-8",
    )

    adapter = _make_adapter({})
    adapter._reload_dynamic_routes()

    assert "unsafe" not in adapter._routes
    assert "unsafe" not in adapter._dynamic_routes


@pytest.mark.asyncio
async def test_startup_rejects_deliver_only_combined_with_deterministic_handler(monkeypatch):
    module_name = _install_handler_module(monkeypatch, handle=lambda **kwargs: {"status_code": 200, "body": {}})
    routes = {
        "bad": {
            "secret": _INSECURE_NO_AUTH,
            "deliver_only": True,
            "deliver": "telegram",
            "deterministic_handler": {"import": f"{module_name}:handle"},
        }
    }
    adapter = _make_adapter(routes)

    with pytest.raises(ValueError, match="deterministic_handler.*deliver_only"):
        await adapter.connect()
