"""Tests for Codex auth — tokens stored in Hermes auth store (~/.hermes/auth.json)."""

import json
import time
import base64
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from hermes_cli.auth import (
    AuthError,
    CODEX_ACCESS_TOKEN_MAX_AGE_SECONDS,
    CODEX_SHARED_STORE_FILENAME,
    DEFAULT_CODEX_BASE_URL,
    PROVIDER_REGISTRY,
    _codex_access_token_is_expiring,
    _codex_shared_auth_dir,
    _codex_shared_store_path,
    _merge_shared_codex_state,
    _read_codex_tokens,
    _read_shared_codex_state,
    _save_codex_tokens,
    _import_codex_cli_tokens,
    _login_openai_codex,
    _write_shared_codex_state,
    get_codex_auth_status,
    get_provider_auth_state,
    refresh_codex_oauth_pure,
    resolve_codex_runtime_credentials,
    resolve_provider,
)


def _setup_hermes_auth(
    hermes_home: Path,
    *,
    access_token: str = "access",
    refresh_token: str = "refresh",
    last_refresh: str | None = None,
):
    """Write Codex tokens into the Hermes auth store.

    ``last_refresh`` defaults to ``now`` so callers get a fresh-by-default
    fixture.  Tests that need to exercise stale-token behaviour should pass an
    explicit ISO-8601 UTC timestamp older than CODEX_ACCESS_TOKEN_MAX_AGE_SECONDS.
    """
    from datetime import datetime, timezone
    if last_refresh is None:
        last_refresh = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    hermes_home.mkdir(parents=True, exist_ok=True)
    auth_store = {
        "version": 1,
        "active_provider": "openai-codex",
        "providers": {
            "openai-codex": {
                "tokens": {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                },
                "last_refresh": last_refresh,
                "auth_mode": "chatgpt",
            },
        },
    }
    auth_file = hermes_home / "auth.json"
    auth_file.write_text(json.dumps(auth_store, indent=2))
    return auth_file


def _jwt_with_exp(exp_epoch: int) -> str:
    payload = {"exp": exp_epoch}
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).rstrip(b"=").decode("utf-8")
    return f"h.{encoded}.s"


def test_read_codex_tokens_success(tmp_path, monkeypatch):
    hermes_home = tmp_path / "hermes"
    _setup_hermes_auth(hermes_home)
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    data = _read_codex_tokens()
    assert data["tokens"]["access_token"] == "access"
    assert data["tokens"]["refresh_token"] == "refresh"


def test_read_codex_tokens_missing(tmp_path, monkeypatch):
    hermes_home = tmp_path / "hermes"
    hermes_home.mkdir(parents=True, exist_ok=True)
    # Empty auth store
    (hermes_home / "auth.json").write_text(json.dumps({"version": 1, "providers": {}}))
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    with pytest.raises(AuthError) as exc:
        _read_codex_tokens()
    assert exc.value.code == "codex_auth_missing"


def test_resolve_codex_runtime_credentials_missing_access_token(tmp_path, monkeypatch):
    hermes_home = tmp_path / "hermes"
    _setup_hermes_auth(hermes_home, access_token="")
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    with pytest.raises(AuthError) as exc:
        resolve_codex_runtime_credentials()
    assert exc.value.code == "codex_auth_missing_access_token"
    assert exc.value.relogin_required is True


def test_resolve_codex_runtime_credentials_refreshes_expiring_token(tmp_path, monkeypatch):
    hermes_home = tmp_path / "hermes"
    expiring_token = _jwt_with_exp(int(time.time()) - 10)
    _setup_hermes_auth(hermes_home, access_token=expiring_token, refresh_token="refresh-old")
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    called = {"count": 0}

    def _fake_refresh(tokens, timeout_seconds):
        called["count"] += 1
        return {"access_token": "access-new", "refresh_token": "refresh-new"}

    monkeypatch.setattr("hermes_cli.auth._refresh_codex_auth_tokens", _fake_refresh)

    resolved = resolve_codex_runtime_credentials()

    assert called["count"] == 1
    assert resolved["api_key"] == "access-new"


def test_resolve_codex_runtime_credentials_force_refresh(tmp_path, monkeypatch):
    hermes_home = tmp_path / "hermes"
    _setup_hermes_auth(hermes_home, access_token="access-current", refresh_token="refresh-old")
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    called = {"count": 0}

    def _fake_refresh(tokens, timeout_seconds):
        called["count"] += 1
        return {"access_token": "access-forced", "refresh_token": "refresh-new"}

    monkeypatch.setattr("hermes_cli.auth._refresh_codex_auth_tokens", _fake_refresh)

    resolved = resolve_codex_runtime_credentials(force_refresh=True, refresh_if_expiring=False)

    assert called["count"] == 1
    assert resolved["api_key"] == "access-forced"


def test_resolve_codex_runtime_credentials_falls_back_to_pool_when_singleton_empty(tmp_path, monkeypatch):
    """Regression for #32992 — chat path returns 401 when singleton is empty but pool has creds.

    The chat path historically went through ``resolve_codex_runtime_credentials`` which
    only consulted ``providers.openai-codex.tokens`` and raised ``AuthError`` when that
    was empty.  The auxiliary path went through ``_read_codex_access_token`` which
    checks the pool first.  Users with creds only in the pool (manual seed, partial
    re-auth, restore from backup) hit a bare HTTP 401 on chat but worked fine on
    auxiliary calls.  The fallback closes that divergence.
    """
    hermes_home = tmp_path / "hermes"
    hermes_home.mkdir(parents=True, exist_ok=True)
    # Singleton: empty tokens (would normally raise AuthError).
    # Pool: valid access_token.
    auth_store = {
        "version": 1,
        "providers": {},  # no openai-codex singleton at all
        "credential_pool": {
            "openai-codex": [
                {
                    "source": "device_code",
                    "access_token": "pool-fallback-token",
                    "refresh_token": "pool-refresh",
                    "last_status": "ok",
                    "auth_type": "oauth",
                },
            ],
        },
    }
    (hermes_home / "auth.json").write_text(json.dumps(auth_store))
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    resolved = resolve_codex_runtime_credentials()
    assert resolved["api_key"] == "pool-fallback-token"
    assert resolved["source"] == "credential_pool"
    assert resolved["base_url"]  # default codex backend URL


def test_resolve_codex_runtime_credentials_pool_fallback_skips_exhausted(tmp_path, monkeypatch):
    """The pool fallback skips entries currently in an exhaustion cooldown window."""
    import time as _time

    hermes_home = tmp_path / "hermes"
    hermes_home.mkdir(parents=True, exist_ok=True)
    future_reset = _time.time() + 3600  # 1h cooldown remaining
    auth_store = {
        "version": 1,
        "providers": {},
        "credential_pool": {
            "openai-codex": [
                {
                    "source": "device_code",
                    "access_token": "wedged-token",
                    "last_error_reset_at": future_reset,  # in cooldown
                },
                {
                    "source": "device_code",
                    "access_token": "usable-token",
                    "last_status": "ok",
                },
            ],
        },
    }
    (hermes_home / "auth.json").write_text(json.dumps(auth_store))
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    resolved = resolve_codex_runtime_credentials()
    assert resolved["api_key"] == "usable-token"
    assert resolved["source"] == "credential_pool"


def test_resolve_codex_runtime_credentials_pool_fallback_no_usable_entry(tmp_path, monkeypatch):
    """When both singleton and pool are empty/unusable, the original AuthError propagates."""
    hermes_home = tmp_path / "hermes"
    hermes_home.mkdir(parents=True, exist_ok=True)
    auth_store = {
        "version": 1,
        "providers": {},
        "credential_pool": {
            "openai-codex": [
                {"source": "device_code", "access_token": ""},  # empty
            ],
        },
    }
    (hermes_home / "auth.json").write_text(json.dumps(auth_store))
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    with pytest.raises(AuthError) as exc:
        resolve_codex_runtime_credentials()
    assert exc.value.code == "codex_auth_missing"


def test_resolve_provider_explicit_codex_does_not_fallback(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert resolve_provider("openai-codex") == "openai-codex"


def test_save_codex_tokens_roundtrip(tmp_path, monkeypatch):
    hermes_home = tmp_path / "hermes"
    hermes_home.mkdir(parents=True, exist_ok=True)
    (hermes_home / "auth.json").write_text(json.dumps({"version": 1, "providers": {}}))
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    _save_codex_tokens({"access_token": "at123", "refresh_token": "rt456"})
    data = _read_codex_tokens()

    assert data["tokens"]["access_token"] == "at123"
    assert data["tokens"]["refresh_token"] == "rt456"


def test_save_codex_tokens_syncs_credential_pool(tmp_path, monkeypatch):
    """Re-auth must update the credential_pool device_code entry, not just providers.

    Regression for #33000: the runtime selects from credential_pool, so a
    re-auth that only refreshed providers.openai-codex.tokens left the pool
    holding a consumed refresh token and stale error markers, causing an
    immediate 401 token_invalidated on the next request.
    """
    hermes_home = tmp_path / "hermes"
    hermes_home.mkdir(parents=True, exist_ok=True)
    (hermes_home / "auth.json").write_text(json.dumps({
        "version": 1,
        "providers": {
            "openai-codex": {
                "tokens": {"access_token": "old-at", "refresh_token": "old-rt"},
                "last_refresh": "2026-01-01T00:00:00Z",
                "auth_mode": "chatgpt",
            },
        },
        "credential_pool": {
            "openai-codex": [
                {
                    "id": "abc123",
                    "source": "device_code",
                    "auth_type": "oauth",
                    "access_token": "old-at",
                    "refresh_token": "old-rt",
                    "last_status": "exhausted",
                    "last_error_code": 401,
                    "last_error_reason": "token_invalidated",
                    "last_error_reset_at": 9999999999,
                },
                {
                    "id": "manual1",
                    "source": "manual:codex",
                    "auth_type": "oauth",
                    "access_token": "manual-at",
                    "refresh_token": "manual-rt",
                },
            ],
        },
    }))
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    _save_codex_tokens({"access_token": "new-at", "refresh_token": "new-rt"},
                       last_refresh="2026-05-27T00:00:00Z")

    auth = json.loads((hermes_home / "auth.json").read_text())
    pool = auth["credential_pool"]["openai-codex"]
    seeded = next(e for e in pool if e["source"] == "device_code")
    assert seeded["access_token"] == "new-at"
    assert seeded["refresh_token"] == "new-rt"
    assert seeded["last_refresh"] == "2026-05-27T00:00:00Z"
    assert seeded["last_status"] is None
    assert seeded["last_error_code"] is None
    assert seeded["last_error_reason"] is None
    assert seeded["last_error_reset_at"] is None

    # Manual entries are independent credentials and must not be overwritten.
    manual = next(e for e in pool if e["source"] == "manual:codex")
    assert manual["access_token"] == "manual-at"
    assert manual["refresh_token"] == "manual-rt"

    # Provider singleton is updated too.
    assert auth["providers"]["openai-codex"]["tokens"]["access_token"] == "new-at"


def test_save_codex_tokens_syncs_manual_device_code_entries(tmp_path, monkeypatch):
    """Re-auth must also refresh ``manual:device_code`` pool entries.

    Regression for #33538: a user who hit #33000 before the #33164 fix landed
    would have run ``hermes auth add openai-codex`` as a workaround, leaving
    a pool entry with ``source="manual:device_code"``.  On every subsequent
    re-auth via setup/model picker, the singleton-seeded ``device_code`` entry
    got refreshed but the ``manual:device_code`` entry stayed stale, recreating
    the same 401 token_invalidated symptom that #33164 was supposed to fix.

    An interactive Codex device-code re-auth proves the user owns the ChatGPT
    account, so it is safe to refresh every device-code-backed entry in the
    pool — but NOT independent ``manual:api_key`` entries (separate accounts /
    explicit API keys).
    """
    hermes_home = tmp_path / "hermes"
    hermes_home.mkdir(parents=True, exist_ok=True)
    (hermes_home / "auth.json").write_text(json.dumps({
        "version": 1,
        "providers": {
            "openai-codex": {
                "tokens": {"access_token": "old-at", "refresh_token": "old-rt"},
                "last_refresh": "2026-01-01T00:00:00Z",
                "auth_mode": "chatgpt",
            },
        },
        "credential_pool": {
            "openai-codex": [
                {
                    "id": "seeded",
                    "source": "device_code",
                    "auth_type": "oauth",
                    "access_token": "old-at",
                    "refresh_token": "old-rt",
                },
                {
                    "id": "auth-add",
                    "source": "manual:device_code",
                    "auth_type": "oauth",
                    "access_token": "stale-manual-at",
                    "refresh_token": "stale-manual-rt",
                    "last_status": "exhausted",
                    "last_error_code": 401,
                    "last_error_reason": "token_invalidated",
                },
                {
                    "id": "api-key",
                    "source": "manual:api_key",
                    "auth_type": "api_key",
                    "access_token": "user-api-key",
                },
            ],
        },
    }))
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    _save_codex_tokens({"access_token": "fresh-at", "refresh_token": "fresh-rt"},
                       last_refresh="2026-05-28T00:00:00Z")

    auth = json.loads((hermes_home / "auth.json").read_text())
    pool = auth["credential_pool"]["openai-codex"]

    # Singleton-seeded device_code entry: refreshed and error markers cleared.
    seeded = next(e for e in pool if e["source"] == "device_code")
    assert seeded["access_token"] == "fresh-at"
    assert seeded["refresh_token"] == "fresh-rt"

    # manual:device_code entry: ALSO refreshed (the new behavior).
    manual_dc = next(e for e in pool if e["source"] == "manual:device_code")
    assert manual_dc["access_token"] == "fresh-at"
    assert manual_dc["refresh_token"] == "fresh-rt"
    assert manual_dc["last_refresh"] == "2026-05-28T00:00:00Z"
    assert manual_dc["last_status"] is None
    assert manual_dc["last_error_code"] is None
    assert manual_dc["last_error_reason"] is None

    # manual:api_key entry: untouched — independent credential.
    api_key = next(e for e in pool if e["source"] == "manual:api_key")
    assert api_key["access_token"] == "user-api-key"
    assert "refresh_token" not in api_key or api_key.get("refresh_token") is None


def test_import_codex_cli_tokens(tmp_path, monkeypatch):
    codex_home = tmp_path / "codex-cli"
    codex_home.mkdir(parents=True, exist_ok=True)
    (codex_home / "auth.json").write_text(json.dumps({
        "tokens": {"access_token": "cli-at", "refresh_token": "cli-rt"},
    }))
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    tokens = _import_codex_cli_tokens()
    assert tokens is not None
    assert tokens["access_token"] == "cli-at"
    assert tokens["refresh_token"] == "cli-rt"


def test_import_codex_cli_tokens_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "nonexistent"))
    assert _import_codex_cli_tokens() is None


def test_codex_tokens_not_written_to_shared_file(tmp_path, monkeypatch):
    """Verify _save_codex_tokens writes only to Hermes auth store, not ~/.codex/."""
    hermes_home = tmp_path / "hermes"
    codex_home = tmp_path / "codex-cli"
    hermes_home.mkdir(parents=True, exist_ok=True)
    codex_home.mkdir(parents=True, exist_ok=True)

    (hermes_home / "auth.json").write_text(json.dumps({"version": 1, "providers": {}}))
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    _save_codex_tokens({"access_token": "hermes-at", "refresh_token": "hermes-rt"})

    # ~/.codex/auth.json should NOT exist — _save_codex_tokens only touches Hermes store
    assert not (codex_home / "auth.json").exists()

    # Hermes auth store should have the tokens
    data = _read_codex_tokens()
    assert data["tokens"]["access_token"] == "hermes-at"


def test_resolve_returns_hermes_auth_store_source(tmp_path, monkeypatch):
    hermes_home = tmp_path / "hermes"
    _setup_hermes_auth(hermes_home)
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    creds = resolve_codex_runtime_credentials()
    assert creds["source"] == "hermes-auth-store"
    assert creds["provider"] == "openai-codex"
    assert creds["base_url"] == DEFAULT_CODEX_BASE_URL


class _StubHTTPResponse:
    def __init__(self, status_code: int, payload, headers=None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}
        self.text = json.dumps(payload) if isinstance(payload, (dict, list)) else str(payload)

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class _StubHTTPClient:
    def __init__(self, response):
        self._response = response

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def post(self, *args, **kwargs):
        return self._response


def _patch_httpx(monkeypatch, response):
    def _factory(*args, **kwargs):
        return _StubHTTPClient(response)

    monkeypatch.setattr("hermes_cli.auth.httpx.Client", _factory)


def test_refresh_parses_openai_nested_error_shape_refresh_token_reused(monkeypatch):
    """OpenAI returns {"error": {"code": "refresh_token_reused", "message": "..."}}
    — parser must surface relogin_required and the dedicated message.
    """
    response = _StubHTTPResponse(
        401,
        {
            "error": {
                "message": "Your refresh token has already been used to generate a new access token. Please try signing in again.",
                "type": "invalid_request_error",
                "param": None,
                "code": "refresh_token_reused",
            }
        },
    )
    _patch_httpx(monkeypatch, response)

    with pytest.raises(AuthError) as exc_info:
        refresh_codex_oauth_pure("a-tok", "r-tok")

    err = exc_info.value
    assert err.code == "refresh_token_reused"
    assert err.relogin_required is True
    # The existing dedicated branch should override the message with actionable guidance.
    assert "already consumed by another client" in str(err)


def test_refresh_parses_openai_nested_error_shape_generic_code(monkeypatch):
    """Nested error with arbitrary code still surfaces code + message."""
    response = _StubHTTPResponse(
        400,
        {
            "error": {
                "message": "Invalid client credentials.",
                "type": "invalid_request_error",
                "code": "invalid_client",
            }
        },
    )
    _patch_httpx(monkeypatch, response)

    with pytest.raises(AuthError) as exc_info:
        refresh_codex_oauth_pure("a-tok", "r-tok")

    err = exc_info.value
    assert err.code == "invalid_client"
    assert "Invalid client credentials." in str(err)


def test_refresh_parses_oauth_spec_flat_error_shape_invalid_grant(monkeypatch):
    """Fallback path: OAuth spec-shape {"error": "invalid_grant", "error_description": "..."}
    must still map to relogin_required=True via the existing code set.
    """
    response = _StubHTTPResponse(
        400,
        {
            "error": "invalid_grant",
            "error_description": "Refresh token is expired or revoked.",
        },
    )
    _patch_httpx(monkeypatch, response)

    with pytest.raises(AuthError) as exc_info:
        refresh_codex_oauth_pure("a-tok", "r-tok")

    err = exc_info.value
    assert err.code == "invalid_grant"
    assert err.relogin_required is True
    assert "Refresh token is expired or revoked." in str(err)


def test_refresh_falls_back_to_generic_message_on_unparseable_body(monkeypatch):
    """No JSON body → generic 'with status 401' message; 401 always forces relogin."""
    response = _StubHTTPResponse(401, ValueError("not json"))
    _patch_httpx(monkeypatch, response)

    with pytest.raises(AuthError) as exc_info:
        refresh_codex_oauth_pure("a-tok", "r-tok")

    err = exc_info.value
    assert err.code == "codex_refresh_failed"
    # 401/403 from the token endpoint always means the refresh token is
    # invalid/expired — force relogin even without a parseable error body.
    assert err.relogin_required is True
    assert "status 401" in str(err)


def test_refresh_429_classified_as_quota_not_auth_failure(monkeypatch):
    """429 from the token endpoint is a usage-quota cap, not an auth failure.

    Regression test for #32790: must NOT force relogin and must carry the
    dedicated rate-limit code so callers surface a "retry later" notice rather
    than a misleading "run hermes auth".
    """
    from hermes_cli.auth import (
        CODEX_RATE_LIMITED_CODE,
        format_auth_error,
        is_rate_limited_auth_error,
    )

    response = _StubHTTPResponse(
        429,
        {"error": {"message": "You hit your usage limit.", "code": "usage_limit_reached"}},
        headers={"retry-after": "120"},
    )
    _patch_httpx(monkeypatch, response)

    with pytest.raises(AuthError) as exc_info:
        refresh_codex_oauth_pure("a-tok", "r-tok")

    err = exc_info.value
    assert err.code == CODEX_RATE_LIMITED_CODE
    assert err.relogin_required is False
    assert is_rate_limited_auth_error(err) is True
    assert "retry after 120s" in str(err)
    # User-facing copy must not tell the operator to re-authenticate.
    rendered = format_auth_error(err)
    assert "re-authenticate" not in rendered
    assert "hermes auth" not in rendered


def test_refresh_429_without_retry_after_header(monkeypatch):
    """429 without a Retry-After header still classifies as quota, no relogin."""
    from hermes_cli.auth import CODEX_RATE_LIMITED_CODE

    response = _StubHTTPResponse(429, {"error": "rate_limited"})
    _patch_httpx(monkeypatch, response)

    with pytest.raises(AuthError) as exc_info:
        refresh_codex_oauth_pure("a-tok", "r-tok")

    err = exc_info.value
    assert err.code == CODEX_RATE_LIMITED_CODE
    assert err.relogin_required is False
    assert "quota exhausted" in str(err).lower()


def test_is_rate_limited_auth_error_distinguishes_credential_errors():
    """Missing/expired credentials must NOT be treated as rate-limit errors."""
    from hermes_cli.auth import CODEX_RATE_LIMITED_CODE, is_rate_limited_auth_error

    rate_limited = AuthError(
        "quota", provider="openai-codex", code=CODEX_RATE_LIMITED_CODE, relogin_required=False
    )
    missing_creds = AuthError(
        "No Codex credentials stored.",
        provider="openai-codex",
        code="codex_auth_missing",
        relogin_required=True,
    )
    assert is_rate_limited_auth_error(rate_limited) is True
    assert is_rate_limited_auth_error(missing_creds) is False
    assert is_rate_limited_auth_error(ValueError("nope")) is False


def test_login_openai_codex_force_new_login_skips_existing_reuse_prompt(monkeypatch):
    called = {"device_login": 0}

    monkeypatch.setattr(
        "hermes_cli.auth.resolve_codex_runtime_credentials",
        lambda: {"base_url": DEFAULT_CODEX_BASE_URL},
    )
    monkeypatch.setattr(
        "hermes_cli.auth._import_codex_cli_tokens",
        lambda: {"access_token": "cli-at", "refresh_token": "cli-rt"},
    )
    monkeypatch.setattr(
        "hermes_cli.auth._codex_device_code_login",
        lambda: {
            "tokens": {"access_token": "fresh-at", "refresh_token": "fresh-rt"},
            "last_refresh": "2026-04-01T00:00:00Z",
            "base_url": DEFAULT_CODEX_BASE_URL,
        },
    )

    def _fake_save(tokens, last_refresh=None):
        called["device_login"] += 1
        called["tokens"] = dict(tokens)
        called["last_refresh"] = last_refresh

    monkeypatch.setattr("hermes_cli.auth._save_codex_tokens", _fake_save)
    monkeypatch.setattr("hermes_cli.auth._update_config_for_provider", lambda *args, **kwargs: "/tmp/config.yaml")
    monkeypatch.setattr(
        "builtins.input",
        lambda prompt="": (_ for _ in ()).throw(AssertionError("force_new_login should not prompt for reuse/import")),
    )

    _login_openai_codex(SimpleNamespace(), PROVIDER_REGISTRY["openai-codex"], force_new_login=True)

    assert called["device_login"] == 1
    assert called["tokens"]["access_token"] == "fresh-at"


# -----------------------------------------------------------------------------
# _codex_access_token_is_expiring — wall-clock floor on top of JWT exp.
#
# The JWT-exp-only predicate is insufficient because chatgpt.com's Cloudflare
# layer enforces a server-side TTL much shorter than the JWT's declared exp
# (observed in production: JWT exp ~10 days out, server starts silently
# dropping requests after a few hours).  Adding ``last_refresh`` lets the
# predicate trigger refresh on wall-clock age, regardless of what the JWT
# claims.
# -----------------------------------------------------------------------------

def _jwt_no_exp() -> str:
    """Return a JWT whose payload omits the ``exp`` claim entirely."""
    encoded = base64.urlsafe_b64encode(json.dumps({"sub": "u"}).encode("utf-8")).rstrip(b"=").decode("utf-8")
    return f"h.{encoded}.s"


def _iso_now_minus(seconds: int) -> str:
    """Return an ISO-8601 UTC timestamp ``seconds`` in the past."""
    from datetime import datetime, timezone, timedelta
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def test_codex_access_token_is_expiring_jwt_exp_in_past_returns_true():
    """Legacy: JWT exp in the past still triggers refresh (regression guard)."""
    token = _jwt_with_exp(int(time.time()) - 60)
    assert _codex_access_token_is_expiring(token, 0) is True


def test_codex_access_token_is_expiring_jwt_exp_far_future_no_last_refresh_returns_false():
    """Backward compat: callers that don't pass last_refresh see the original JWT-only behavior."""
    token = _jwt_with_exp(int(time.time()) + 10 * 24 * 3600)  # 10 days out, matches real Codex JWTs
    assert _codex_access_token_is_expiring(token, 120) is False


def test_codex_access_token_is_expiring_fresh_last_refresh_returns_false():
    """30-min-old last_refresh is under the 45-min default cap → no refresh."""
    token = _jwt_with_exp(int(time.time()) + 10 * 24 * 3600)
    assert _codex_access_token_is_expiring(
        token, 120, last_refresh=_iso_now_minus(30 * 60)
    ) is False


def test_codex_access_token_is_expiring_stale_last_refresh_overrides_jwt_exp():
    """THE PRODUCTION FIX.  JWT exp far future, but last_refresh is 50 min old → refresh.

    Repro: JWTs from chatgpt.com/backend-api/codex carry exp ~10 days out,
    so the legacy JWT-only predicate returns False forever.  Cloudflare
    nevertheless silently drops requests once its server-side TTL elapses
    (observed somewhere between a few hours and several days post-refresh).
    The wall-clock floor on ``last_refresh`` catches this case.
    """
    token = _jwt_with_exp(int(time.time()) + 10 * 24 * 3600)
    assert _codex_access_token_is_expiring(
        token, 120, last_refresh=_iso_now_minus(50 * 60)
    ) is True


def test_codex_access_token_is_expiring_no_exp_but_stale_last_refresh_returns_true():
    """JWT lacks exp; wall-clock alone triggers refresh."""
    assert _codex_access_token_is_expiring(
        _jwt_no_exp(), 120, last_refresh=_iso_now_minus(60 * 60)
    ) is True


def test_codex_access_token_is_expiring_no_exp_no_last_refresh_returns_false():
    """Both signals absent → preserve original conservative behavior (no spurious refresh)."""
    assert _codex_access_token_is_expiring(_jwt_no_exp(), 120) is False


def test_codex_access_token_is_expiring_malformed_last_refresh_falls_through_to_jwt():
    """Garbage in last_refresh must not crash; predicate falls through to JWT-exp path."""
    fresh_token = _jwt_with_exp(int(time.time()) + 3600)
    assert _codex_access_token_is_expiring(
        fresh_token, 120, last_refresh="not-an-iso-timestamp"
    ) is False
    expired_token = _jwt_with_exp(int(time.time()) - 60)
    assert _codex_access_token_is_expiring(
        expired_token, 0, last_refresh="not-an-iso-timestamp"
    ) is True


def test_codex_access_token_is_expiring_env_var_overrides_max_age(monkeypatch):
    """HERMES_CODEX_TOKEN_MAX_AGE_SECONDS env var tightens / loosens the cap."""
    token = _jwt_with_exp(int(time.time()) + 10 * 24 * 3600)
    last_refresh = _iso_now_minus(40 * 60)  # under 45-min default, over a 30-min override
    assert _codex_access_token_is_expiring(token, 120, last_refresh=last_refresh) is False
    monkeypatch.setenv("HERMES_CODEX_TOKEN_MAX_AGE_SECONDS", "1800")  # 30 min
    assert _codex_access_token_is_expiring(token, 120, last_refresh=last_refresh) is True


def test_codex_access_token_is_expiring_explicit_max_age_kwarg_overrides_default():
    """Explicit ``max_age_seconds`` kwarg takes precedence over default; 0 disables wall-clock floor."""
    token = _jwt_with_exp(int(time.time()) + 10 * 24 * 3600)
    stale = _iso_now_minus(60 * 60)
    assert _codex_access_token_is_expiring(
        token, 120, last_refresh=stale, max_age_seconds=0
    ) is False
    assert _codex_access_token_is_expiring(
        token, 120, last_refresh=stale, max_age_seconds=600
    ) is True


def test_codex_access_token_max_age_default_is_45_minutes():
    """Documented value: 45 min.  Guard against silent default changes."""
    assert CODEX_ACCESS_TOKEN_MAX_AGE_SECONDS == 45 * 60


# -----------------------------------------------------------------------------
# Shared Codex auth store — cross-profile coordination via a single file.
#
# Use case: multiple Hermes profiles (e.g. a Docker fleet of agents) all
# authenticate against the same ChatGPT account.  Without shared state, the
# first profile to rotate the single-use refresh_token invalidates every
# sibling's local copy and they trip ``refresh_token_reused`` on next refresh.
# The shared store gives them a single source of truth.
# -----------------------------------------------------------------------------

def test_codex_shared_auth_dir_honors_env_override(tmp_path, monkeypatch):
    """HERMES_SHARED_AUTH_DIR redirects the shared-store directory."""
    monkeypatch.setenv("HERMES_SHARED_AUTH_DIR", str(tmp_path / "shared"))
    assert _codex_shared_auth_dir() == tmp_path / "shared"


def test_codex_shared_auth_dir_defaults_to_hermes_root_shared(tmp_path, monkeypatch):
    """Default location is ``<hermes-root>/shared/`` when env var is unset."""
    monkeypatch.delenv("HERMES_SHARED_AUTH_DIR", raising=False)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes"))
    expected = _codex_shared_auth_dir()
    # We don't assert the exact path (depends on platform & hermes_constants)
    # but it must end in /shared and live somewhere under or alongside HERMES_HOME.
    assert expected.name == "shared"


def test_codex_shared_store_path_seat_belt_blocks_real_home(tmp_path, monkeypatch):
    """Under pytest, refuse to touch the real user's shared store without override."""
    monkeypatch.delenv("HERMES_SHARED_AUTH_DIR", raising=False)
    # Force the default-resolution path to match the seat-belt target.
    # We use a monkeypatch on get_default_hermes_root via the auth module's
    # cached import — both sides need to agree for the seat-belt guard to fire.
    from hermes_constants import get_default_hermes_root as real_get_root  # noqa: F401
    with pytest.raises(RuntimeError, match="Refusing to touch real user shared Codex"):
        _codex_shared_store_path()


def test_codex_shared_store_path_with_override(tmp_path, monkeypatch):
    """Override path bypasses the seat belt."""
    monkeypatch.setenv("HERMES_SHARED_AUTH_DIR", str(tmp_path / "shared_override"))
    path = _codex_shared_store_path()
    assert path == tmp_path / "shared_override" / CODEX_SHARED_STORE_FILENAME


def test_read_shared_codex_state_returns_none_when_missing(tmp_path, monkeypatch):
    """Missing shared file returns None, not an error."""
    monkeypatch.setenv("HERMES_SHARED_AUTH_DIR", str(tmp_path / "shared"))
    assert _read_shared_codex_state() is None


def test_read_shared_codex_state_returns_dict(tmp_path, monkeypatch):
    """Populated shared file is read back as a dict."""
    shared_dir = tmp_path / "shared"
    monkeypatch.setenv("HERMES_SHARED_AUTH_DIR", str(shared_dir))
    shared_dir.mkdir()
    payload = {
        "access_token": "at-1",
        "refresh_token": "rt-1",
        "last_refresh": "2026-05-28T10:00:00.000000Z",
    }
    (shared_dir / CODEX_SHARED_STORE_FILENAME).write_text(json.dumps(payload))
    state = _read_shared_codex_state()
    assert state["access_token"] == "at-1"
    assert state["refresh_token"] == "rt-1"


def test_write_shared_codex_state_persists(tmp_path, monkeypatch):
    """Writing shared state produces a readable file under HERMES_SHARED_AUTH_DIR."""
    shared_dir = tmp_path / "shared"
    monkeypatch.setenv("HERMES_SHARED_AUTH_DIR", str(shared_dir))
    _write_shared_codex_state(
        {"access_token": "at-w", "refresh_token": "rt-w"},
        "2026-05-28T11:00:00.000000Z",
    )
    written = json.loads((shared_dir / CODEX_SHARED_STORE_FILENAME).read_text())
    assert written["access_token"] == "at-w"
    assert written["refresh_token"] == "rt-w"
    assert written["last_refresh"] == "2026-05-28T11:00:00.000000Z"
    assert written["auth_mode"] == "chatgpt"


def test_write_shared_codex_state_skips_when_tokens_empty(tmp_path, monkeypatch):
    """No-op write when either token is missing — don't pollute shared with garbage."""
    shared_dir = tmp_path / "shared"
    monkeypatch.setenv("HERMES_SHARED_AUTH_DIR", str(shared_dir))
    _write_shared_codex_state({"access_token": "at-only", "refresh_token": ""}, None)
    assert not (shared_dir / CODEX_SHARED_STORE_FILENAME).exists()


def test_merge_shared_codex_state_adopts_fresher(tmp_path, monkeypatch):
    """Local state with stale last_refresh adopts fresher shared tokens."""
    shared_dir = tmp_path / "shared"
    monkeypatch.setenv("HERMES_SHARED_AUTH_DIR", str(shared_dir))
    shared_dir.mkdir()
    (shared_dir / CODEX_SHARED_STORE_FILENAME).write_text(json.dumps({
        "access_token": "at-fresh",
        "refresh_token": "rt-fresh",
        "last_refresh": "2026-05-28T12:00:00.000000Z",
    }))
    local = {
        "tokens": {"access_token": "at-stale", "refresh_token": "rt-stale"},
        "last_refresh": "2026-05-28T10:00:00.000000Z",
    }
    assert _merge_shared_codex_state(local) is True
    assert local["tokens"]["access_token"] == "at-fresh"
    assert local["tokens"]["refresh_token"] == "rt-fresh"
    assert local["last_refresh"] == "2026-05-28T12:00:00.000000Z"


def test_merge_shared_codex_state_skips_when_local_is_newer(tmp_path, monkeypatch):
    """Local fresher than shared → no merge, no mutation."""
    shared_dir = tmp_path / "shared"
    monkeypatch.setenv("HERMES_SHARED_AUTH_DIR", str(shared_dir))
    shared_dir.mkdir()
    (shared_dir / CODEX_SHARED_STORE_FILENAME).write_text(json.dumps({
        "access_token": "at-old",
        "refresh_token": "rt-old",
        "last_refresh": "2026-05-28T10:00:00.000000Z",
    }))
    local = {
        "tokens": {"access_token": "at-new", "refresh_token": "rt-new"},
        "last_refresh": "2026-05-28T12:00:00.000000Z",
    }
    assert _merge_shared_codex_state(local) is False
    assert local["tokens"]["access_token"] == "at-new"


def test_merge_shared_codex_state_returns_false_when_shared_missing(tmp_path, monkeypatch):
    """No shared store configured → merge is a clean no-op."""
    monkeypatch.setenv("HERMES_SHARED_AUTH_DIR", str(tmp_path / "shared-none"))
    local = {
        "tokens": {"access_token": "at", "refresh_token": "rt"},
        "last_refresh": "2026-05-28T12:00:00.000000Z",
    }
    assert _merge_shared_codex_state(local) is False


def test_save_codex_tokens_propagates_to_shared_store(tmp_path, monkeypatch):
    """Saving local tokens also writes them to the shared store (if configured)."""
    hermes_home = tmp_path / "hermes"
    shared_dir = tmp_path / "shared"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.setenv("HERMES_SHARED_AUTH_DIR", str(shared_dir))
    _save_codex_tokens(
        {"access_token": "at-saved", "refresh_token": "rt-saved"},
        last_refresh="2026-05-28T13:00:00.000000Z",
    )
    written = json.loads((shared_dir / CODEX_SHARED_STORE_FILENAME).read_text())
    assert written["access_token"] == "at-saved"
    assert written["refresh_token"] == "rt-saved"
    assert written["last_refresh"] == "2026-05-28T13:00:00.000000Z"


def test_resolve_adopts_shared_tokens_and_skips_refresh(tmp_path, monkeypatch):
    """End-to-end: stale local + fresh shared → adopt shared, no network refresh."""
    from datetime import datetime, timezone, timedelta
    hermes_home = tmp_path / "hermes"
    shared_dir = tmp_path / "shared"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.setenv("HERMES_SHARED_AUTH_DIR", str(shared_dir))

    # Stale local — older than the 45-min wall-clock floor.
    stale_ago = (datetime.now(timezone.utc) - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    _setup_hermes_auth(
        hermes_home,
        access_token=_jwt_with_exp(int(time.time()) + 10 * 24 * 3600),
        refresh_token="stale-rt",
        last_refresh=stale_ago,
    )
    # Fresh shared — written by a "sibling profile" 5 seconds ago.
    fresh_ago = (datetime.now(timezone.utc) - timedelta(seconds=5)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    shared_dir.mkdir()
    (shared_dir / CODEX_SHARED_STORE_FILENAME).write_text(json.dumps({
        "access_token": _jwt_with_exp(int(time.time()) + 10 * 24 * 3600),
        "refresh_token": "fresh-rt-from-sibling",
        "last_refresh": fresh_ago,
    }))

    # If the code under test calls the network, the test fails noisily.
    def _explode(*a, **kw):
        raise AssertionError("refresh should NOT fire when shared store has fresh tokens")
    monkeypatch.setattr("hermes_cli.auth._refresh_codex_auth_tokens", _explode)

    resolved = resolve_codex_runtime_credentials()
    assert resolved["api_key"]  # non-empty
    # Local store should now hold the sibling's tokens.
    local_after = json.loads((hermes_home / "auth.json").read_text())
    state = local_after["providers"]["openai-codex"]
    assert state["tokens"]["refresh_token"] == "fresh-rt-from-sibling"
    assert state["last_refresh"] == fresh_ago
