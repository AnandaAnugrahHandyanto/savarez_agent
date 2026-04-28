"""Tests for GitHub Code Mode API endpoints."""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest


def _signature(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


@pytest.fixture()
def client():
    try:
        from starlette.testclient import TestClient
    except ImportError:
        pytest.skip("fastapi/starlette not installed")
    from hermes_cli.web_server import app, _SESSION_TOKEN

    c = TestClient(app)
    c.headers["Authorization"] = f"Bearer {_SESSION_TOKEN}"
    return c


def test_github_status_endpoint(client, monkeypatch):
    monkeypatch.delenv("HERMES_GITHUB_APP_ID", raising=False)
    monkeypatch.delenv("HERMES_GITHUB_DEV_PAT", raising=False)

    resp = client.get("/api/code/github/status")

    assert resp.status_code == 200
    assert resp.json()["status"]["mode"] == "unconfigured"


def test_github_repositories_endpoint(client):
    resp = client.get("/api/code/github/repositories")

    assert resp.status_code == 200
    assert resp.json()["repositories"] == []


def test_github_repository_sync_endpoint_dry_run(client, monkeypatch):
    from hermes_cli.code import github_sync

    monkeypatch.setattr(
        github_sync.GitHubSyncService,
        "sync_repositories",
        lambda self, installation_id=None, dry_run=False, limit=100: {
            "dry_run": dry_run,
            "synced": 0,
            "repositories": [],
        },
    )

    resp = client.post("/api/code/github/repositories/sync", json={"dry_run": True})

    assert resp.status_code == 200
    assert resp.json()["result"]["dry_run"] is True


def test_webhook_endpoint_is_public_and_validates_signature(monkeypatch):
    from starlette.testclient import TestClient
    from hermes_cli.web_server import app

    secret = "webhook-secret"
    monkeypatch.setenv("HERMES_GITHUB_WEBHOOK_SECRET", secret)
    payload = {
        "action": "created",
        "repository": {"full_name": "nous/hermes"},
        "issue": {"number": 1},
        "comment": {"id": 10, "body": "@hermes status"},
        "sender": {"login": "octo"},
    }
    body = json.dumps(payload).encode()

    resp = TestClient(app).post(
        "/api/code/github/webhooks",
        content=body,
        headers={
            "X-GitHub-Event": "issue_comment",
            "X-GitHub-Delivery": "delivery-api-1",
            "X-Hub-Signature-256": _signature(secret, body),
        },
    )

    assert resp.status_code == 200
    assert resp.json()["accepted"] is True


def test_comments_endpoint_requires_approval_before_posting(client):
    resp = client.post(
        "/api/code/github/comments",
        json={
            "repo_full_name": "nous/hermes",
            "issue_number": 1,
            "body": "Hermes status update",
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["approval_required"] is True
    assert data["approval"]["kind"] == "github_write"
