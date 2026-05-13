"""POST /keys: registration and IP rate limit."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_register_key_returns_api_key(async_client: AsyncClient) -> None:
    resp = await async_client.post(
        "/keys", json={"email": "dev@example.com", "intended_use": "test"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["api_key"].startswith("dp_live_")
    assert len(data["api_key"]) == len("dp_live_") + 32  # 16 hex bytes = 32 chars
    assert data["created_at"]


async def test_register_key_missing_email_returns_422(async_client: AsyncClient) -> None:
    resp = await async_client.post("/keys", json={"intended_use": "no email"})
    assert resp.status_code == 422


async def test_register_key_optional_intended_use(async_client: AsyncClient) -> None:
    resp = await async_client.post("/keys", json={"email": "dev@example.com"})
    assert resp.status_code == 200


async def test_register_key_rate_limit_5_per_hour(
    async_client: AsyncClient, monkeypatch
) -> None:
    import deepparser_api.auth as auth_mod
    import deepparser_api.config as cfg_mod

    monkeypatch.setattr(cfg_mod, "KEYS_PER_IP_MAX", 3)
    monkeypatch.setattr(auth_mod, "KEYS_PER_IP_MAX", 3)

    for _ in range(3):
        resp = await async_client.post(
            "/keys", json={"email": "flood@example.com"}
        )
        assert resp.status_code == 200

    resp = await async_client.post(
        "/keys", json={"email": "flood@example.com"}
    )
    assert resp.status_code == 429
    assert resp.json()["detail"]["code"] == "RATE_LIMITED"


async def test_each_key_is_unique(async_client: AsyncClient) -> None:
    keys = []
    for i in range(3):
        resp = await async_client.post(
            "/keys", json={"email": f"u{i}@example.com"}
        )
        assert resp.status_code == 200
        keys.append(resp.json()["api_key"])
    assert len(set(keys)) == 3  # all distinct
