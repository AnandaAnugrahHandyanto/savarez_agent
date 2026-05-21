"""Security regression tests for hermes_cli.proxy.server."""

from __future__ import annotations

import pytest
from aiohttp import ClientSession, web

from hermes_cli.proxy.adapters.base import UpstreamAdapter, UpstreamCredential
from hermes_cli.proxy.server import create_app


class _FakeAdapter(UpstreamAdapter):
    name = "fake"
    display_name = "Fake Subscription"
    allowed_paths = frozenset({"/chat/completions", "/models"})

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url

    def is_authenticated(self) -> bool:
        return True

    def get_credential(self) -> UpstreamCredential:
        return UpstreamCredential(
            bearer="REAL_PROVIDER_ACCESS_TOKEN_SECRET",
            base_url=self.base_url,
            token_type="Bearer",
            expires_at=None,
        )


async def _start_upstream(captured: dict[str, str | None]) -> tuple[web.AppRunner, int]:
    async def upstream_handler(request: web.Request) -> web.Response:
        captured["authorization"] = request.headers.get("Authorization")
        return web.json_response({"ok": True})

    upstream_app = web.Application()
    upstream_app.router.add_route("*", "/v1/{tail:.*}", upstream_handler)
    runner = web.AppRunner(upstream_app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    return runner, runner.addresses[0][1]


async def _start_proxy(upstream_port: int) -> tuple[web.AppRunner, int]:
    proxy_app = create_app(
        _FakeAdapter(f"http://127.0.0.1:{upstream_port}/v1"),
        client_api_key="required-client-secret",
    )
    runner = web.AppRunner(proxy_app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    return runner, runner.addresses[0][1]


@pytest.mark.asyncio
async def test_proxy_rejects_requests_without_configured_client_bearer() -> None:
    captured: dict[str, str | None] = {}
    upstream_runner, upstream_port = await _start_upstream(captured)
    proxy_runner, proxy_port = await _start_proxy(upstream_port)

    try:
        async with ClientSession() as session:
            response = await session.post(
                f"http://127.0.0.1:{proxy_port}/v1/chat/completions",
                headers={"Authorization": "Bearer attacker-supplied-token"},
                json={"model": "paid-model", "messages": []},
            )
            body = await response.json()

        assert response.status == 401
        assert body["error"]["code"] == "invalid_proxy_api_key"
        assert captured == {}
    finally:
        await proxy_runner.cleanup()
        await upstream_runner.cleanup()


@pytest.mark.asyncio
async def test_proxy_accepts_configured_client_bearer_and_replaces_upstream_auth() -> None:
    captured: dict[str, str | None] = {}
    upstream_runner, upstream_port = await _start_upstream(captured)
    proxy_runner, proxy_port = await _start_proxy(upstream_port)

    try:
        async with ClientSession() as session:
            response = await session.post(
                f"http://127.0.0.1:{proxy_port}/v1/chat/completions",
                headers={"Authorization": "Bearer required-client-secret"},
                json={"model": "paid-model", "messages": []},
            )
            body = await response.json()

        assert response.status == 200
        assert body == {"ok": True}
        assert captured["authorization"] == "Bearer REAL_PROVIDER_ACCESS_TOKEN_SECRET"
    finally:
        await proxy_runner.cleanup()
        await upstream_runner.cleanup()
