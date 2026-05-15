import base64
import json
import time
from pathlib import Path

import pytest

from hermes_cli.auth import (
    AuthError,
    PROVIDER_REGISTRY,
    get_auth_status,
    get_openai_oauth_auth_status,
    resolve_openai_oauth_runtime_credentials,
)


def _jwt_with_exp(exp_epoch: int) -> str:
    header = base64.urlsafe_b64encode(json.dumps({"alg": "RS256", "typ": "JWT"}).encode()).decode().rstrip("=")
    payload = base64.urlsafe_b64encode(
        json.dumps(
            {
                "exp": exp_epoch,
                "https://api.openai.com/auth": {"chatgpt_account_id": "acct-test-123"},
            }
        ).encode()
    ).decode().rstrip("=")
    return f"{header}.{payload}.sig"


def test_provider_registry_contains_openai_oauth():
    assert "openai-oauth" in PROVIDER_REGISTRY
    cfg = PROVIDER_REGISTRY["openai-oauth"]
    assert cfg.auth_type == "oauth_external"
    assert cfg.inference_base_url == "https://api.openai.com/v1"


def test_openai_oauth_auth_path_falls_back_to_home_brian(monkeypatch, tmp_path):
    import hermes_cli.auth as auth_mod

    mounted = tmp_path / "home" / "brian" / ".local" / "share" / "opencode"
    mounted.mkdir(parents=True)
    auth_file = mounted / "auth.json"
    auth_file.write_text("{}", encoding="utf-8")

    monkeypatch.delenv("HERMES_OPENAI_OAUTH_AUTH_PATH", raising=False)
    monkeypatch.setattr(auth_mod.Path, "home", lambda: Path("/root"))

    original_exists = auth_mod.Path.exists

    def _exists(self):
        if str(self) == "/home/brian/.local/share/opencode/auth.json":
            return True
        if str(self) == "/root/.local/share/opencode/auth.json":
            return False
        return original_exists(self)

    monkeypatch.setattr(auth_mod.Path, "exists", _exists, raising=False)

    assert auth_mod._openai_oauth_auth_path() == Path("/home/brian/.local/share/opencode/auth.json")


def test_resolve_openai_oauth_runtime_credentials_reads_auth_file(tmp_path, monkeypatch):
    auth_path = tmp_path / "opencode-auth.json"
    auth_path.write_text(
        json.dumps(
            {
                "openai": {
                    "type": "oauth",
                    "access": _jwt_with_exp(int(time.time()) + 3600),
                    "refresh": "refresh-token",
                    "expires": int((time.time() + 3600) * 1000),
                    "accountId": "acct-file-456",
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_OPENAI_OAUTH_AUTH_PATH", str(auth_path))

    creds = resolve_openai_oauth_runtime_credentials(refresh_if_expiring=False)

    assert creds["provider"] == "openai-oauth"
    assert creds["base_url"] == "https://api.openai.com/v1"
    assert creds["source"] == "opencode-auth"
    assert creds["account_id"] == "acct-file-456"
    assert creds["auth_file"] == str(auth_path)
    assert creds["refresh_token"] == "refresh-token"


def test_resolve_openai_oauth_runtime_credentials_rejects_expiring_token(tmp_path, monkeypatch):
    auth_path = tmp_path / "opencode-auth.json"
    auth_path.write_text(
        json.dumps(
            {
                "openai": {
                    "type": "oauth",
                    "access": _jwt_with_exp(int(time.time()) - 10),
                    "refresh": "refresh-token",
                    "expires": int((time.time() - 10) * 1000),
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_OPENAI_OAUTH_AUTH_PATH", str(auth_path))

    with pytest.raises(AuthError) as exc_info:
        resolve_openai_oauth_runtime_credentials()

    assert exc_info.value.code == "openai_oauth_token_expired"
    assert exc_info.value.relogin_required is True


def test_get_openai_oauth_auth_status_dispatches(tmp_path, monkeypatch):
    auth_path = tmp_path / "opencode-auth.json"
    auth_path.write_text(
        json.dumps(
            {
                "openai": {
                    "type": "oauth",
                    "access": _jwt_with_exp(int(time.time()) + 3600),
                    "refresh": "refresh-token",
                    "expires": int((time.time() + 3600) * 1000),
                    "accountId": "acct-file-456",
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_OPENAI_OAUTH_AUTH_PATH", str(auth_path))

    status = get_openai_oauth_auth_status()
    dispatched = get_auth_status("openai-oauth")

    assert status["logged_in"] is True
    assert status["provider"] == "openai-oauth"
    assert status["account_id"] == "acct-file-456"
    assert dispatched["logged_in"] is True
    assert dispatched["provider"] == "openai-oauth"
