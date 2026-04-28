"""Tests for the Hermes GitHub integration service."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


class _Response:
    def __init__(self, status_code=200, json_data=None, headers=None, text=""):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.headers = headers or {}
        self.text = text

    def json(self):
        return self._json_data


class _HttpClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)


def test_unconfigured_status_does_not_leak_secrets(tmp_path, monkeypatch):
    from hermes_cli.code.github_integration import GitHubIntegrationService

    for key in (
        "HERMES_GITHUB_APP_ID",
        "HERMES_GITHUB_APP_PRIVATE_KEY_PATH",
        "HERMES_GITHUB_WEBHOOK_SECRET",
        "HERMES_GITHUB_DEV_PAT",
        "HERMES_GITHUB_ALLOW_DEV_PAT",
    ):
        monkeypatch.delenv(key, raising=False)

    status = GitHubIntegrationService(db_path=tmp_path / "state.db").status()

    assert status["mode"] == "unconfigured"
    assert status["configured"] is False
    assert "secret-value" not in str(status)


def test_github_app_config_detection_without_secret_leak(tmp_path, monkeypatch):
    from hermes_cli.code.github_integration import GitHubIntegrationService

    key_path = tmp_path / "github-app.pem"
    key_path.write_text("private-key-secret-value")
    monkeypatch.setenv("HERMES_GITHUB_APP_ID", "12345")
    monkeypatch.setenv("HERMES_GITHUB_APP_PRIVATE_KEY_PATH", str(key_path))
    monkeypatch.setenv("HERMES_GITHUB_WEBHOOK_SECRET", "webhook-secret-value")

    status = GitHubIntegrationService(db_path=tmp_path / "state.db").status()

    assert status["mode"] == "github_app"
    assert status["configured"] is True
    assert status["app_id_configured"] is True
    assert status["private_key_configured"] is True
    assert status["webhook_secret_configured"] is True
    assert "private-key-secret-value" not in str(status)
    assert "webhook-secret-value" not in str(status)


def test_pat_dev_fallback_requires_explicit_gate(tmp_path, monkeypatch):
    from hermes_cli.code.github_integration import GitHubIntegrationService

    monkeypatch.setenv("HERMES_GITHUB_DEV_PAT", "ghp_secret_token_value")
    monkeypatch.delenv("HERMES_GITHUB_ALLOW_DEV_PAT", raising=False)
    svc = GitHubIntegrationService(db_path=tmp_path / "state.db")
    assert svc.status()["mode"] == "unconfigured"

    monkeypatch.setenv("HERMES_GITHUB_ALLOW_DEV_PAT", "1")
    status = GitHubIntegrationService(db_path=tmp_path / "state.db").status()
    assert status["mode"] == "pat_dev"
    assert status["configured"] is True
    assert "ghp_secret_token_value" not in str(status)


def test_installation_token_cache_uses_expiry_metadata(tmp_path, monkeypatch):
    from hermes_cli.code.github_integration import GitHubIntegrationService

    expires = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
    svc = GitHubIntegrationService(db_path=tmp_path / "state.db")
    calls = {"count": 0}

    def fake_request(installation_id):
        calls["count"] += 1
        return {"token": f"token-{calls['count']}", "expires_at": expires}

    monkeypatch.setattr(svc, "_request_installation_token", fake_request)

    assert svc.get_installation_token(99) == "token-1"
    assert svc.get_installation_token(99) == "token-1"
    assert calls["count"] == 1


def test_api_error_normalization_and_redaction():
    from hermes_cli.code.github_integration import GitHubAPIClient, GitHubAPIError

    http = _HttpClient([
        _Response(
            status_code=403,
            json_data={"message": "Bad credentials for ghp_secret_token_value"},
            headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": "123"},
        )
    ])
    client = GitHubAPIClient(lambda: "ghp_secret_token_value", http_client=http)

    try:
        client.request("GET", "/rate_limit")
    except GitHubAPIError as exc:
        assert exc.status_code == 403
        assert exc.rate_limit["remaining"] == "0"
        assert "ghp_secret_token_value" not in exc.message
    else:
        raise AssertionError("expected GitHubAPIError")


def test_rate_limit_metadata_captured_on_success():
    from hermes_cli.code.github_integration import GitHubAPIClient

    http = _HttpClient([
        _Response(
            status_code=200,
            json_data={"ok": True},
            headers={"x-ratelimit-remaining": "42", "x-ratelimit-reset": "999"},
        )
    ])
    client = GitHubAPIClient(lambda: "token", http_client=http)

    result = client.request("GET", "/meta")

    assert result["data"] == {"ok": True}
    assert result["rate_limit"]["remaining"] == "42"
