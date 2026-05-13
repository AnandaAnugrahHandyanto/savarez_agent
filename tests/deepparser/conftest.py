"""Shared fixtures for deepparser_api unit tests."""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# ---------------------------------------------------------------------------
# Pinned dp_cli JSON fixtures — any DPCLIParseResult model drift is caught here
# ---------------------------------------------------------------------------

PINNED_PARSE_JSON = {
    "ok": True,
    "uploads": [
        {
            "result": {
                "response": {
                    "body": {
                        "data": {
                            "id": "file-abc123",
                            "folder_id": "folder-xyz789",
                            "file_name": "test.pdf",
                            "extension": "pdf",
                        }
                    }
                }
            },
            "ready": {
                "status": {
                    "tasks": {
                        "plugin_parse": {"pages": 4, "tables": 2}
                    }
                }
            },
        }
    ],
}

PINNED_ASK_JSON = {
    "ok": True,
    "response": {
        "body": {
            "answer": "The total contract value is $84,000.",
            "citations": [
                {"filename": "test.pdf", "page": 2, "cell": None},
            ],
        }
    },
}


# ---------------------------------------------------------------------------
# Core fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def async_client(tmp_path, monkeypatch):
    """
    httpx.AsyncClient pointed at the FastAPI ASGI app, isolated per test:
    - fresh SQLite DB in tmp_path
    - upload dir in tmp_path
    - rate-limit stores cleared
    - parse semaphore reset
    """
    db_path = str(tmp_path / "test.db")
    upload_dir = str(tmp_path / "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    import deepparser_api.auth as auth_mod
    import deepparser_api.config as cfg_mod
    import deepparser_api.db as db_mod
    import deepparser_api.routes.parse as parse_mod
    import deepparser_api.tasks.parse_task as pt_mod

    monkeypatch.setattr(db_mod, "DB_PATH", db_path)
    monkeypatch.setattr(cfg_mod, "DB_PATH", db_path)
    monkeypatch.setattr(cfg_mod, "UPLOAD_DIR", upload_dir)
    monkeypatch.setattr(parse_mod, "UPLOAD_DIR", upload_dir)
    monkeypatch.setenv("ADMIN_PASSWORD", "test-admin-pw")
    monkeypatch.setattr(cfg_mod, "ADMIN_PASSWORD", "test-admin-pw")

    # Clear in-memory rate-limit buckets
    auth_mod._auth_failures.clear()
    auth_mod._key_registrations.clear()

    # Reset semaphore so size changes take effect
    pt_mod._semaphore = None

    # Init DB at the patched path
    await db_mod.init_db()

    from deepparser_api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client

    # Cleanup
    auth_mod._auth_failures.clear()
    auth_mod._key_registrations.clear()
    pt_mod._semaphore = None


@pytest_asyncio.fixture
async def api_key(async_client: AsyncClient) -> str:
    """Register a fresh API key and return it."""
    resp = await async_client.post(
        "/keys", json={"email": "test@example.com", "intended_use": "testing"}
    )
    assert resp.status_code == 200
    return resp.json()["api_key"]


@pytest_asyncio.fixture
async def ready_job(async_client: AsyncClient, api_key: str, tmp_path) -> dict:
    """
    Insert a READY parse job directly into the DB; return {job_id, api_key}.
    Useful for ask tests that don't need to go through the full parse pipeline.
    """
    import json
    import uuid

    import aiosqlite

    import deepparser_api.db as db_mod

    job_id = str(uuid.uuid4())

    # Look up the api_key_id
    async with aiosqlite.connect(db_mod.DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        row = await (await conn.execute(
            "SELECT id FROM api_keys WHERE key=?", (api_key,)
        )).fetchone()
        key_id = row["id"]

        result_json = json.dumps({
            "file_id": "file-abc123",
            "folder_id": "folder-xyz",
            "file_name": "test.pdf",
            "extension": "pdf",
            "pages": 4,
            "tables": 2,
        })
        await conn.execute(
            """INSERT INTO parse_jobs
               (id, api_key_id, status, filename_original, filename_stored,
                dp_file_id, dp_folder_id, result_json, completed_at)
               VALUES (?, ?, 'READY', 'test.pdf', 'stored.pdf',
                       'file-abc123', 'folder-xyz', ?, datetime('now'))""",
            (job_id, key_id, result_json),
        )
        await conn.commit()

    return {"job_id": job_id, "api_key": api_key, "key_id": key_id}
