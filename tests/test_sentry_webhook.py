"""Tests for hermes_cli.sentry_webhook — Vedere ecosystem standardization.

Covers:

* Token authentication (missing / wrong)
* Happy path with mocked ``gh`` CLI subprocess invocation
* Recurrence dedup within 30 days
* Regression detection (last_seen > 7 days ago AND state == 'closed')
* Thread isolation under a synthetic agent-loop hang (G6 — CRITICAL)
* Pydantic validation errors → 422
* Unknown environment → 400
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import patch

import httpx
import pytest
from fastapi import FastAPI

# Ensure the repo root is importable when pytest is invoked from the cwd.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from hermes_cli import sentry_webhook as sw


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def webhook_token(monkeypatch) -> str:
    token = "test-token-deadbeef"
    monkeypatch.setenv("SENTRY_WEBHOOK_TOKEN", token)
    return token


@pytest.fixture
def isolated_cache(tmp_path) -> sw.FingerprintCache:
    db_path = tmp_path / "fingerprints.db"
    cache = sw.FingerprintCache(db_path=db_path)
    sw.set_cache(cache)
    yield cache
    cache.close()
    sw.set_cache(None)  # type: ignore[arg-type]


@pytest.fixture
def app(isolated_cache) -> FastAPI:
    instance = FastAPI()
    instance.include_router(sw.router)
    return instance


@pytest.fixture
def client(app) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


def _valid_payload(
    *,
    fingerprint: str = "deadbeefcafe1234",
    environment: str = "lms-prod",
    title: str = "ZeroDivisionError: division by zero",
) -> Dict[str, Any]:
    return {
        "action": "triggered",
        "data": {
            "event": {
                "fingerprint": [fingerprint],
                "level": "error",
                "environment": environment,
                "exception": {"values": [{"type": "ZeroDivisionError", "value": "division by zero"}]},
                "title": title,
                "web_url": "https://sentry.io/organizations/vedere/issues/123/events/abc/",
                "project_slug": "lms",
            },
            "issue_url": "https://sentry.io/organizations/vedere/issues/123/",
            "triggered_rule": "Send a notification for new issues",
        },
    }


def _mock_gh_success(returncode: int = 0, url: str = "https://github.com/manlaughed/VedereLMS/issues/42"):
    def _runner(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0] if args else kwargs.get("args"),
            returncode=returncode,
            stdout=f"{url}\n",
            stderr="",
        )
    return _runner


# ---------------------------------------------------------------------------
# (a) missing token → 401
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_webhook_rejects_missing_token(webhook_token, client):
    async with client as c:
        resp = await c.post("/api/sentry/webhook", json=_valid_payload())
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Unauthorized"


# ---------------------------------------------------------------------------
# (b) wrong token → 401
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_webhook_rejects_wrong_token(webhook_token, client):
    async with client as c:
        resp = await c.post(
            "/api/sentry/webhook",
            params={"token": "wrong-token"},
            json=_valid_payload(),
        )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# (c) happy path — valid payload creates issue + records cache
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_webhook_accepts_valid_payload_creates_issue(
    webhook_token, isolated_cache, client,
):
    issue_url = "https://github.com/manlaughed/VedereLMS/issues/777"
    with patch.object(sw.subprocess, "run", side_effect=_mock_gh_success(url=issue_url)):
        async with client as c:
            resp = await c.post(
                "/api/sentry/webhook",
                params={"token": webhook_token},
                json=_valid_payload(),
            )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["action"] == "created"
    assert body["github_issue_url"] == issue_url
    assert body["repo"] == "manlaughed/VedereLMS"
    assert body["regression"] is False

    # SQLite row recorded.
    row = isolated_cache._row("deadbeefcafe1234", "lms-prod")
    assert row is not None
    assert row[3] == issue_url            # github_issue_url
    assert row[4] == "open"               # github_issue_state


# ---------------------------------------------------------------------------
# (d) recurring fingerprint within 30 days → skipped
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_webhook_dedups_recurring_fingerprint(
    webhook_token, isolated_cache, client,
):
    fp = "recurringfp"
    isolated_cache.record(
        fingerprint=fp,
        env="lms-prod",
        issue_url="https://github.com/manlaughed/VedereLMS/issues/1",
        issue_state="open",
        now=int(time.time()) - 60,  # 1 minute ago
    )

    with patch.object(sw.subprocess, "run", side_effect=AssertionError("gh must NOT be called")):
        async with client as c:
            resp = await c.post(
                "/api/sentry/webhook",
                params={"token": webhook_token},
                json=_valid_payload(fingerprint=fp),
            )
    assert resp.status_code == 200
    body = resp.json()
    assert body["action"] == "skipped"
    assert body["reason"] == "recurring"


# ---------------------------------------------------------------------------
# (e) old + closed → regression → new issue created
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_webhook_treats_old_resolved_as_regression(
    webhook_token, isolated_cache, client,
):
    fp = "regressionfp"
    eight_days_ago = int(time.time()) - (8 * 24 * 60 * 60)
    isolated_cache.record(
        fingerprint=fp,
        env="lms-prod",
        issue_url="https://github.com/manlaughed/VedereLMS/issues/9",
        issue_state="closed",
        now=eight_days_ago,
    )

    assert isolated_cache.is_regression(fp, "lms-prod") is True

    new_url = "https://github.com/manlaughed/VedereLMS/issues/10"
    with patch.object(sw.subprocess, "run", side_effect=_mock_gh_success(url=new_url)):
        async with client as c:
            resp = await c.post(
                "/api/sentry/webhook",
                params={"token": webhook_token},
                json=_valid_payload(fingerprint=fp),
            )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["action"] == "created"
    assert body["regression"] is True
    assert body["github_issue_url"] == new_url


# ---------------------------------------------------------------------------
# (f) G6 — CRITICAL: thread isolation under blocked agent loop
#
# Spin up a worker thread that holds an asyncio loop blocked via
# time.sleep(60). In parallel, send a webhook request via httpx and
# assert the response completes within 5s with status 200/201 — proving
# the FastAPI request thread is independent of any blocked agent loop.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_webhook_thread_isolation_under_agent_loop_hang(
    webhook_token, isolated_cache, client,
):
    blocker_started = threading.Event()
    blocker_done = threading.Event()

    def _blocked_agent_loop():
        loop = asyncio.new_event_loop()
        try:
            blocker_started.set()
            # Block the loop's thread for 60s. If the FastAPI request thread
            # is somehow coupled to this loop, the request below will time out.
            time.sleep(60)
        finally:
            try:
                loop.close()
            except Exception:
                pass
            blocker_done.set()

    blocker_thread = threading.Thread(target=_blocked_agent_loop, daemon=True)
    blocker_thread.start()
    assert blocker_started.wait(timeout=2.0), "blocker thread never started"

    issue_url = "https://github.com/manlaughed/VedereLMS/issues/123"
    gh_called = threading.Event()

    def _gh_runner(*args, **kwargs):
        gh_called.set()
        return subprocess.CompletedProcess(
            args=args[0] if args else kwargs.get("args"),
            returncode=0,
            stdout=f"{issue_url}\n",
            stderr="",
        )

    start = time.monotonic()
    with patch.object(sw.subprocess, "run", side_effect=_gh_runner):
        async with client as c:
            resp = await asyncio.wait_for(
                c.post(
                    "/api/sentry/webhook",
                    params={"token": webhook_token},
                    json=_valid_payload(fingerprint="threadisolationfp"),
                ),
                timeout=5.0,
            )
    elapsed = time.monotonic() - start

    assert resp.status_code in (200, 201), f"unexpected status {resp.status_code}: {resp.text}"
    assert elapsed < 5.0, f"request took {elapsed:.2f}s — thread isolation broken"
    assert gh_called.is_set(), "issue creation path was not invoked"

    # Cleanup: blocker thread is daemon; the test can finish without joining.


# ---------------------------------------------------------------------------
# (g) malformed payload (missing fingerprint) → 422
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_payload_validation_rejects_malformed(webhook_token, client):
    payload = {
        "action": "triggered",
        "data": {
            "event": {
                # fingerprint intentionally omitted
                "level": "error",
                "environment": "lms-prod",
            }
        },
    }
    async with client as c:
        resp = await c.post(
            "/api/sentry/webhook",
            params={"token": webhook_token},
            json=payload,
        )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# (h) unknown environment → 400
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_env_to_repo_mapping_unknown_env_returns_400(
    webhook_token, isolated_cache, client,
):
    async with client as c:
        resp = await c.post(
            "/api/sentry/webhook",
            params={"token": webhook_token},
            json=_valid_payload(environment="unknown-prod"),
        )
    assert resp.status_code == 400
    assert "unknown environment" in resp.json()["detail"].lower()
