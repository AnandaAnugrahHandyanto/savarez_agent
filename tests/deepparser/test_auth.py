"""Auth: 401 / 403 / 429 flows."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_missing_key_returns_401(async_client: AsyncClient) -> None:
    resp = await async_client.get("/parse/fake-job")
    assert resp.status_code == 401
    body = resp.json()["detail"]
    assert body["code"] == "MISSING_API_KEY"


async def test_invalid_key_returns_401(async_client: AsyncClient) -> None:
    resp = await async_client.get(
        "/parse/fake-job", headers={"X-API-Key": "dp_live_notavalidkey"}
    )
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "INVALID_API_KEY"


async def test_revoked_key_returns_403(async_client: AsyncClient, api_key: str) -> None:
    import aiosqlite
    import deepparser_api.db as db_mod

    # Revoke the key directly in DB
    async with aiosqlite.connect(db_mod.DB_PATH) as conn:
        await conn.execute("UPDATE api_keys SET revoked=1 WHERE key=?", (api_key,))
        await conn.commit()

    resp = await async_client.get(
        "/parse/fake-job", headers={"X-API-Key": api_key}
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "REVOKED_API_KEY"


async def test_valid_key_passes_auth(async_client: AsyncClient, api_key: str) -> None:
    resp = await async_client.get(
        "/parse/nonexistent-job", headers={"X-API-Key": api_key}
    )
    # 404 means auth passed (key was recognized), just the job doesn't exist
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "NOT_FOUND"


async def test_rate_limit_triggers_after_max_failures(
    async_client: AsyncClient, monkeypatch
) -> None:
    import deepparser_api.config as cfg_mod

    monkeypatch.setattr(cfg_mod, "AUTH_FAIL_MAX", 3)
    import deepparser_api.auth as auth_mod
    monkeypatch.setattr(auth_mod, "AUTH_FAIL_MAX", 3)

    # Exhaust the limit with bad keys
    for _ in range(3):
        await async_client.get(
            "/parse/x", headers={"X-API-Key": "dp_live_bad"}
        )

    resp = await async_client.get(
        "/parse/x", headers={"X-API-Key": "dp_live_bad"}
    )
    assert resp.status_code == 429
    assert resp.json()["detail"]["code"] == "RATE_LIMITED"
