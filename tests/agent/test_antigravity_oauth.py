"""Tests for the Antigravity CLI OAuth token source."""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolate_home(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    return tmp_path


def _write_antigravity_token(home: Path, *, access_token: str, refresh_token: str, expiry: datetime) -> Path:
    path = home / ".gemini" / "antigravity-cli" / "antigravity-oauth-token"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "auth_method": "consumer",
                "token": {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "token_type": "Bearer",
                    "expiry": expiry.isoformat(),
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def test_load_credentials_reads_antigravity_cli_token_shape(tmp_path):
    from agent.antigravity_oauth import _credentials_path, load_credentials

    expiry = datetime.now(timezone.utc) + timedelta(hours=1)
    token_path = _write_antigravity_token(
        tmp_path,
        access_token="old-access",
        refresh_token="refresh-token",
        expiry=expiry,
    )

    creds = load_credentials()
    assert _credentials_path() == token_path
    assert creds is not None
    assert creds.access_token == "old-access"
    assert creds.refresh_token == "refresh-token"
    assert creds.token_type == "Bearer"
    assert creds.expiry == expiry
    assert creds.access_token_expired() is False


def test_get_valid_access_token_refreshes_and_preserves_refresh_token(monkeypatch, tmp_path):
    from agent import antigravity_oauth

    expired = datetime.now(timezone.utc) - timedelta(minutes=1)
    token_path = _write_antigravity_token(
        tmp_path,
        access_token="expired-access",
        refresh_token="refresh-token",
        expiry=expired,
    )

    monkeypatch.setattr(
        antigravity_oauth,
        "_iter_oauth_client_credentials",
        lambda: iter([("client-id", "client-secret")]),
    )
    monkeypatch.setattr(
        antigravity_oauth,
        "_post_form",
        lambda url, data, timeout: {
            "access_token": "new-access",
            "expires_in": 3600,
            "token_type": "Bearer",
        },
    )

    assert antigravity_oauth.get_valid_access_token() == "new-access"

    saved = json.loads(token_path.read_text(encoding="utf-8"))
    assert saved["auth_method"] == "consumer"
    assert saved["token"]["access_token"] == "new-access"
    assert saved["token"]["refresh_token"] == "refresh-token"


def test_invalid_grant_clears_antigravity_credentials(monkeypatch, tmp_path):
    from agent import antigravity_oauth

    expired = datetime.now(timezone.utc) - timedelta(minutes=1)
    _write_antigravity_token(
        tmp_path,
        access_token="expired-access",
        refresh_token="refresh-token",
        expiry=expired,
    )

    monkeypatch.setattr(
        antigravity_oauth,
        "_iter_oauth_client_credentials",
        lambda: iter([("client-id", "client-secret")]),
    )

    def boom(url, data, timeout):
        raise antigravity_oauth.AntigravityOAuthError(
            "invalid_grant",
            code="antigravity_oauth_invalid_grant",
        )

    monkeypatch.setattr(antigravity_oauth, "_post_form", boom)

    with pytest.raises(antigravity_oauth.AntigravityOAuthError) as exc_info:
        antigravity_oauth.get_valid_access_token()

    assert exc_info.value.code == "antigravity_oauth_invalid_grant"
    assert antigravity_oauth.load_credentials() is None


def test_get_valid_access_token_dedupes_concurrent_refresh(monkeypatch, tmp_path):
    from agent import antigravity_oauth

    expired = datetime.now(timezone.utc) - timedelta(minutes=1)
    _write_antigravity_token(
        tmp_path,
        access_token="expired-access",
        refresh_token="refresh-token",
        expiry=expired,
    )

    monkeypatch.setattr(
        antigravity_oauth,
        "_iter_oauth_client_credentials",
        lambda: iter([("client-id", "client-secret")]),
    )

    calls = []
    entered = threading.Event()
    release = threading.Event()

    def fake_post_form(url, data, timeout):
        calls.append(data["refresh_token"])
        entered.set()
        release.wait(timeout=2)
        return {"access_token": "new-access", "expires_in": 3600}

    monkeypatch.setattr(antigravity_oauth, "_post_form", fake_post_form)

    results = []
    errors = []

    def worker():
        try:
            results.append(antigravity_oauth.get_valid_access_token())
        except Exception as exc:
            errors.append(exc)

    first = threading.Thread(target=worker)
    second = threading.Thread(target=worker)
    first.start()
    assert entered.wait(timeout=1)
    second.start()
    time.sleep(0.1)
    release.set()
    first.join(timeout=2)
    second.join(timeout=2)

    assert errors == []
    assert sorted(results) == ["new-access", "new-access"]
    assert calls == ["refresh-token"]


def test_refresh_preserves_antigravity_token_metadata(monkeypatch, tmp_path):
    from agent import antigravity_oauth

    expired = datetime.now(timezone.utc) - timedelta(minutes=1)
    token_path = _write_antigravity_token(
        tmp_path,
        access_token="expired-access",
        refresh_token="refresh-token",
        expiry=expired,
    )
    original = json.loads(token_path.read_text(encoding="utf-8"))
    original["token"]["client_id"] = "agy-client-id"
    original["token"]["client_secret"] = "agy-client-secret"
    original["token"]["token_url"] = "https://oauth2.googleapis.com/token"
    original["token"]["scope"] = "scope-a scope-b"
    original["extra_top_level"] = {"keep": True}
    token_path.write_text(json.dumps(original), encoding="utf-8")

    monkeypatch.setattr(
        antigravity_oauth,
        "_iter_oauth_client_credentials",
        lambda: iter([("agy-client-id", "agy-client-secret")]),
    )
    monkeypatch.setattr(
        antigravity_oauth,
        "_post_form",
        lambda url, data, timeout: {
            "access_token": "new-access",
            "expires_in": 3600,
            "token_type": "Bearer",
        },
    )

    assert antigravity_oauth.get_valid_access_token() == "new-access"

    saved = json.loads(token_path.read_text(encoding="utf-8"))
    assert saved["token"]["access_token"] == "new-access"
    assert saved["token"]["refresh_token"] == "refresh-token"
    assert saved["token"]["client_id"] == "agy-client-id"
    assert saved["token"]["client_secret"] == "agy-client-secret"
    assert saved["token"]["token_url"] == "https://oauth2.googleapis.com/token"
    assert saved["token"]["scope"] == "scope-a scope-b"
    assert saved["extra_top_level"] == {"keep": True}


def test_missing_credentials_has_actionable_error():
    from agent.antigravity_oauth import AntigravityOAuthError, get_valid_access_token

    with pytest.raises(AntigravityOAuthError) as exc_info:
        get_valid_access_token()

    assert exc_info.value.code == "antigravity_oauth_not_logged_in"
    assert "Run `agy`" in str(exc_info.value)


def test_runtime_credentials_return_antigravity_provider_shape(tmp_path):
    from hermes_cli.auth import resolve_antigravity_oauth_runtime_credentials

    expiry = datetime.now(timezone.utc) + timedelta(hours=1)
    _write_antigravity_token(
        tmp_path,
        access_token="live-antigravity-token",
        refresh_token="refresh-token",
        expiry=expiry,
    )

    creds = resolve_antigravity_oauth_runtime_credentials()
    assert creds["provider"] == "antigravity-cli"
    assert creds["base_url"] == "cloudcode-pa://google"
    assert creds["api_key"] == "live-antigravity-token"
    assert creds["source"] == "antigravity-cli"
    assert creds["expires_at_ms"] == int(expiry.timestamp() * 1000)


def test_auth_status_reports_antigravity_token_store(tmp_path):
    from hermes_cli.auth import get_auth_status

    _write_antigravity_token(
        tmp_path,
        access_token="status-token",
        refresh_token="refresh-token",
        expiry=datetime.now(timezone.utc) + timedelta(hours=1),
    )

    status = get_auth_status("antigravity-cli")
    assert status["logged_in"] is True
    assert status["source"] == "antigravity-cli"
    assert status["api_key"] == "status-token"
    assert Path(status["auth_file"]).parts[-3:] == (
        ".gemini",
        "antigravity-cli",
        "antigravity-oauth-token",
    )


def test_malformed_expiry_is_treated_as_invalid_credentials(tmp_path):
    from agent.antigravity_oauth import load_credentials

    path = tmp_path / ".gemini" / "antigravity-cli" / "antigravity-oauth-token"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "auth_method": "consumer",
                "token": {
                    "access_token": "access-token",
                    "refresh_token": "refresh-token",
                    "token_type": "Bearer",
                    "expiry": "not-a-date",
                },
            }
        ),
        encoding="utf-8",
    )

    assert load_credentials() is None


def test_refresh_tries_later_agy_client_candidate_when_first_fails(monkeypatch):
    from agent import antigravity_oauth

    attempts = []

    monkeypatch.setattr(
        antigravity_oauth,
        "_iter_oauth_client_credentials",
        lambda: iter([
            ("bad-client", "bad-secret"),
            ("good-client", "good-secret"),
        ]),
    )

    def fake_post_form(url, data, timeout):
        attempts.append((data["client_id"], data.get("client_secret")))
        if data["client_id"] == "bad-client":
            raise antigravity_oauth.AntigravityOAuthError(
                "invalid client",
                code="antigravity_oauth_token_http_error",
            )
        return {"access_token": "new-access", "expires_in": 3600}

    monkeypatch.setattr(antigravity_oauth, "_post_form", fake_post_form)

    result = antigravity_oauth.refresh_access_token("refresh-token")
    assert result["access_token"] == "new-access"
    assert attempts == [
        ("bad-client", "bad-secret"),
        ("good-client", "good-secret"),
    ]


def test_refresh_invalid_grant_tries_later_client_candidates(monkeypatch):
    from agent import antigravity_oauth

    attempts = []

    monkeypatch.setattr(
        antigravity_oauth,
        "_iter_oauth_client_credentials",
        lambda: iter([
            ("first-client", "first-secret"),
            ("second-client", "second-secret"),
        ]),
    )

    def fake_post_form(url, data, timeout):
        attempts.append((data["client_id"], data.get("client_secret")))
        if data["client_id"] == "first-client":
            raise antigravity_oauth.AntigravityOAuthError(
                "invalid_grant",
                code="antigravity_oauth_invalid_grant",
            )
        return {"access_token": "new-access", "expires_in": 3600}

    monkeypatch.setattr(antigravity_oauth, "_post_form", fake_post_form)

    result = antigravity_oauth.refresh_access_token("refresh-token")

    assert result["access_token"] == "new-access"
    assert attempts == [
        ("first-client", "first-secret"),
        ("second-client", "second-secret"),
    ]
