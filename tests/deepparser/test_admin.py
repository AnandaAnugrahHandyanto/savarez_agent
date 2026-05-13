"""GET /admin/stats: password guard and stat accuracy."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_admin_no_password_configured_returns_500(
    async_client: AsyncClient, monkeypatch
) -> None:
    import deepparser_api.routes.admin as admin_mod

    # Must patch the name as imported in the admin module, not just config
    monkeypatch.setattr(admin_mod, "ADMIN_PASSWORD", "")

    resp = await async_client.get(
        "/admin/stats", headers={"X-Admin-Password": "anything"}
    )
    assert resp.status_code == 500
    assert "ADMIN_PASSWORD" in resp.json()["detail"]


async def test_admin_wrong_password_returns_401(
    async_client: AsyncClient,
) -> None:
    resp = await async_client.get(
        "/admin/stats", headers={"X-Admin-Password": "wrong-password"}
    )
    assert resp.status_code == 401


async def test_admin_missing_password_header_returns_401(
    async_client: AsyncClient,
) -> None:
    resp = await async_client.get("/admin/stats")
    assert resp.status_code == 401


async def test_admin_correct_password_returns_stats(
    async_client: AsyncClient, api_key: str
) -> None:
    resp = await async_client.get(
        "/admin/stats", headers={"X-Admin-Password": "test-admin-pw"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["keys_registered"] >= 1
    assert data["keys_activated"] == 0  # no parse completed yet
    assert data["activation_rate"] == 0.0
    assert isinstance(data["parse_jobs"], int)
    assert isinstance(data["storage_bytes"], int)
    assert isinstance(data["errors_today"], int)


async def test_admin_activation_rate_updates_after_parse(
    async_client: AsyncClient, ready_job: dict
) -> None:
    """first_parse_at set → key is 'activated' → activation_rate > 0."""
    import aiosqlite
    import deepparser_api.db as db_mod

    # Mark the key as having completed a parse
    async with aiosqlite.connect(db_mod.DB_PATH) as conn:
        await conn.execute(
            "UPDATE api_keys SET first_parse_at=datetime('now') WHERE id=?",
            (ready_job["key_id"],),
        )
        await conn.commit()

    resp = await async_client.get(
        "/admin/stats", headers={"X-Admin-Password": "test-admin-pw"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["keys_activated"] >= 1
    assert data["activation_rate"] > 0.0
