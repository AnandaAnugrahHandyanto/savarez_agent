"""API tests for /api/code/github/* endpoints."""

from __future__ import annotations

import hashlib
import hmac
import json
import time

import pytest


def _signature(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


@pytest.fixture()
def clients(monkeypatch, _isolate_hermes_home):
    from starlette.testclient import TestClient
    import hermes_state
    from hermes_constants import get_hermes_home
    from hermes_cli.web_server import app, _SESSION_HEADER_NAME, _SESSION_TOKEN

    monkeypatch.setattr(hermes_state, "DEFAULT_DB_PATH", get_hermes_home() / "state.db")
    auth_client = TestClient(app)
    auth_client.headers[_SESSION_HEADER_NAME] = _SESSION_TOKEN
    unauth_client = TestClient(app)
    return auth_client, unauth_client


def test_github_status_endpoint(clients):
    auth, _unauth = clients
    resp = auth.get("/api/code/github/status")
    assert resp.status_code == 200
    assert "status" in resp.json()
    assert "mode" in resp.json()["status"]


def test_github_repositories_endpoint(clients, tmp_path):
    auth, _unauth = clients
    from hermes_state import SessionDB

    db = SessionDB()
    try:
        now = time.time()
        db._conn.execute(
            """
            INSERT INTO github_repositories
                (id, installation_id, github_repo_id, owner, name, full_name, default_branch, private,
                 html_url, clone_url, ssh_url, archived, disabled, pushed_at, created_at, updated_at, last_synced_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "gr-1",
                11,
                22,
                "acme",
                "repo",
                "acme/repo",
                "main",
                0,
                "https://github.com/acme/repo",
                "https://github.com/acme/repo.git",
                "git@github.com:acme/repo.git",
                0,
                0,
                None,
                now,
                now,
                now,
            ),
        )
        db._conn.commit()
    finally:
        db.close()

    resp = auth.get("/api/code/github/repositories")
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


def test_github_repositories_sync_endpoint(monkeypatch, clients):
    auth, _unauth = clients
    from hermes_cli.code.github_sync import GitHubSyncService

    monkeypatch.setattr(
        GitHubSyncService,
        "sync_repositories",
        lambda self, installation_id=None, dry_run=False, limit=100: {"dry_run": dry_run, "synced": 1, "repositories": [{"full_name": "acme/repo"}]},
    )
    resp = auth.post("/api/code/github/repositories/sync", json={"dry_run": True, "limit": 5})
    assert resp.status_code == 200
    assert resp.json()["result"]["dry_run"] is True


def test_github_webhook_endpoint_signature_validation(monkeypatch, clients):
    _auth, unauth = clients
    monkeypatch.setenv("HERMES_GITHUB_WEBHOOK_SECRET", "secret")
    payload = {"repository": {"full_name": "acme/repo"}}
    body = json.dumps(payload).encode("utf-8")

    bad = unauth.post(
        "/api/code/github/webhooks",
        data=body,
        headers={
            "X-GitHub-Event": "push",
            "X-GitHub-Delivery": "deliv-1",
            "X-Hub-Signature-256": "sha256=deadbeef",
        },
    )
    assert bad.status_code == 401

    ok = unauth.post(
        "/api/code/github/webhooks",
        data=body,
        headers={
            "X-GitHub-Event": "push",
            "X-GitHub-Delivery": "deliv-2",
            "X-Hub-Signature-256": _signature("secret", body),
        },
    )
    assert ok.status_code == 200
    assert ok.json()["accepted"] is True


def test_github_comments_endpoint_approval_flow(monkeypatch, clients):
    auth, _unauth = clients
    from hermes_cli.code.github_integration import GitHubIntegrationService

    monkeypatch.setattr(
        GitHubIntegrationService,
        "post_issue_comment",
        lambda self, repo_full_name, issue_number, body, installation_id=None: {"id": 1, "body": body},
    )

    pending = auth.post(
        "/api/code/github/comments",
        json={
            "repo_full_name": "acme/repo",
            "issue_number": 7,
            "body": "hello",
            "approved": False,
        },
    )
    assert pending.status_code == 200
    assert pending.json()["approval_required"] is True

    approved = auth.post(
        "/api/code/github/comments",
        json={
            "repo_full_name": "acme/repo",
            "issue_number": 7,
            "body": "hello",
            "approved": True,
        },
    )
    assert approved.status_code == 200
    assert approved.json()["approval_required"] is False


def test_github_pull_request_prepare_endpoint(clients):
    auth, _unauth = clients
    resp = auth.post(
        "/api/code/github/pull-requests/prepare",
        json={
            "repo_full_name": "acme/repo",
            "title": "feat: x",
            "head": "feature/x",
            "base": "main",
            "body": "desc",
        },
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["prepared"]["auto_push"] is False
    assert payload["prepared"]["auto_merge"] is False
