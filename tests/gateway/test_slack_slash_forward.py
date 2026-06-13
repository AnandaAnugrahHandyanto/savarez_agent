"""
Tests for config-driven Slack slash-command HTTP forwarding.

Socket Mode delivers every manifest-declared slash through the gateway's
WebSocket, so commands owned by an external local service (e.g. a separate
approval/ops server) never reach their HTTP Request URL. The
``slack_slash_forward`` module lets a profile declare ``slack.slash_forwards``
in config.yaml so the gateway acks the slash and relays a re-signed copy of
the payload to that service.
"""

import hashlib
import hmac
import json
import time

import pytest

from gateway.platforms.slack_slash_forward import (
    build_signed_request,
    forward_slash_command,
    parse_slash_forwards,
    post_response_url,
)


# ---------------------------------------------------------------------------
# parse_slash_forwards
# ---------------------------------------------------------------------------

def test_parse_slash_forwards_normalizes_names():
    raw = {
        "/wpc-order": "http://127.0.0.1:8787/slack/commands/order-collect",
        "other": "http://127.0.0.1:9999/hook",
    }
    parsed = parse_slash_forwards(raw)
    assert parsed == {
        "wpc-order": "http://127.0.0.1:8787/slack/commands/order-collect",
        "other": "http://127.0.0.1:9999/hook",
    }


def test_parse_slash_forwards_rejects_non_dict():
    assert parse_slash_forwards(None) == {}
    assert parse_slash_forwards("wpc-order") == {}
    assert parse_slash_forwards(["wpc-order"]) == {}


def test_parse_slash_forwards_skips_empty_entries():
    raw = {"": "http://localhost/x", "ok": "", "good": "http://localhost/y", "/": "http://localhost/z"}
    assert parse_slash_forwards(raw) == {"good": "http://localhost/y"}


# ---------------------------------------------------------------------------
# build_signed_request — must satisfy Slack's v0 signature scheme so an
# external server's standard verification accepts the forwarded copy.
# ---------------------------------------------------------------------------

def _verify_slack_signature(signing_secret: str, timestamp: str, body: bytes, signature: str) -> bool:
    """Mirror of a standard Slack v0 verifier (e.g. WPC approval server)."""
    base = b"v0:" + timestamp.encode("utf-8") + b":" + body
    expected = "v0=" + hmac.new(signing_secret.encode("utf-8"), base, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def test_build_signed_request_roundtrips_standard_verifier():
    command = {
        "command": "/wpc-order",
        "text": "collect",
        "user_id": "U123",
        "channel_id": "C456",
        "team_id": "T789",
        "trigger_id": "tr-1",
        "response_url": "https://hooks.slack.com/commands/T789/1/abc",
    }
    secret = "test-signing-secret"
    body, headers = build_signed_request(command, secret, timestamp="1700000000")

    assert headers["Content-Type"] == "application/x-www-form-urlencoded"
    assert headers["X-Slack-Request-Timestamp"] == "1700000000"
    assert _verify_slack_signature(secret, "1700000000", body, headers["X-Slack-Signature"])


def test_build_signed_request_body_parses_back_to_command_fields():
    import urllib.parse

    command = {"command": "/wpc-order", "text": "collect", "user_id": "U123", "_ignored": {"nested": 1}}
    body, _headers = build_signed_request(command, "s", timestamp="1700000000")
    form = {k: v[0] for k, v in urllib.parse.parse_qs(body.decode("utf-8")).items()}
    assert form["command"] == "/wpc-order"
    assert form["text"] == "collect"
    assert form["user_id"] == "U123"
    assert "_ignored" not in form


def test_build_signed_request_defaults_timestamp_to_now():
    body, headers = build_signed_request({"command": "/x"}, "s")
    ts = int(headers["X-Slack-Request-Timestamp"])
    assert abs(time.time() - ts) < 5
    assert _verify_slack_signature("s", headers["X-Slack-Request-Timestamp"], body, headers["X-Slack-Signature"])


# ---------------------------------------------------------------------------
# forward_slash_command / post_response_url — fake aiohttp session
# ---------------------------------------------------------------------------

class _FakeResponse:
    def __init__(self, status=200, text=""):
        self.status = status
        self._text = text

    async def text(self):
        return self._text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _FakeSession:
    def __init__(self, response: _FakeResponse, raise_exc: Exception = None):
        self._response = response
        self._raise = raise_exc
        self.posts = []

    def post(self, url, **kwargs):
        self.posts.append({"url": url, **kwargs})
        if self._raise is not None:
            raise self._raise
        return self._response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


COMMAND = {"command": "/wpc-order", "text": "collect", "user_id": "U123"}


@pytest.mark.asyncio
async def test_forward_relays_json_payload_on_200():
    session = _FakeSession(_FakeResponse(200, json.dumps({"response_type": "ephemeral", "text": "ok"})))
    result = await forward_slash_command(
        COMMAND, "http://127.0.0.1:8787/slack/commands/order-collect", "secret",
        session_factory=lambda: session,
    )
    assert result["ok"] is True
    assert result["payload"] == {"response_type": "ephemeral", "text": "ok"}
    assert session.posts[0]["url"] == "http://127.0.0.1:8787/slack/commands/order-collect"
    headers = session.posts[0]["headers"]
    assert _verify_slack_signature("secret", headers["X-Slack-Request-Timestamp"], session.posts[0]["data"], headers["X-Slack-Signature"])


@pytest.mark.asyncio
async def test_forward_reports_non_200_status():
    session = _FakeSession(_FakeResponse(401, "invalid signature"))
    result = await forward_slash_command(COMMAND, "http://127.0.0.1:8787/x", "secret", session_factory=lambda: session)
    assert result["ok"] is False
    assert result["status"] == 401
    assert "invalid signature" in result["error"]


@pytest.mark.asyncio
async def test_forward_requires_signing_secret():
    session = _FakeSession(_FakeResponse(200, "{}"))
    result = await forward_slash_command(COMMAND, "http://127.0.0.1:8787/x", "", session_factory=lambda: session)
    assert result["ok"] is False
    assert "SLACK_SIGNING_SECRET" in result["error"]
    assert session.posts == []


@pytest.mark.asyncio
async def test_forward_reports_connection_error():
    session = _FakeSession(_FakeResponse(200, "{}"), raise_exc=ConnectionError("refused"))
    result = await forward_slash_command(COMMAND, "http://127.0.0.1:8787/x", "secret", session_factory=lambda: session)
    assert result["ok"] is False
    assert "refused" in result["error"]


@pytest.mark.asyncio
async def test_forward_tolerates_non_json_200_body():
    session = _FakeSession(_FakeResponse(200, "plain ok"))
    result = await forward_slash_command(COMMAND, "http://127.0.0.1:8787/x", "secret", session_factory=lambda: session)
    assert result["ok"] is True
    assert result["payload"] == {"response_type": "ephemeral", "text": "plain ok"}


@pytest.mark.asyncio
async def test_post_response_url_sends_json_payload():
    session = _FakeSession(_FakeResponse(200, "ok"))
    ok = await post_response_url(
        "https://hooks.slack.com/commands/T/1/abc",
        {"response_type": "ephemeral", "text": "done"},
        session_factory=lambda: session,
    )
    assert ok is True
    assert session.posts[0]["url"] == "https://hooks.slack.com/commands/T/1/abc"
    assert session.posts[0]["json"] == {"response_type": "ephemeral", "text": "done"}


# ---------------------------------------------------------------------------
# SlackAdapter._handle_forwarded_slash_command — relays outcome via response_url
# ---------------------------------------------------------------------------

def _make_adapter():
    import sys
    from unittest.mock import MagicMock

    if "slack_bolt" not in sys.modules or not hasattr(sys.modules["slack_bolt"], "__file__"):
        slack_bolt = MagicMock()
        slack_bolt.async_app.AsyncApp = MagicMock
        slack_bolt.adapter.socket_mode.async_handler.AsyncSocketModeHandler = MagicMock
        slack_sdk = MagicMock()
        slack_sdk.web.async_client.AsyncWebClient = MagicMock
        for name, mod in [
            ("slack_bolt", slack_bolt),
            ("slack_bolt.async_app", slack_bolt.async_app),
            ("slack_bolt.adapter", slack_bolt.adapter),
            ("slack_bolt.adapter.socket_mode", slack_bolt.adapter.socket_mode),
            ("slack_bolt.adapter.socket_mode.async_handler", slack_bolt.adapter.socket_mode.async_handler),
            ("slack_sdk", slack_sdk),
            ("slack_sdk.web", slack_sdk.web),
            ("slack_sdk.web.async_client", slack_sdk.web.async_client),
        ]:
            sys.modules.setdefault(name, mod)

    import gateway.platforms.slack as slack_mod

    slack_mod.SLACK_AVAILABLE = True
    from gateway.config import Platform, PlatformConfig

    adapter = object.__new__(slack_mod.SlackAdapter)
    adapter.platform = Platform.SLACK
    adapter.config = PlatformConfig(enabled=True, extra={})
    return adapter


@pytest.mark.asyncio
async def test_handler_relays_forward_payload_to_response_url(monkeypatch):
    import gateway.platforms.slack_slash_forward as fwd_mod

    adapter = _make_adapter()
    posted = []

    async def fake_forward(command, url, secret, **kwargs):
        return {"ok": True, "status": 200, "payload": {"text": "recorded"}}

    async def fake_post(response_url, payload, **kwargs):
        posted.append((response_url, payload))
        return True

    monkeypatch.setattr(fwd_mod, "forward_slash_command", fake_forward)
    monkeypatch.setattr(fwd_mod, "post_response_url", fake_post)
    monkeypatch.setenv("SLACK_SIGNING_SECRET", "secret")

    command = {"command": "/wpc-order", "text": "collect", "response_url": "https://hooks.slack.com/commands/T/1/a"}
    await adapter._handle_forwarded_slash_command(command, "http://127.0.0.1:8787/x")

    assert posted == [
        ("https://hooks.slack.com/commands/T/1/a", {"text": "recorded", "response_type": "ephemeral"})
    ]


@pytest.mark.asyncio
async def test_handler_reports_forward_error_to_response_url(monkeypatch):
    import gateway.platforms.slack_slash_forward as fwd_mod

    adapter = _make_adapter()
    posted = []

    async def fake_forward(command, url, secret, **kwargs):
        return {"ok": False, "error": "connection refused"}

    async def fake_post(response_url, payload, **kwargs):
        posted.append(payload)
        return True

    monkeypatch.setattr(fwd_mod, "forward_slash_command", fake_forward)
    monkeypatch.setattr(fwd_mod, "post_response_url", fake_post)

    command = {"command": "/wpc-order", "response_url": "https://hooks.slack.com/commands/T/1/a"}
    await adapter._handle_forwarded_slash_command(command, "http://127.0.0.1:8787/x")

    assert len(posted) == 1
    assert posted[0]["response_type"] == "ephemeral"
    assert "connection refused" in posted[0]["text"]


# ---------------------------------------------------------------------------
# config.yaml bridging — slack.slash_forwards must land in PlatformConfig.extra
# ---------------------------------------------------------------------------

def test_slash_forwards_bridged_from_yaml(tmp_path, monkeypatch):
    from gateway.config import Platform, load_gateway_config

    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    (hermes_home / "config.yaml").write_text(
        "slack:\n"
        "  slash_forwards:\n"
        "    wpc-order: http://127.0.0.1:8787/slack/commands/order-collect\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test")

    cfg = load_gateway_config()
    slack_cfg = cfg.platforms[Platform.SLACK]
    assert slack_cfg.extra.get("slash_forwards") == {
        "wpc-order": "http://127.0.0.1:8787/slack/commands/order-collect"
    }
