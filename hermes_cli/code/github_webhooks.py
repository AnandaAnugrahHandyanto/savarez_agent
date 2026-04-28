#!/usr/bin/env python3
"""GitHub webhook verification and event normalization."""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from typing import Any, Dict, Optional

from hermes_cli.code.github_chatops import GitHubChatOpsService
from hermes_cli.code.github_integration import GitHubIntegrationDB, _env_value, redact_github_secrets

SUPPORTED_EVENTS = frozenset(
    {
        "installation",
        "installation_repositories",
        "issues",
        "issue_comment",
        "pull_request",
        "pull_request_review",
        "pull_request_review_comment",
        "check_suite",
        "check_run",
        "push",
    }
)


class WebhookSignatureError(ValueError):
    """Raised when a GitHub webhook signature is missing or invalid."""


def verify_signature(secret: str, body: bytes, signature: Optional[str]) -> bool:
    if not secret:
        raise WebhookSignatureError("GitHub webhook secret is not configured")
    if not signature or not signature.startswith("sha256="):
        raise WebhookSignatureError("Missing GitHub webhook signature")
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise WebhookSignatureError("Invalid GitHub webhook signature")
    return True


def _payload_hash(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _normalize(event: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    repo = payload.get("repository") if isinstance(payload.get("repository"), dict) else {}
    sender = payload.get("sender") if isinstance(payload.get("sender"), dict) else {}
    issue = payload.get("issue") if isinstance(payload.get("issue"), dict) else {}
    pr = payload.get("pull_request") if isinstance(payload.get("pull_request"), dict) else {}
    comment = payload.get("comment") if isinstance(payload.get("comment"), dict) else {}
    review = payload.get("review") if isinstance(payload.get("review"), dict) else {}

    repo_full_name = repo.get("full_name")
    issue_number = issue.get("number")
    pr_number = pr.get("number")
    if event in {"issue_comment", "issues"} and issue.get("pull_request"):
        pr_number = issue_number

    return {
        "event": event,
        "action": payload.get("action"),
        "repo_full_name": repo_full_name,
        "sender_login": sender.get("login"),
        "issue_number": issue_number,
        "pr_number": pr_number,
        "comment_id": comment.get("id"),
        "comment_body": comment.get("body") or "",
        "review_id": review.get("id"),
        "github_ids": {
            "repository": repo.get("id"),
            "issue": issue.get("id"),
            "pull_request": pr.get("id"),
            "comment": comment.get("id"),
        },
    }


class GitHubWebhookService:
    """Validate, persist, dedupe, and normalize GitHub webhook deliveries."""

    def __init__(self, db_path: Optional[Path] = None, realtime_hub=None) -> None:
        self._db_path = db_path
        self._realtime_hub = realtime_hub

    def _db(self) -> GitHubIntegrationDB:
        return GitHubIntegrationDB(db_path=self._db_path)

    def process(
        self,
        delivery_id: str,
        event: str,
        body: bytes,
        signature: Optional[str],
    ) -> Dict[str, Any]:
        secret = _env_value("HERMES_GITHUB_WEBHOOK_SECRET").strip()
        verify_signature(secret, body, signature)
        payload_sha = _payload_hash(body)

        db = self._db()
        try:
            existing = db.get_delivery(delivery_id)
            if existing:
                return {
                    "accepted": True,
                    "duplicate": True,
                    "status": existing.get("status"),
                    "delivery": existing,
                    "chatops_commands": [],
                }

            try:
                payload = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError as exc:
                db.record_webhook_delivery(
                    delivery_id=delivery_id,
                    event=event,
                    action=None,
                    repo_full_name=None,
                    sender_login=None,
                    payload_hash=payload_sha,
                    status="error",
                    error="Invalid JSON payload",
                )
                raise ValueError("Invalid GitHub webhook JSON") from exc

            normalized = _normalize(event, payload if isinstance(payload, dict) else {})
            if event not in SUPPORTED_EVENTS:
                delivery = db.record_webhook_delivery(
                    delivery_id=delivery_id,
                    event=event,
                    action=normalized.get("action"),
                    repo_full_name=normalized.get("repo_full_name"),
                    sender_login=normalized.get("sender_login"),
                    payload_hash=payload_sha,
                    status="ignored",
                )
                return {
                    "accepted": True,
                    "duplicate": False,
                    "status": "ignored",
                    "delivery": delivery,
                    "normalized": normalized,
                    "chatops_commands": [],
                }

            delivery = db.record_webhook_delivery(
                delivery_id=delivery_id,
                event=event,
                action=normalized.get("action"),
                repo_full_name=normalized.get("repo_full_name"),
                sender_login=normalized.get("sender_login"),
                payload_hash=payload_sha,
                status="processed",
            )
        finally:
            db.close()

        commands = []
        if event in {"issue_comment", "pull_request_review_comment"} and normalized.get("comment_body"):
            commands = GitHubChatOpsService(db_path=self._db_path, realtime_hub=self._realtime_hub).create_commands_from_comment(
                delivery_id=delivery_id,
                repo_full_name=normalized.get("repo_full_name") or "",
                issue_number=normalized.get("issue_number"),
                pr_number=normalized.get("pr_number"),
                comment_id=normalized.get("comment_id"),
                sender_login=normalized.get("sender_login"),
                body=normalized.get("comment_body") or "",
            )

        return {
            "accepted": True,
            "duplicate": False,
            "status": "processed",
            "delivery": delivery,
            "normalized": normalized,
            "chatops_commands": commands,
        }

    @staticmethod
    def safe_error(exc: Exception) -> str:
        return redact_github_secrets(str(exc))
