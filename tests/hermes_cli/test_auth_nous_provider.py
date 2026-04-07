"""Regression tests for Nous OAuth refresh + agent-key mint interactions."""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from hermes_cli.auth import AuthError, get_nous_auth_status, get_provider_auth_state, resolve_nous_runtime_credentials


def _setup_nous_auth(
    hermes_home: Path,
    *,
    access_token: str = "access-old",
    refresh_token: str = "refresh-old",
) -> None:
    hermes_home.mkdir(parents=True, exist_ok=True)
    auth_store = {
        "version": 1,
        "active_provider": "nous",
        "providers": {
            "nous": {
                "portal_base_url": "https://portal.example.com",
                "inference_base_url": "https://inference.example.com/v1",
                "client_id": "hermes-cli",
                "token_type": "Bearer",
                "scope": "inference:mint_agent_key",
                "access_token": access_token,
                "refresh_token": refresh_token,
                "obtained_at": "2026-02-01T00:00:00+00:00",
                "expires_in": 0,
                "expires_at": "2026-02-01T00:00:00+00:00",
                "agent_key": None,
                "agent_key_id": None,
                "agent_key_expires_at": None,
                "agent_key_expires_in": None,
                "agent_key_reused": None,
                "agent_key_obtained_at": None,
            }
        },
    }
    (hermes_home / "auth.json").write_text(json.dumps(auth_store, indent=2))


def _mint_payload(api_key: str = "agent-key") -> dict:
    return {
        "api_key": api_key,
        "key_id": "key-id-1",
        "expires_at": datetime.now(timezone.utc).isoformat(),
        "expires_in": 1800,
        "reused": False,
    }


def test_refresh_token_persisted_when_mint_returns_insufficient_credits(tmp_path, monkeypatch):
    hermes_home = tmp_path / "hermes"
    _setup_nous_auth(hermes_home, refresh_token="refresh-old")
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    refresh_calls = []
    mint_calls = {"count": 0}

    def _fake_refresh_access_token(*, client, portal_base_url, client_id, refresh_token):
        refresh_calls.append(refresh_token)
        idx = len(refresh_calls)
        return {
            "access_token": f"access-{idx}",
            "refresh_token": f"refresh-{idx}",
            "expires_in": 0,
            "token_type": "Bearer",
        }

    def _fake_mint_agent_key(*, client, portal_base_url, access_token, min_ttl_seconds):
        mint_calls["count"] += 1
        if mint_calls["count"] == 1:
            raise AuthError("credits exhausted", provider="nous", code="insufficient_credits")
        return _mint_payload(api_key="agent-key-2")

    monkeypatch.setattr("hermes_cli.auth._refresh_access_token", _fake_refresh_access_token)
    monkeypatch.setattr("hermes_cli.auth._mint_agent_key", _fake_mint_agent_key)

    with pytest.raises(AuthError) as exc:
        resolve_nous_runtime_credentials(min_key_ttl_seconds=300)
    assert exc.value.code == "insufficient_credits"

    state_after_failure = get_provider_auth_state("nous")
    assert state_after_failure is not None
    assert state_after_failure["refresh_token"] == "refresh-1"
    assert state_after_failure["access_token"] == "access-1"

    creds = resolve_nous_runtime_credentials(min_key_ttl_seconds=300)
    assert creds["api_key"] == "agent-key-2"
    assert refresh_calls == ["refresh-old", "refresh-1"]


def test_refresh_token_persisted_when_mint_times_out(tmp_path, monkeypatch):
    hermes_home = tmp_path / "hermes"
    _setup_nous_auth(hermes_home, refresh_token="refresh-old")
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    def _fake_refresh_access_token(*, client, portal_base_url, client_id, refresh_token):
        return {
            "access_token": "access-1",
            "refresh_token": "refresh-1",
            "expires_in": 0,
            "token_type": "Bearer",
        }

    def _fake_mint_agent_key(*, client, portal_base_url, access_token, min_ttl_seconds):
        raise httpx.ReadTimeout("mint timeout")

    monkeypatch.setattr("hermes_cli.auth._refresh_access_token", _fake_refresh_access_token)
    monkeypatch.setattr("hermes_cli.auth._mint_agent_key", _fake_mint_agent_key)

    with pytest.raises(httpx.ReadTimeout):
        resolve_nous_runtime_credentials(min_key_ttl_seconds=300)

    state_after_failure = get_provider_auth_state("nous")
    assert state_after_failure is not None
    assert state_after_failure["refresh_token"] == "refresh-1"
    assert state_after_failure["access_token"] == "access-1"


def test_mint_retry_uses_latest_rotated_refresh_token(tmp_path, monkeypatch):
    hermes_home = tmp_path / "hermes"
    _setup_nous_auth(hermes_home, refresh_token="refresh-old")
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    refresh_calls = []
    mint_calls = {"count": 0}

    def _fake_refresh_access_token(*, client, portal_base_url, client_id, refresh_token):
        refresh_calls.append(refresh_token)
        idx = len(refresh_calls)
        return {
            "access_token": f"access-{idx}",
            "refresh_token": f"refresh-{idx}",
            "expires_in": 0,
            "token_type": "Bearer",
        }

    def _fake_mint_agent_key(*, client, portal_base_url, access_token, min_ttl_seconds):
        mint_calls["count"] += 1
        if mint_calls["count"] == 1:
            raise AuthError("stale access token", provider="nous", code="invalid_token")
        return _mint_payload(api_key="agent-key")

    monkeypatch.setattr("hermes_cli.auth._refresh_access_token", _fake_refresh_access_token)
    monkeypatch.setattr("hermes_cli.auth._mint_agent_key", _fake_mint_agent_key)

    creds = resolve_nous_runtime_credentials(min_key_ttl_seconds=300)
    assert creds["api_key"] == "agent-key"
    assert refresh_calls == ["refresh-old", "refresh-1"]


# =============================================================================
# get_nous_auth_status — credential pool path (issue #5807)
# =============================================================================


def _make_pool_entry(
    *,
    access_token: str = "access-tok",
    refresh_token: str = "refresh-tok",
    portal_base_url: str = "https://portal.example.com",
    inference_base_url: str = "https://inference.example.com/v1",
    expires_at: str = "2099-01-01T00:00:00+00:00",
    agent_key_expires_at: str = "2099-01-01T00:00:00+00:00",
    label: str = "test@example.com",
):
    """Return a minimal PooledCredential-like mock for nous."""
    entry = MagicMock()
    entry.access_token = access_token
    entry.refresh_token = refresh_token
    entry.portal_base_url = portal_base_url
    entry.inference_base_url = inference_base_url
    entry.expires_at = expires_at
    entry.agent_key_expires_at = agent_key_expires_at
    entry.label = label
    return entry


def _make_pool(entry=None, *, has_creds: bool = True):
    pool = MagicMock()
    pool.has_credentials.return_value = has_creds
    pool.select.return_value = entry
    return pool


def test_get_nous_auth_status_pool_logged_in(tmp_path, monkeypatch):
    """get_nous_auth_status returns logged_in=True when a valid pool entry exists."""
    hermes_home = tmp_path / "hermes"
    hermes_home.mkdir(parents=True, exist_ok=True)
    # Empty legacy state — pool should win
    (hermes_home / "auth.json").write_text(json.dumps({"version": 1, "providers": {}}))
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    entry = _make_pool_entry()
    fake_pool = _make_pool(entry)

    with patch("agent.credential_pool.load_pool", return_value=fake_pool) as mock_load_pool:
        status = get_nous_auth_status()

    mock_load_pool.assert_called_once_with("nous")
    assert status["logged_in"] is True
    assert status["portal_base_url"] == "https://portal.example.com"
    assert status["inference_base_url"] == "https://inference.example.com/v1"
    assert status["access_expires_at"] == "2099-01-01T00:00:00+00:00"
    assert status["agent_key_expires_at"] == "2099-01-01T00:00:00+00:00"
    assert status["has_refresh_token"] is True
    assert "pool:" in status["source"]


def test_get_nous_auth_status_pool_empty_falls_back_to_legacy(tmp_path, monkeypatch):
    """get_nous_auth_status falls back to legacy provider state when pool is empty."""
    hermes_home = tmp_path / "hermes"
    _setup_nous_auth(hermes_home, access_token="legacy-token", refresh_token="legacy-refresh")
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    empty_pool = _make_pool(entry=None, has_creds=False)

    with patch("agent.credential_pool.load_pool", return_value=empty_pool):
        status = get_nous_auth_status()

    assert status["logged_in"] is True
    assert status["has_refresh_token"] is True
    # source key is absent for legacy path
    assert "source" not in status


def test_get_nous_auth_status_pool_entry_no_access_token_falls_back(tmp_path, monkeypatch):
    """get_nous_auth_status falls back when the pool entry has no access_token."""
    hermes_home = tmp_path / "hermes"
    _setup_nous_auth(hermes_home, access_token="legacy-token")
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    entry = _make_pool_entry(access_token="")  # empty access_token
    fake_pool = _make_pool(entry)

    with patch("agent.credential_pool.load_pool", return_value=fake_pool):
        status = get_nous_auth_status()

    # Falls back to legacy which has access_token
    assert status["logged_in"] is True
    assert "source" not in status


def test_get_nous_auth_status_not_logged_in_when_no_creds(tmp_path, monkeypatch):
    """get_nous_auth_status returns logged_in=False when both pool and legacy are empty."""
    hermes_home = tmp_path / "hermes"
    hermes_home.mkdir(parents=True, exist_ok=True)
    (hermes_home / "auth.json").write_text(json.dumps({"version": 1, "providers": {}}))
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    empty_pool = _make_pool(entry=None, has_creds=False)

    with patch("agent.credential_pool.load_pool", return_value=empty_pool):
        status = get_nous_auth_status()

    assert status["logged_in"] is False
    assert status["portal_base_url"] is None


def test_get_nous_auth_status_pool_exception_falls_back(tmp_path, monkeypatch):
    """get_nous_auth_status silently falls back to legacy when load_pool raises."""
    hermes_home = tmp_path / "hermes"
    _setup_nous_auth(hermes_home, access_token="legacy-token")
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    with patch("agent.credential_pool.load_pool", side_effect=RuntimeError("pool exploded")):
        status = get_nous_auth_status()

    # Falls back to legacy
    assert status["logged_in"] is True
    assert "source" not in status
