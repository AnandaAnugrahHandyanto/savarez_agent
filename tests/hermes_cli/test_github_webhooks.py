"""Tests for GitHub webhook verification and event processing."""

from __future__ import annotations

import hashlib
import hmac
import json


def _signature(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _comment_payload(body: str = "@hermes plan"):
    return {
        "action": "created",
        "repository": {
            "full_name": "nous/hermes",
            "owner": {"login": "nous"},
            "name": "hermes",
        },
        "issue": {"number": 7, "pull_request": {"url": "https://api.github.com/pr"}},
        "comment": {"id": 123, "body": body, "html_url": "https://github.com/nous/hermes/issues/7#issuecomment-123"},
        "sender": {"login": "octo"},
    }


def test_valid_signature_accepted(tmp_path, monkeypatch):
    from hermes_cli.code.github_webhooks import GitHubWebhookService

    secret = "webhook-secret"
    monkeypatch.setenv("HERMES_GITHUB_WEBHOOK_SECRET", secret)
    body = json.dumps(_comment_payload()).encode()

    result = GitHubWebhookService(db_path=tmp_path / "state.db").process(
        delivery_id="delivery-1",
        event="issue_comment",
        body=body,
        signature=_signature(secret, body),
    )

    assert result["accepted"] is True
    assert result["duplicate"] is False
    assert result["chatops_commands"][0]["command"] == "plan"


def test_invalid_signature_rejected(tmp_path, monkeypatch):
    from hermes_cli.code.github_webhooks import GitHubWebhookService, WebhookSignatureError

    monkeypatch.setenv("HERMES_GITHUB_WEBHOOK_SECRET", "webhook-secret")
    body = json.dumps(_comment_payload()).encode()

    try:
        GitHubWebhookService(db_path=tmp_path / "state.db").process(
            delivery_id="delivery-2",
            event="issue_comment",
            body=body,
            signature="sha256=bad",
        )
    except WebhookSignatureError:
        pass
    else:
        raise AssertionError("expected WebhookSignatureError")


def test_missing_signature_rejected(tmp_path, monkeypatch):
    from hermes_cli.code.github_webhooks import GitHubWebhookService, WebhookSignatureError

    monkeypatch.setenv("HERMES_GITHUB_WEBHOOK_SECRET", "webhook-secret")
    body = json.dumps(_comment_payload()).encode()

    try:
        GitHubWebhookService(db_path=tmp_path / "state.db").process(
            delivery_id="delivery-3",
            event="issue_comment",
            body=body,
            signature=None,
        )
    except WebhookSignatureError:
        pass
    else:
        raise AssertionError("expected WebhookSignatureError")


def test_duplicate_delivery_deduped(tmp_path, monkeypatch):
    from hermes_cli.code.github_webhooks import GitHubWebhookService

    secret = "webhook-secret"
    monkeypatch.setenv("HERMES_GITHUB_WEBHOOK_SECRET", secret)
    body = json.dumps(_comment_payload()).encode()
    svc = GitHubWebhookService(db_path=tmp_path / "state.db")

    svc.process("delivery-4", "issue_comment", body, _signature(secret, body))
    duplicate = svc.process("delivery-4", "issue_comment", body, _signature(secret, body))

    assert duplicate["accepted"] is True
    assert duplicate["duplicate"] is True


def test_pull_request_payload_parsed(tmp_path, monkeypatch):
    from hermes_cli.code.github_webhooks import GitHubWebhookService

    secret = "webhook-secret"
    monkeypatch.setenv("HERMES_GITHUB_WEBHOOK_SECRET", secret)
    payload = {
        "action": "opened",
        "repository": {"full_name": "nous/hermes"},
        "pull_request": {"number": 12, "id": 456, "title": "Add thing"},
        "sender": {"login": "octo"},
    }
    body = json.dumps(payload).encode()

    result = GitHubWebhookService(db_path=tmp_path / "state.db").process(
        "delivery-pr",
        "pull_request",
        body,
        _signature(secret, body),
    )

    assert result["normalized"]["repo_full_name"] == "nous/hermes"
    assert result["normalized"]["pr_number"] == 12


def test_unsupported_event_handled_safely(tmp_path, monkeypatch):
    from hermes_cli.code.github_webhooks import GitHubWebhookService

    secret = "webhook-secret"
    monkeypatch.setenv("HERMES_GITHUB_WEBHOOK_SECRET", secret)
    body = json.dumps({"zen": "Keep it logically awesome."}).encode()

    result = GitHubWebhookService(db_path=tmp_path / "state.db").process(
        "delivery-unsupported",
        "ping",
        body,
        _signature(secret, body),
    )

    assert result["accepted"] is True
    assert result["status"] == "ignored"
    assert "webhook-secret" not in str(result)
