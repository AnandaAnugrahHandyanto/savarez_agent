"""Tests for the Discord interaction route mounted on the API server.

These tests intentionally keep the route local/test-only. They prove the
safety boundary before any live Discord endpoint registration:
raw request bytes and signature headers are captured first, invalid signatures
fail closed, and component callbacks only produce an ACK preview.
"""

from __future__ import annotations

import importlib
import json

pytest = importlib.import_module("pytest")
web = importlib.import_module("aiohttp.web")
aiohttp_test_utils = importlib.import_module("aiohttp.test_utils")
TestClient = aiohttp_test_utils.TestClient
TestServer = aiohttp_test_utils.TestServer

from gateway.config import PlatformConfig
from gateway.platforms.api_server import APIServerAdapter
from gateway.discord_interactions import (
    DISCORD_INTERACTION_ROUTE,
    DiscordInteractionConfig,
    resolve_discord_interaction_config,
)


def _adapter(extra: dict | None = None) -> APIServerAdapter:
    return APIServerAdapter(PlatformConfig(enabled=True, extra=extra or {}))


@pytest.mark.parametrize(
    "extra",
    [
        {},
        {"discord_interactions": {"enabled": True}},
        {"discord_interactions": {"enabled": True, "public_key_env": "DISCORD_BOT_TOKEN"}},
        {"discord_interactions": {"enabled": True, "public_key_env": "DISCORD_CLIENT_SECRET"}},
        {"discord_interactions": {"enabled": True, "public_key_env": "DISCORD_WEBHOOK_URL"}},
        {"discord_interactions": {"enabled": True, "public_key_env": "HERMES_WEBHOOK_SECRET"}},
        {"discord_interactions": {"enabled": True, "public_key_env": "TELEGRAM_TOKEN"}},
    ],
)
def test_discord_interaction_config_fails_closed_without_explicit_public_key(extra, monkeypatch):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "not-a-public-key")
    monkeypatch.setenv("DISCORD_CLIENT_SECRET", "not-a-public-key")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "not-a-public-key")
    monkeypatch.setenv("HERMES_WEBHOOK_SECRET", "not-a-public-key")
    monkeypatch.setenv("TELEGRAM_TOKEN", "not-a-public-key")

    config = resolve_discord_interaction_config(extra)

    assert config.enabled is False
    assert config.public_key == ""
    assert config.route_path == DISCORD_INTERACTION_ROUTE


def test_discord_interaction_config_accepts_only_public_key_source(monkeypatch):
    monkeypatch.setenv("DISCORD_APPLICATION_PUBLIC_KEY", "abc123")

    config = resolve_discord_interaction_config(
        {"discord_interactions": {"enabled": True, "public_key_env": "DISCORD_APPLICATION_PUBLIC_KEY"}}
    )

    assert config == DiscordInteractionConfig(
        enabled=True,
        public_key="abc123",
        route_path=DISCORD_INTERACTION_ROUTE,
    )


@pytest.mark.asyncio
async def test_route_is_not_mounted_when_config_is_disabled():
    adapter = _adapter()
    app = web.Application()

    mounted = adapter._register_discord_interaction_route(app)

    assert mounted is False
    assert all(getattr(route.resource, "canonical", "") != DISCORD_INTERACTION_ROUTE for route in app.router.routes())


@pytest.mark.asyncio
async def test_ping_reads_raw_body_and_signature_headers_before_ack_preview():
    adapter = _adapter({"discord_interactions": {"enabled": True, "public_key": "public-key"}})
    seen = {}

    def verifier(*, public_key: str, timestamp: str, signature: str, body: bytes) -> bool:
        seen.update(
            {
                "public_key": public_key,
                "timestamp": timestamp,
                "signature": signature,
                "body": body,
            }
        )
        return True

    adapter._discord_interaction_verifier = verifier
    app = web.Application()
    assert adapter._register_discord_interaction_route(app) is True

    body = b'{"type":1,"id":"interaction-1"}'
    async with TestClient(TestServer(app)) as cli:
        resp = await cli.post(
            DISCORD_INTERACTION_ROUTE,
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Signature-Ed25519": "sig-1",
                "X-Signature-Timestamp": "12345",
            },
        )
        assert resp.status == 200
        assert await resp.json() == {"type": 1}

    assert seen == {
        "public_key": "public-key",
        "timestamp": "12345",
        "signature": "sig-1",
        "body": body,
    }


@pytest.mark.asyncio
async def test_invalid_signature_fails_before_json_parse_or_dry_run():
    adapter = _adapter({"discord_interactions": {"enabled": True, "public_key": "public-key"}})
    calls = []

    def verifier(**_kwargs) -> bool:
        return False

    adapter._discord_interaction_verifier = verifier
    adapter._discord_interaction_dry_run_handler = lambda _payload: calls.append(_payload)
    app = web.Application()
    adapter._register_discord_interaction_route(app)

    async with TestClient(TestServer(app)) as cli:
        resp = await cli.post(
            DISCORD_INTERACTION_ROUTE,
            data=b"not-json-but-signature-fails-first",
            headers={
                "Content-Type": "application/json",
                "X-Signature-Ed25519": "bad-sig",
                "X-Signature-Timestamp": "12345",
            },
        )
        assert resp.status == 401
        data = await resp.json()
        assert data["error"] == "invalid_signature"

    assert calls == []


@pytest.mark.asyncio
async def test_component_interaction_returns_ephemeral_dry_run_ack_without_apply():
    adapter = _adapter({"discord_interactions": {"enabled": True, "public_key": "public-key"}})
    calls = []

    adapter._discord_interaction_verifier = lambda **_kwargs: True
    adapter._discord_interaction_dry_run_handler = lambda payload: calls.append(payload) or {
        "status": "dry_run",
        "action": "approve",
        "review_id": "review-123",
    }
    app = web.Application()
    adapter._register_discord_interaction_route(app)

    payload = {
        "type": 3,
        "id": "interaction-2",
        "data": {"custom_id": "mim:soma-review:v1:approve:review-123"},
    }
    async with TestClient(TestServer(app)) as cli:
        resp = await cli.post(
            DISCORD_INTERACTION_ROUTE,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-Signature-Ed25519": "sig-2",
                "X-Signature-Timestamp": "12345",
            },
        )
        assert resp.status == 200
        data = await resp.json()

    assert calls == [payload]
    assert data["type"] == 4
    assert data["data"]["flags"] == 64
    assert "dry-run" in data["data"]["content"]
    assert "approve" in data["data"]["content"]
    assert "review-123" in data["data"]["content"]


@pytest.mark.asyncio
async def test_route_rejects_unknown_component_payload_without_dry_run_apply():
    adapter = _adapter({"discord_interactions": {"enabled": True, "public_key": "public-key"}})
    calls = []

    adapter._discord_interaction_verifier = lambda **_kwargs: True
    adapter._discord_interaction_dry_run_handler = lambda payload: calls.append(payload)
    app = web.Application()
    adapter._register_discord_interaction_route(app)

    payload = {"type": 3, "id": "interaction-3", "data": {"custom_id": "bad:payload"}}
    async with TestClient(TestServer(app)) as cli:
        resp = await cli.post(
            DISCORD_INTERACTION_ROUTE,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-Signature-Ed25519": "sig-3",
                "X-Signature-Timestamp": "12345",
            },
        )
        assert resp.status == 400
        data = await resp.json()

    assert data["error"] == "invalid_component"
    assert calls == []
