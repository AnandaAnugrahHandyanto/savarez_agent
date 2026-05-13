"""POST /ask: NOT_READY guard, 404, success path."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from .conftest import PINNED_ASK_JSON

pytestmark = pytest.mark.asyncio


async def test_ask_job_not_found(
    async_client: AsyncClient, api_key: str
) -> None:
    resp = await async_client.post(
        "/ask",
        json={"job_id": "00000000-0000-0000-0000-000000000000", "question": "what?"},
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "NOT_FOUND"


async def test_ask_not_ready_returns_400(
    async_client: AsyncClient, api_key: str
) -> None:
    """QUEUED job → 400 NOT_READY."""
    # Submit a parse job (will be QUEUED immediately)
    with patch(
        "deepparser_api.tasks.parse_task.run_dp_parse",
        new=AsyncMock(side_effect=Exception("blocked for test")),
    ):
        submit_resp = await async_client.post(
            "/parse",
            files={"file": ("test.pdf", b"%PDF-1.4 x", "application/octet-stream")},
            headers={"X-API-Key": api_key},
        )
    job_id = submit_resp.json()["job_id"]

    resp = await async_client.post(
        "/ask",
        json={"job_id": job_id, "question": "what is the total?"},
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "NOT_READY"


async def test_ask_scoped_to_api_key(
    async_client: AsyncClient, ready_job: dict
) -> None:
    """Cross-key ask → 404."""
    resp2 = await async_client.post(
        "/keys", json={"email": "other2@example.com"}
    )
    other_key = resp2.json()["api_key"]

    resp = await async_client.post(
        "/ask",
        json={"job_id": ready_job["job_id"], "question": "anything"},
        headers={"X-API-Key": other_key},
    )
    assert resp.status_code == 404


async def test_ask_success(
    async_client: AsyncClient, ready_job: dict
) -> None:
    from deepparser_api.models import Citation, DPCLIAskResult

    mock_result = DPCLIAskResult(
        answer="The total contract value is $84,000.",
        citations=[Citation(filename="test.pdf", page=2)],
    )

    with patch(
        "deepparser_api.routes.ask.run_dp_ask",
        new=AsyncMock(return_value=mock_result),
    ):
        resp = await async_client.post(
            "/ask",
            json={"job_id": ready_job["job_id"], "question": "what is the total?"},
            headers={"X-API-Key": ready_job["api_key"]},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"] == "The total contract value is $84,000."
    assert len(data["citations"]) == 1
    assert data["citations"][0]["filename"] == "test.pdf"
    assert data["citations"][0]["page"] == 2
