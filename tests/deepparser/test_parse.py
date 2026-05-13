"""POST /parse and GET /parse/{job_id}: submit, poll, state machine."""
from __future__ import annotations

import asyncio
import json
import os
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from .conftest import PINNED_PARSE_JSON

pytestmark = pytest.mark.asyncio


def _pdf_file(name: str = "test.pdf", size: int = 100) -> tuple[str, bytes, str]:
    return (name, b"%PDF-1.4 " + b"x" * size, "application/octet-stream")


async def test_submit_returns_queued(
    async_client: AsyncClient, api_key: str
) -> None:
    resp = await async_client.post(
        "/parse",
        files={"file": _pdf_file()},
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "QUEUED"
    assert "job_id" in data


async def test_submit_unsupported_extension(
    async_client: AsyncClient, api_key: str
) -> None:
    resp = await async_client.post(
        "/parse",
        files={"file": ("exploit.exe", b"MZ...", "application/octet-stream")},
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 400
    body = resp.json()["detail"]
    assert body["code"] == "UNSUPPORTED_FORMAT"
    assert ".exe" in body["message"]


async def test_submit_file_too_large(
    async_client: AsyncClient, api_key: str, monkeypatch
) -> None:
    import deepparser_api.config as cfg_mod

    monkeypatch.setattr(cfg_mod, "MAX_UPLOAD_BYTES", 10)

    import deepparser_api.routes.parse as parse_mod
    monkeypatch.setattr(parse_mod, "MAX_UPLOAD_BYTES", 10)

    resp = await async_client.post(
        "/parse",
        files={"file": _pdf_file(size=20)},
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "FILE_TOO_LARGE"


async def test_submit_stores_uuid_filename_not_original(
    async_client: AsyncClient, api_key: str
) -> None:
    """Original filename must NOT appear in the stored filename (path traversal guard)."""
    resp = await async_client.post(
        "/parse",
        files={"file": ("../../etc/passwd.pdf", b"%PDF-1.4 real", "application/octet-stream")},
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]

    # Check the DB record — filename_stored is the UUID name, filename_original keeps the real name
    import aiosqlite
    import deepparser_api.db as db_mod

    async with aiosqlite.connect(db_mod.DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        row = await (await conn.execute(
            "SELECT filename_original, filename_stored FROM parse_jobs WHERE id=?", (job_id,)
        )).fetchone()

    assert row is not None
    assert "passwd" not in row["filename_stored"]
    assert "etc" not in row["filename_stored"]
    assert row["filename_stored"].endswith(".pdf")
    # Original name is preserved for logging purposes
    assert "passwd" in row["filename_original"]


async def test_poll_job_scoped_to_api_key(
    async_client: AsyncClient, api_key: str, ready_job: dict
) -> None:
    """Job belonging to a different key should return 404."""
    # Register a second key
    resp2 = await async_client.post(
        "/keys", json={"email": "other@example.com"}
    )
    other_key = resp2.json()["api_key"]

    resp = await async_client.get(
        f"/parse/{ready_job['job_id']}",
        headers={"X-API-Key": other_key},
    )
    assert resp.status_code == 404


async def test_poll_ready_job(
    async_client: AsyncClient, ready_job: dict
) -> None:
    resp = await async_client.get(
        f"/parse/{ready_job['job_id']}",
        headers={"X-API-Key": ready_job["api_key"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "READY"
    assert data["result"]["file_id"] == "file-abc123"


async def test_parse_task_state_machine_ready(
    async_client: AsyncClient, api_key: str, monkeypatch
) -> None:
    """QUEUED → PARSING → READY when dp_cli returns successfully."""
    from deepparser_api.models import DPCLIParseResult

    mock_result = DPCLIParseResult(
        file_id="file-abc123",
        folder_id="folder-xyz",
        file_name="test.pdf",
        extension="pdf",
        pages=4,
        tables=2,
    )

    with patch(
        "deepparser_api.tasks.parse_task.run_dp_parse",
        new=AsyncMock(return_value=mock_result),
    ):
        resp = await async_client.post(
            "/parse?mode=sync",
            files={"file": _pdf_file()},
            headers={"X-API-Key": api_key},
        )

    assert resp.status_code == 200
    data = resp.json()
    # sync mode + instant completion → READY inline
    assert data["status"] == "READY"
    assert data["result"]["file_id"] == "file-abc123"


async def test_parse_task_state_machine_failed(
    async_client: AsyncClient, api_key: str, monkeypatch
) -> None:
    """dp_cli raises → job → PARSE_FAILED."""
    with patch(
        "deepparser_api.tasks.parse_task.run_dp_parse",
        new=AsyncMock(side_effect=RuntimeError("dp exit 1: connection refused")),
    ):
        resp = await async_client.post(
            "/parse?mode=sync",
            files={"file": _pdf_file()},
            headers={"X-API-Key": api_key},
        )

    # sync wait may time out before task fails — just get the job_id and poll
    job_id = resp.json()["job_id"]

    # Give the background task a moment to finish
    await asyncio.sleep(0.1)

    poll = await async_client.get(
        f"/parse/{job_id}", headers={"X-API-Key": api_key}
    )
    assert poll.json()["status"] == "PARSE_FAILED"
    assert "dp exit 1" in poll.json()["error_detail"]


async def test_parse_task_timeout(
    async_client: AsyncClient, api_key: str, monkeypatch
) -> None:
    """asyncio.TimeoutError from dp_cli → TIMEOUT status."""
    async def _slow(*_args, **_kwargs):
        await asyncio.sleep(999)

    with patch(
        "deepparser_api.tasks.parse_task.run_dp_parse",
        new=AsyncMock(side_effect=asyncio.TimeoutError),
    ):
        resp = await async_client.post(
            "/parse",
            files={"file": _pdf_file()},
            headers={"X-API-Key": api_key},
        )
        job_id = resp.json()["job_id"]

    await asyncio.sleep(0.1)

    poll = await async_client.get(
        f"/parse/{job_id}", headers={"X-API-Key": api_key}
    )
    assert poll.json()["status"] == "TIMEOUT"


async def test_semaphore_full_returns_parse_failed(
    async_client: AsyncClient, api_key: str, monkeypatch
) -> None:
    """When semaphore is exhausted and times out, job → PARSE_FAILED."""
    import deepparser_api.config as cfg_mod
    import deepparser_api.tasks.parse_task as pt_mod

    monkeypatch.setattr(cfg_mod, "SEMAPHORE_TIMEOUT_SECS", 0.01)
    monkeypatch.setattr(cfg_mod, "SEMAPHORE_SIZE", 1)
    pt_mod._semaphore = None  # force re-creation with new size

    # Acquire the single semaphore slot manually so the task can't get it
    sem = pt_mod.get_semaphore()
    await sem.acquire()

    try:
        with patch("deepparser_api.tasks.parse_task.run_dp_parse", new=AsyncMock()):
            resp = await async_client.post(
                "/parse",
                files={"file": _pdf_file()},
                headers={"X-API-Key": api_key},
            )
        job_id = resp.json()["job_id"]
        await asyncio.sleep(0.1)

        poll = await async_client.get(
            f"/parse/{job_id}", headers={"X-API-Key": api_key}
        )
        assert poll.json()["status"] == "PARSE_FAILED"
        assert "Semaphore timeout" in poll.json()["error_detail"]
    finally:
        sem.release()
