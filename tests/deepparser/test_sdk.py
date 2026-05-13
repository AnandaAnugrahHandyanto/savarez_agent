"""SDK client: parse_and_ask, polling, debug logging, DeprecationWarning."""
from __future__ import annotations

import io
import sys
import warnings

import pytest
import respx
from httpx import Response

from deepparser import DeepParserClient
from deepparser.exceptions import (
    AuthError,
    JobNotFoundError,
    ParseFailedError,
    ParseTimeoutError,
    RateLimitError,
)
from deepparser.models import AskResult, ParseJob

pytestmark = pytest.mark.asyncio

BASE = "http://fake-server"
KEY = "dp_live_testkey123456789012345678"


# ---------------------------------------------------------------------------
# register_key
# ---------------------------------------------------------------------------

async def test_register_key() -> None:
    with respx.mock(base_url=BASE) as mock:
        mock.post("/keys").mock(
            return_value=Response(
                200, json={"api_key": "dp_live_abc", "created_at": "2026-01-01 00:00:00"}
            )
        )
        info = await DeepParserClient.register_key(
            "test@example.com", base_url=BASE
        )
    assert info.api_key == "dp_live_abc"
    assert info.created_at == "2026-01-01 00:00:00"


# ---------------------------------------------------------------------------
# parse
# ---------------------------------------------------------------------------

async def test_parse_returns_queued() -> None:
    with respx.mock(base_url=BASE) as mock:
        mock.post("/parse").mock(
            return_value=Response(
                200, json={"job_id": "job-1", "status": "QUEUED"}
            )
        )
        async with DeepParserClient(api_key=KEY, base_url=BASE) as client:
            job = await client.parse(io.BytesIO(b"%PDF"), filename="test.pdf")

    assert job.job_id == "job-1"
    assert job.status == "QUEUED"


async def test_parse_sync_returns_ready() -> None:
    with respx.mock(base_url=BASE) as mock:
        mock.post("/parse").mock(
            return_value=Response(
                200,
                json={
                    "job_id": "job-2",
                    "status": "READY",
                    "result": {
                        "file_id": "f-abc",
                        "folder_id": "fld-1",
                        "file_name": "test.pdf",
                        "extension": "pdf",
                    },
                },
            )
        )
        async with DeepParserClient(api_key=KEY, base_url=BASE) as client:
            job = await client.parse(b"%PDF content", filename="test.pdf", sync=True)

    assert job.status == "READY"
    assert job.result.file_id == "f-abc"


# ---------------------------------------------------------------------------
# wait_until_ready
# ---------------------------------------------------------------------------

async def test_wait_until_ready_polls_until_ready(monkeypatch) -> None:
    calls = 0

    def _status_response(request):
        nonlocal calls
        calls += 1
        status = "PARSING" if calls < 3 else "READY"
        result = (
            {"file_id": "f-1", "folder_id": "fld-1", "file_name": "x.pdf", "extension": "pdf"}
            if status == "READY"
            else None
        )
        return Response(
            200,
            json={
                "job_id": "job-3",
                "status": status,
                "created_at": "2026-01-01",
                "result": result,
            },
        )

    # Speed up polling in tests
    monkeypatch.setattr("deepparser.client._POLL_INTERVAL_INIT", 0.01)

    with respx.mock(base_url=BASE) as mock:
        mock.get("/parse/job-3").mock(side_effect=_status_response)
        async with DeepParserClient(api_key=KEY, base_url=BASE) as client:
            job = await client.wait_until_ready("job-3")

    assert job.status == "READY"
    assert calls == 3


async def test_wait_until_ready_raises_parse_failed(monkeypatch) -> None:
    monkeypatch.setattr("deepparser.client._POLL_INTERVAL_INIT", 0.01)

    with respx.mock(base_url=BASE) as mock:
        mock.get("/parse/job-fail").mock(
            return_value=Response(
                200,
                json={
                    "job_id": "job-fail",
                    "status": "PARSE_FAILED",
                    "created_at": "2026-01-01",
                    "error_detail": "dp exit 1: connection refused",
                },
            )
        )
        async with DeepParserClient(api_key=KEY, base_url=BASE) as client:
            with pytest.raises(ParseFailedError) as exc_info:
                await client.wait_until_ready("job-fail")

    assert "dp exit 1" in exc_info.value.detail


async def test_wait_until_ready_raises_timeout(monkeypatch) -> None:
    monkeypatch.setattr("deepparser.client._POLL_INTERVAL_INIT", 0.01)

    with respx.mock(base_url=BASE) as mock:
        mock.get("/parse/job-to").mock(
            return_value=Response(
                200,
                json={
                    "job_id": "job-to",
                    "status": "TIMEOUT",
                    "created_at": "2026-01-01",
                },
            )
        )
        async with DeepParserClient(api_key=KEY, base_url=BASE) as client:
            with pytest.raises(ParseTimeoutError):
                await client.wait_until_ready("job-to")


# ---------------------------------------------------------------------------
# ask
# ---------------------------------------------------------------------------

async def test_ask_returns_result() -> None:
    with respx.mock(base_url=BASE) as mock:
        mock.post("/ask").mock(
            return_value=Response(
                200,
                json={
                    "job_id": "job-1",
                    "answer": "The total is $84,000.",
                    "citations": [{"filename": "test.pdf", "page": 2, "cell": None}],
                },
            )
        )
        async with DeepParserClient(api_key=KEY, base_url=BASE) as client:
            result = await client.ask("job-1", "What is the total?")

    assert isinstance(result, AskResult)
    assert result.answer == "The total is $84,000."
    assert result.citations[0].page == 2


# ---------------------------------------------------------------------------
# parse_and_ask convenience
# ---------------------------------------------------------------------------

async def test_parse_and_ask_ready_on_first_try() -> None:
    with respx.mock(base_url=BASE) as mock:
        mock.post("/parse").mock(
            return_value=Response(
                200,
                json={
                    "job_id": "j1",
                    "status": "READY",
                    "result": {
                        "file_id": "f-1",
                        "folder_id": "fld-1",
                        "file_name": "invoice.pdf",
                        "extension": "pdf",
                    },
                },
            )
        )
        mock.post("/ask").mock(
            return_value=Response(
                200,
                json={"job_id": "j1", "answer": "Net 30 days.", "citations": []},
            )
        )
        async with DeepParserClient(api_key=KEY, base_url=BASE) as client:
            result = await client.parse_and_ask(
                b"%PDF-1.4 invoice", "What are the payment terms?", filename="invoice.pdf"
            )

    assert result.answer == "Net 30 days."


# ---------------------------------------------------------------------------
# Error mapping
# ---------------------------------------------------------------------------

async def test_auth_error_on_401() -> None:
    with respx.mock(base_url=BASE) as mock:
        mock.post("/parse").mock(
            return_value=Response(
                401,
                json={"detail": {"code": "INVALID_API_KEY", "message": "Bad key"}},
            )
        )
        async with DeepParserClient(api_key=KEY, base_url=BASE) as client:
            with pytest.raises(AuthError):
                await client.parse(b"%PDF", filename="t.pdf")


async def test_rate_limit_error_on_429() -> None:
    with respx.mock(base_url=BASE) as mock:
        mock.post("/parse").mock(
            return_value=Response(
                429,
                json={"detail": {"code": "RATE_LIMITED", "message": "Slow down"}},
            )
        )
        async with DeepParserClient(api_key=KEY, base_url=BASE) as client:
            with pytest.raises(RateLimitError):
                await client.parse(b"%PDF", filename="t.pdf")


# ---------------------------------------------------------------------------
# debug=True logs to stderr
# ---------------------------------------------------------------------------

async def test_debug_logs_to_stderr(capsys) -> None:
    with respx.mock(base_url=BASE) as mock:
        mock.get("/parse/job-dbg").mock(
            return_value=Response(
                200,
                json={
                    "job_id": "job-dbg",
                    "status": "READY",
                    "created_at": "2026-01-01",
                    "result": {
                        "file_id": "f-1",
                        "folder_id": "fld-1",
                        "file_name": "x.pdf",
                        "extension": "pdf",
                    },
                },
            )
        )
        async with DeepParserClient(api_key=KEY, base_url=BASE, debug=True) as client:
            await client.get_status("job-dbg")

    captured = capsys.readouterr()
    assert "[deepparser]" in captured.err
    assert "GET" in captured.err
    assert "200" in captured.err


# ---------------------------------------------------------------------------
# DeprecationWarning on Deepparser-Deprecation header
# ---------------------------------------------------------------------------

async def test_deprecation_warning_on_header() -> None:
    with respx.mock(base_url=BASE) as mock:
        mock.get("/parse/job-dep").mock(
            return_value=Response(
                200,
                headers={"Deepparser-Deprecation": "GET /parse/{id} deprecated in v2.0"},
                json={
                    "job_id": "job-dep",
                    "status": "READY",
                    "created_at": "2026-01-01",
                    "result": {
                        "file_id": "f-1",
                        "folder_id": "fld-1",
                        "file_name": "x.pdf",
                        "extension": "pdf",
                    },
                },
            )
        )
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            async with DeepParserClient(api_key=KEY, base_url=BASE) as client:
                await client.get_status("job-dep")

    assert any(issubclass(warning.category, DeprecationWarning) for warning in w)
    assert any("deprecated in v2.0" in str(warning.message) for warning in w)


# ---------------------------------------------------------------------------
# No context manager raises RuntimeError
# ---------------------------------------------------------------------------

async def test_no_context_manager_raises() -> None:
    client = DeepParserClient(api_key=KEY, base_url=BASE)
    with pytest.raises(RuntimeError, match="async context manager"):
        await client.get_status("job-x")
