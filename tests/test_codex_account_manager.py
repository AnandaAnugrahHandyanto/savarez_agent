from __future__ import annotations

import base64
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent.credential_pool import AUTH_TYPE_OAUTH, PooledCredential, load_pool
from hermes_cli.auth import AuthError, _read_codex_tokens, _save_codex_tokens, write_credential_pool
from hermes_constants import get_hermes_home

import codex_account_manager as cam


@pytest.fixture(autouse=True)
def _isolate_codex_home(tmp_path, monkeypatch):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / ".codex"))


def _jwt_for_email(email: str) -> str:
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode()).decode().rstrip("=")
    payload = base64.urlsafe_b64encode(
        json.dumps({"https://api.openai.com/profile": {"email": email}}).encode()
    ).decode().rstrip("=")
    return f"{header}.{payload}.sig"


def _entry(
    entry_id: str,
    label: str,
    priority: int,
    *,
    email: str | None = None,
    plan_type: str | None = None,
    plan_expires_at: str | None = None,
    source: str = "manual:device_code",
    account_id: str | None = None,
) -> PooledCredential:
    extra = {}
    if email:
        extra["email"] = email
    if plan_type:
        extra["plan_type"] = plan_type
    if plan_expires_at:
        extra["plan_expires_at"] = plan_expires_at
    if account_id:
        extra["account_id"] = account_id
    return PooledCredential(
        provider="openai-codex",
        id=entry_id,
        label=label,
        auth_type=AUTH_TYPE_OAUTH,
        priority=priority,
        source=source,
        access_token=f"access-{entry_id}",
        refresh_token=f"refresh-{entry_id}",
        base_url="https://chatgpt.com/backend-api/codex",
        request_count=0,
        extra=extra,
    )


def _seed_pool(*entries: PooledCredential) -> None:
    write_credential_pool("openai-codex", [entry.to_dict() for entry in entries])


def test_module_loads_proxy_from_hermes_env_file(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir(parents=True, exist_ok=True)
    (hermes_home / ".env").write_text(
        "HTTP_PROXY=http://proxy.example:7890\nHTTPS_PROXY=http://proxy.example:7890\nALL_PROXY=socks5h://proxy.example:7891\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.delenv("HTTP_PROXY", raising=False)
    monkeypatch.delenv("HTTPS_PROXY", raising=False)
    monkeypatch.delenv("ALL_PROXY", raising=False)

    import importlib
    import sys

    sys.modules.pop("codex_account_manager", None)
    reloaded = importlib.import_module("codex_account_manager")

    assert reloaded.os.getenv("HTTP_PROXY") == "http://proxy.example:7890"
    assert reloaded.os.getenv("HTTPS_PROXY") == "http://proxy.example:7890"
    assert reloaded.os.getenv("ALL_PROXY") == "socks5h://proxy.example:7891"



def test_switch_account_updates_auth_state_and_priority(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    monkeypatch.setattr(cam, "DEFAULT_NOTIFY_EMAIL", "")

    cli_tokens = []
    monkeypatch.setattr(
        cam,
        "_write_codex_cli_tokens",
        lambda access, refresh, last_refresh=None, account_id=None, id_token=None: cli_tokens.append((access, refresh, last_refresh, account_id, id_token)),
    )

    _seed_pool(
        _entry("a11111", "alpha", 0, email="alpha@example.com"),
        _entry("b22222", "beta", 1, email="beta@example.com", plan_type="plus"),
    )

    switched = cam.switch_account("beta")

    assert switched.id == "b22222"
    assert load_pool("openai-codex").entries()[0].id == "b22222"
    assert cam.load_manager_state()["active_credential_id"] == "b22222"
    assert _read_codex_tokens()["tokens"] == {
        "access_token": "access-b22222",
        "refresh_token": "refresh-b22222",
    }
    assert cli_tokens == [("access-b22222", "refresh-b22222", None, None, None)]


def test_switch_account_with_real_cli_writeback_preserves_other_accounts(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    codex_home = tmp_path / ".codex"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setattr(cam, "DEFAULT_NOTIFY_EMAIL", "")

    _seed_pool(
        _entry(
            "a11111",
            "alpha",
            0,
            email="alpha@example.com",
            source="device_code",
            account_id="acct-alpha",
        ),
        _entry(
            "b22222",
            "beta",
            1,
            email="beta@example.com",
            account_id="acct-beta",
        ),
    )
    _save_codex_tokens(
        {
            "access_token": "access-a11111",
            "refresh_token": "refresh-a11111",
            "account_id": "acct-alpha",
        },
        last_refresh="2026-04-13T00:00:00Z",
    )
    cam.save_manager_state({"active_credential_id": "a11111", "active_credential_changed_at": None, "last_auto_switch_at": None, "last_auto_switch_from_credential_id": None, "last_auto_switch_to_credential_id": None, "last_probe": {}, "alerts": {}})

    switched = cam.switch_account("beta")
    entries = load_pool("openai-codex").entries()

    assert switched.id == "b22222"
    assert [entry.id for entry in entries] == ["b22222", "a11111"]
    assert [entry.source for entry in entries] == ["device_code", "manual:device_code"]
    assert entries[0].account_id == "acct-beta"
    assert entries[1].account_id == "acct-alpha"
    assert cam.load_manager_state()["active_credential_id"] == "b22222"
    assert _read_codex_tokens()["tokens"] == {
        "access_token": "access-b22222",
        "refresh_token": "refresh-b22222",
        "account_id": "acct-beta",
    }


def test_classify_probe_failure_detects_auth_quota_and_transient():
    auth_failure = cam.classify_probe_failure(401, "refresh_token_reused: login required")
    quota_failure = cam.classify_probe_failure(429, "Rate limit reached, retry after 120 seconds")
    transient_failure = cam.classify_probe_failure(None, "tls handshake timeout")

    assert auth_failure["status"] == "auth_invalid"
    assert auth_failure["status_code"] == 401

    assert quota_failure["status"] == "rate_limited"
    assert quota_failure["status_code"] == 429
    assert quota_failure["reset_at"] is not None

    assert transient_failure["status"] == "transient_error"
    assert transient_failure["status_code"] is None


def test_active_entry_prefers_codex_cli_auth_account_id_over_stale_state(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    codex_home = tmp_path / ".codex"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    first = _entry("a11111", "alpha", 0, email="alpha@example.com", account_id="acct-alpha")
    second = _entry("b22222", "beta", 1, email="beta@example.com", account_id="acct-beta")
    _seed_pool(first, second)
    cam.save_manager_state({"active_credential_id": "a11111", "active_credential_changed_at": None, "last_auto_switch_at": None, "last_auto_switch_from_credential_id": None, "last_auto_switch_to_credential_id": None, "last_probe": {}, "alerts": {}})
    cam._write_codex_cli_tokens(
        "cli-access",
        "cli-refresh",
        last_refresh="2026-04-13T00:00:00Z",
        account_id="acct-beta",
    )
    monkeypatch.setattr(cam, "_read_codex_tokens", lambda: {"tokens": {"access_token": "hermes-access", "refresh_token": "hermes-refresh", "account_id": "acct-alpha"}})

    active = cam.active_entry()

    assert active is not None
    assert active.id == "b22222"


def test_active_entry_falls_back_to_hermes_auth_when_cli_auth_missing(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    codex_home = tmp_path / ".codex"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    first = _entry("a11111", "alpha@example.com", 0, email="alpha@example.com")
    second = _entry("b22222", "beta@example.com", 1, email="beta@example.com")
    second = replace(second, access_token=_jwt_for_email("beta@example.com"), refresh_token="refresh-beta")
    _seed_pool(first, second)
    cam.save_manager_state({"active_credential_id": "a11111", "active_credential_changed_at": None, "last_auto_switch_at": None, "last_auto_switch_from_credential_id": None, "last_auto_switch_to_credential_id": None, "last_probe": {}, "alerts": {}})
    monkeypatch.setattr(cam, "_read_codex_cli_tokens_raw", lambda: None)
    monkeypatch.setattr(
        cam,
        "_read_codex_tokens",
        lambda: {"tokens": {"access_token": second.access_token, "refresh_token": second.refresh_token or ""}},
    )

    active, source = cam.active_entry_with_source()

    assert active is not None
    assert active.id == "b22222"
    assert source == "hermes_auth"


def test_add_account_uses_email_as_label_and_records_usage_metadata(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    monkeypatch.setattr(cam, "DEFAULT_NOTIFY_EMAIL", "")
    monkeypatch.setattr(
        cam,
        "_codex_device_code_login",
        lambda: {
            "tokens": {
                "access_token": _jwt_for_email("li@example.com"),
                "refresh_token": "***",
            },
            "base_url": cam.DEFAULT_BASE_URL,
            "last_refresh": "2026-04-13T00:00:00Z",
        },
    )
    monkeypatch.setattr(
        cam,
        "_fetch_usage_snapshot",
        lambda entry, timeout=20.0: {
            "email": "li@example.com",
            "account_id": "acct-1",
            "plan_type": "plus",
            "rate_limit": {"allowed": True},
        },
    )

    added = cam.add_account()

    assert added.label == "li@example.com"
    assert added.email == "li@example.com"
    assert added.account_id == "acct-1"
    assert added.plan_type == "plus"


def test_add_account_supports_importing_auth_json_file(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    monkeypatch.setattr(cam, "DEFAULT_NOTIFY_EMAIL", "")
    auth_file = tmp_path / "import-auth.json"
    auth_file.write_text(
        json.dumps(
            {
                "tokens": {
                    "access_token": _jwt_for_email("import@example.com"),
                    "refresh_token": "refresh-import",
                    "id_token": _jwt_for_email("import@example.com"),
                    "account_id": "acct-import",
                },
                "last_refresh": "2026-04-24T08:30:00Z",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    def _device_login_should_not_run():
        raise AssertionError("device login should not run when auth_file is provided")

    monkeypatch.setattr(cam, "_codex_device_code_login", _device_login_should_not_run)
    monkeypatch.setattr(
        cam,
        "_fetch_usage_snapshot",
        lambda entry, timeout=20.0: {
            "email": "import@example.com",
            "account_id": "acct-import",
            "plan_type": "plus",
            "rate_limit": {"allowed": True},
        },
    )

    added = cam.add_account(auth_file=auth_file)

    assert added.label == "import@example.com"
    assert added.email == "import@example.com"
    assert added.refresh_token == "refresh-import"
    assert added.id_token == _jwt_for_email("import@example.com")
    assert added.account_id == "acct-import"
    assert added.last_refresh == "2026-04-24T08:30:00Z"


def test_build_parser_add_includes_auth_file_flag():
    parser = cam.build_parser()

    args = parser.parse_args(["add", "--auth-file", "/tmp/demo-auth.json"])

    assert args.auth_file == "/tmp/demo-auth.json"


def test_add_account_overwrites_existing_same_email_instead_of_creating_duplicate(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    monkeypatch.setattr(cam, "DEFAULT_NOTIFY_EMAIL", "")
    _seed_pool(_entry("a11111", "old-label", 0, email="li@example.com", plan_type="plus"))
    monkeypatch.setattr(
        cam,
        "_codex_device_code_login",
        lambda: {
            "tokens": {
                "access_token": _jwt_for_email("li@example.com"),
                "refresh_token": "refresh-new",
            },
            "base_url": cam.DEFAULT_BASE_URL,
            "last_refresh": "2026-04-13T01:02:03Z",
        },
    )
    monkeypatch.setattr(
        cam,
        "_fetch_usage_snapshot",
        lambda entry, timeout=20.0: {
            "email": "li@example.com",
            "account_id": "acct-new",
            "plan_type": "team",
            "rate_limit": {"allowed": True},
        },
    )

    updated = cam.add_account()
    entries = load_pool("openai-codex").entries()

    assert len(entries) == 1
    assert updated.id == "a11111"
    assert entries[0].id == "a11111"
    assert entries[0].label == "li@example.com"
    assert entries[0].access_token == _jwt_for_email("li@example.com")
    assert entries[0].refresh_token == "refresh-new"
    assert entries[0].account_id == "acct-new"
    assert entries[0].plan_type == "team"


def test_add_account_refreshes_active_same_email_tokens_in_auth_store(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    monkeypatch.setattr(cam, "DEFAULT_NOTIFY_EMAIL", "")
    _seed_pool(_entry("a11111", "old-label", 0, email="li@example.com"))
    cam.save_manager_state({"active_credential_id": "a11111", "active_credential_changed_at": None, "last_auto_switch_at": None, "last_auto_switch_from_credential_id": None, "last_auto_switch_to_credential_id": None, "last_probe": {}, "alerts": {}})

    cli_tokens = []
    monkeypatch.setattr(
        cam,
        "_write_codex_cli_tokens",
        lambda access, refresh, last_refresh=None, account_id=None, id_token=None: cli_tokens.append((access, refresh, last_refresh, account_id, id_token)),
    )
    monkeypatch.setattr(
        cam,
        "_codex_device_code_login",
        lambda: {
            "tokens": {
                "access_token": _jwt_for_email("li@example.com"),
                "refresh_token": "refresh-new",
            },
            "base_url": cam.DEFAULT_BASE_URL,
            "last_refresh": "2026-04-13T01:02:03Z",
        },
    )
    monkeypatch.setattr(
        cam,
        "_fetch_usage_snapshot",
        lambda entry, timeout=20.0: {
            "email": "li@example.com",
            "account_id": "acct-new",
            "plan_type": "team",
            "rate_limit": {"allowed": True},
        },
    )

    updated = cam.add_account()

    assert updated.id == "a11111"
    assert _read_codex_tokens()["tokens"] == {
        "access_token": _jwt_for_email("li@example.com"),
        "refresh_token": "refresh-new",
        "account_id": "acct-new",
    }
    assert cli_tokens == [(_jwt_for_email("li@example.com"), "refresh-new", "2026-04-13T01:02:03Z", "acct-new", None)]


def test_probe_account_uses_usage_snapshot_and_returns_email_and_plan(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    entry = _entry("a11111", "alpha", 0, email="alpha@example.com")
    _seed_pool(entry)
    monkeypatch.setattr(cam, "_refresh_entry_tokens", lambda current: (current, None))
    monkeypatch.setattr(
        cam,
        "_fetch_usage_snapshot",
        lambda current, timeout=20.0: {
            "email": "alpha@example.com",
            "account_id": "acct-a",
            "plan_type": "team",
            "rate_limit": {
                "allowed": True,
                "primary_window": {"used_percent": 12, "reset_at": 1776089199},
                "secondary_window": {"used_percent": 34, "reset_at": 1776391667},
            },
        },
    )

    result = cam.probe_account(entry)

    assert result["status"] == "ok"
    assert result["email"] == "alpha@example.com"
    assert result["plan_type"] == "team"
    assert result["reset_at"] is not None
    assert "套餐=team" in result["message"]
    assert "邮箱=alpha@example.com" in result["message"]


def test_probe_account_marks_usage_blocked_account_as_rate_limited(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    entry = _entry("a11111", "alpha", 0, email="alpha@example.com")
    _seed_pool(entry)
    monkeypatch.setattr(cam, "_refresh_entry_tokens", lambda current: (current, None))
    monkeypatch.setattr(
        cam,
        "_fetch_usage_snapshot",
        lambda current, timeout=20.0: {
            "email": "alpha@example.com",
            "account_id": "acct-a",
            "plan_type": "team",
            "rate_limit": {
                "allowed": False,
                "primary_window": {"used_percent": 100, "reset_at": 1776089199},
                "secondary_window": {"used_percent": 40, "reset_at": 1776391667},
            },
        },
    )

    result = cam.probe_account(entry)

    assert result["status"] == "rate_limited"
    assert result["status_code"] == 429
    assert result["reset_at"] is not None
    assert "当前不允许请求" in result["message"]


def test_probe_account_falls_back_to_existing_access_token_when_refresh_401(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    entry = _entry("a11111", "alpha", 0, email="alpha@example.com")
    _seed_pool(entry)
    monkeypatch.setattr(
        cam,
        "_refresh_entry_tokens",
        lambda current: (
            current,
            {
                "status": "error",
                "status_code": None,
                "message": "Codex token refresh failed with status 401.",
                "reset_at": None,
            },
        ),
    )
    monkeypatch.setattr(
        cam,
        "_fetch_usage_snapshot",
        lambda current, timeout=20.0: {
            "email": "alpha@example.com",
            "account_id": "acct-a",
            "plan_type": "team",
            "rate_limit": {
                "allowed": True,
                "primary_window": {"used_percent": 5, "reset_at": 1776089199},
                "secondary_window": {"used_percent": 41, "reset_at": 1776391667},
            },
        },
    )

    result = cam.probe_account(entry)
    refreshed = next(item for item in load_pool("openai-codex").entries() if item.id == "a11111")

    assert result["status"] == "ok"
    assert result["status_code"] == 200
    assert "刷新令牌失败，但当前 access_token 仍可用" in result["message"]
    assert result["email"] == "alpha@example.com"
    assert refreshed.email == "alpha@example.com"
    assert refreshed.primary_used_percent == 5
    assert refreshed.rate_limit_allowed is True


def test_probe_account_classifies_usage_transport_timeout_as_transient_error(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    entry = _entry("a11111", "alpha", 0, email="alpha@example.com")
    _seed_pool(entry)
    monkeypatch.setattr(cam, "_refresh_entry_tokens", lambda current: (current, None))
    monkeypatch.setattr(
        cam,
        "_probe_request",
        lambda *, entry, model, timeout=20.0: (_ for _ in ()).throw(cam.ProbeError(None, "The handshake operation timed out")),
    )

    result = cam.probe_account(entry)
    refreshed = next(item for item in load_pool("openai-codex").entries() if item.id == "a11111")

    assert result["status"] == "transient_error"
    assert "handshake operation timed out" in result["message"]
    assert refreshed.last_status == "exhausted"
    assert refreshed.last_error_reason == "transient_error"


def test_probe_all_does_not_auto_switch_on_transient_active_error(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    monkeypatch.setattr(cam, "DEFAULT_NOTIFY_EMAIL", "")
    monkeypatch.setattr(cam, "maybe_send_plan_expiry_alert", lambda result, notify_email: False)
    first = _entry("a11111", "alpha", 0)
    second = _entry("b22222", "beta", 1)
    _seed_pool(first, second)
    cam.save_manager_state({"active_credential_id": "a11111", "active_credential_changed_at": None, "last_auto_switch_at": None, "last_auto_switch_from_credential_id": None, "last_auto_switch_to_credential_id": None, "last_probe": {}, "alerts": {}})

    def fake_probe(entry, *, model=cam.DEFAULT_MODEL, skip_request=False):
        if entry.id == "a11111":
            return {
                "id": entry.id,
                "label": entry.label,
                "email": "alpha@example.com",
                "plan_type": "team",
                "plan_expires_at": None,
                "status": "transient_error",
                "status_code": None,
                "message": "tls handshake timeout",
                "reset_at": None,
                "checked_at": cam.now_iso(),
                "active": False,
            }
        return {
            "id": entry.id,
            "label": entry.label,
            "email": "beta@example.com",
            "plan_type": "team",
            "plan_expires_at": None,
            "status": "ok",
            "status_code": 200,
            "message": "ok",
            "reset_at": None,
            "checked_at": cam.now_iso(),
            "active": False,
        }

    monkeypatch.setattr(cam, "probe_account", fake_probe)

    summary = cam.probe_all(auto_switch=True, skip_request=True)

    assert summary["switched_to"] is None
    assert cam.load_manager_state()["active_credential_id"] == "a11111"


def test_load_manager_state_rebuilds_corrupt_json_with_backup(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    state_dir = get_hermes_home() / "codex_account_manager"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = state_dir / "state.json"
    state_path.write_text('{"active_credential_id": "oops"', encoding="utf-8")

    with pytest.raises(cam.ManagerError, match="状态文件损坏"):
        cam.load_manager_state()

    rebuilt = json.loads(state_path.read_text(encoding="utf-8"))
    assert rebuilt["active_credential_id"] is None
    backups = list(state_dir.glob("state.json.corrupt-*"))
    assert backups


def test_read_codex_cli_tokens_raw_raises_on_invalid_json(tmp_path, monkeypatch):
    codex_home = tmp_path / ".codex"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    codex_home.mkdir(parents=True, exist_ok=True)
    (codex_home / "auth.json").write_text('{"tokens": {"access_token": "abc"', encoding="utf-8")

    with pytest.raises(cam.ManagerError, match="auth.json 已损坏"):
        cam._read_codex_cli_tokens_raw()


def test_entry_email_ignores_token_fallback_and_uses_snapshot_or_label():
    entry = _entry("a11111", "work-1", 0)
    entry.access_token = _jwt_for_email("wrong@example.com")

    assert cam._entry_email(entry) == ""
    assert cam._entry_email(entry, {"email": "snapshot@example.com"}) == "snapshot@example.com"


def test_remove_account_supports_email_target(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    _seed_pool(
        _entry("a11111", "work-1", 0, email="alpha@example.com"),
        _entry("b22222", "work-2", 1, email="beta@example.com"),
    )

    removed = cam.remove_account("beta@example.com")
    remaining = load_pool("openai-codex").entries()

    assert removed.id == "b22222"
    assert all(entry.id != "b22222" for entry in remaining)
    assert all((entry.email or "") != "beta@example.com" for entry in remaining)


def test_remove_account_deletes_all_duplicates_when_email_is_ambiguous(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    _seed_pool(
        _entry("a11111", "device_code", 0, email="same@example.com"),
        _entry("b22222", "backup", 1, email="same@example.com"),
        _entry("c33333", "other", 2, email="other@example.com"),
    )
    cam.save_manager_state({"active_credential_id": "a11111", "active_credential_changed_at": None, "last_auto_switch_at": None, "last_auto_switch_from_credential_id": None, "last_auto_switch_to_credential_id": None, "last_probe": {}, "alerts": {}})

    activated = []
    original_activate = cam.activate_entry

    def tracking_activate(entry, *, path=None):
        activated.append(entry.id)
        return original_activate(entry, path=path)

    monkeypatch.setattr(cam, "activate_entry", tracking_activate)

    removed = cam.remove_account("same@example.com")
    remaining = load_pool("openai-codex").entries()

    assert removed.email == "same@example.com"
    assert [entry.id for entry in remaining] == ["c33333"]
    assert cam.load_manager_state()["active_credential_id"] == "c33333"
    assert activated == ["c33333"]



def test_remove_last_account_clears_singletons_so_list_does_not_reseed(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    codex_home = tmp_path / ".codex"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    entry = _entry("a11111", "solo", 0, email="solo@example.com")
    _seed_pool(entry)
    _save_codex_tokens(
        {
            "access_token": entry.access_token,
            "refresh_token": entry.refresh_token or "",
        },
        last_refresh="2026-04-13T00:00:00Z",
    )
    cam._write_codex_cli_tokens(
        entry.access_token,
        entry.refresh_token or "",
        last_refresh="2026-04-13T00:00:00Z",
    )
    cam.save_manager_state({"active_credential_id": "a11111", "active_credential_changed_at": None, "last_auto_switch_at": None, "last_auto_switch_from_credential_id": None, "last_auto_switch_to_credential_id": None, "last_probe": {}, "alerts": {}})

    removed = cam.remove_account("solo@example.com")

    assert removed.id == "a11111"
    assert load_pool("openai-codex").entries() == []
    with pytest.raises(AuthError):
        _read_codex_tokens()
    assert not (codex_home / "auth.json").exists()
    assert cam.load_manager_state()["active_credential_id"] is None



def test_cmd_list_does_not_show_same_current_email_for_other_accounts(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    active = _entry("a11111", "work-1", 0)
    backup = _entry("b22222", "work-2", 1)
    active.access_token = _jwt_for_email("current@example.com")
    backup.access_token = _jwt_for_email("current@example.com")
    _seed_pool(active, backup)
    cam.save_manager_state(
        {
            "active_credential_id": "a11111",
            "last_probe": {
                "b22222": {"email": "backup@example.com"},
            },
            "alerts": {},
        }
    )

    live_result = {
        "id": "a11111",
        "label": "work-1",
        "email": "current@example.com",
        "plan_type": "plus",
        "plan_expires_at": None,
        "status": "ok",
        "status_code": 200,
        "message": "套餐=plus；邮箱=current@example.com；主窗口已用 12%；当前允许请求",
        "reset_at": None,
        "checked_at": cam.now_iso(),
        "active": True,
    }

    def fake_refresh(current):
        updated = cam._replace_pool_entry(
            current.id,
            lambda item: cam._entry_metadata_patch(
                item,
                email="current@example.com",
                plan_type="plus",
                primary_used_percent=12,
                rate_limit_allowed=True,
                usage_checked_at="2026-04-13T00:00:00Z",
            ),
        )
        return updated, live_result

    monkeypatch.setattr(cam, "_refresh_current_entry_for_list", fake_refresh)

    exit_code = cam.cmd_list(SimpleNamespace(json=False))
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "current@example.com [a11111]" in out
    assert "backup@example.com [b22222]" in out
    assert "current@example.com [b22222]" not in out


def test_cmd_list_shows_email_and_live_quota_for_current_account(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    active = _entry("a11111", "work-1", 0)
    backup = _entry("b22222", "backup", 1, email="backup@example.com", plan_type="team")
    _seed_pool(active, backup)
    cam.save_manager_state({"active_credential_id": "a11111", "active_credential_changed_at": None, "last_auto_switch_at": None, "last_auto_switch_from_credential_id": None, "last_auto_switch_to_credential_id": None, "last_probe": {}, "alerts": {}})

    live_result = {
        "id": "a11111",
        "label": "work-1",
        "email": "live@example.com",
        "plan_type": "plus",
        "plan_expires_at": None,
        "status": "ok",
        "status_code": 200,
        "message": "套餐=plus；邮箱=live@example.com；主窗口已用 12%；次窗口已用 34%；当前允许请求",
        "reset_at": None,
        "checked_at": cam.now_iso(),
        "active": True,
    }

    def fake_refresh(current):
        updated = cam._replace_pool_entry(
            current.id,
            lambda item: cam._entry_metadata_patch(
                item,
                email="live@example.com",
                plan_type="plus",
                primary_used_percent=12,
                secondary_used_percent=34,
                rate_limit_allowed=True,
                usage_checked_at="2026-04-13T00:00:00Z",
            ),
        )
        return updated, live_result

    monkeypatch.setattr(cam, "_refresh_current_entry_for_list", fake_refresh)

    exit_code = cam.cmd_list(SimpleNamespace(json=False, refresh_all=False))
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "live@example.com [a11111]" in out
    assert "quota=套餐=plus；邮箱=live@example.com；主窗口已用 12%；次窗口已用 34%；当前允许请求" in out
    assert "backup@example.com [b22222]" in out


def test_cmd_list_refresh_all_probes_every_account_and_uses_live_messages(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    active = _entry("a11111", "alpha", 0, email="alpha@example.com", source="device_code")
    backup = _entry("b22222", "beta", 1, email="beta@example.com")
    _seed_pool(active, backup)
    cam.save_manager_state({"active_credential_id": "a11111", "active_credential_changed_at": None, "last_auto_switch_at": None, "last_auto_switch_from_credential_id": None, "last_auto_switch_to_credential_id": None, "last_probe": {}, "alerts": {}})

    checked = []

    def fake_probe(entry, *, model=cam.DEFAULT_MODEL, skip_request=False):
        checked.append((entry.id, model, skip_request))
        updated = cam._replace_pool_entry(
            entry.id,
            lambda item: cam._entry_metadata_patch(
                item,
                email=f"live-{entry.id}@example.com",
                plan_type="team",
                primary_used_percent=21 if entry.id == "a11111" else 42,
                rate_limit_allowed=True,
                usage_checked_at="2026-04-13T00:00:00Z",
            ),
        )
        return {
            "id": updated.id,
            "label": updated.label,
            "email": f"live-{entry.id}@example.com",
            "plan_type": "team",
            "plan_expires_at": None,
            "status": "ok",
            "status_code": 200,
            "message": f"live-message-{entry.id}",
            "reset_at": None,
            "checked_at": "2026-04-13T00:00:00Z",
            "active": entry.id == "a11111",
        }

    monkeypatch.setattr(cam, "probe_account", fake_probe)

    exit_code = cam.cmd_list(SimpleNamespace(json=False, refresh_all=True))
    out = capsys.readouterr().out

    assert exit_code == 0
    assert checked == [
        ("a11111", cam.DEFAULT_MODEL, False),
        ("b22222", cam.DEFAULT_MODEL, False),
    ]
    assert "live-a11111@example.com [a11111]" in out
    assert "live-b22222@example.com [b22222]" in out
    assert "quota=live-message-a11111" in out
    assert "quota=live-message-b22222" in out


def test_cmd_list_refresh_all_handles_partial_probe_failures(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    active = _entry("a11111", "alpha", 0, email="alpha@example.com", source="device_code")
    backup = _entry("b22222", "beta", 1, email="beta@example.com")
    _seed_pool(active, backup)
    cam.save_manager_state(
        {
            "active_credential_id": "a11111",
            "last_probe": {"b22222": {"email": "snapshot-beta@example.com"}},
            "alerts": {},
        }
    )

    def fake_probe(entry, *, model=cam.DEFAULT_MODEL, skip_request=False):
        if entry.id == "b22222":
            raise RuntimeError("boom")
        updated = cam._replace_pool_entry(
            entry.id,
            lambda item: cam._entry_metadata_patch(
                item,
                email="live-a11111@example.com",
                plan_type="team",
                primary_used_percent=21,
                rate_limit_allowed=True,
                usage_checked_at="2026-04-13T00:00:00Z",
            ),
        )
        return {
            "id": updated.id,
            "label": updated.label,
            "email": "live-a11111@example.com",
            "plan_type": "team",
            "plan_expires_at": None,
            "status": "ok",
            "status_code": 200,
            "message": "live-message-a11111",
            "reset_at": None,
            "checked_at": "2026-04-13T00:00:00Z",
            "active": True,
        }

    monkeypatch.setattr(cam, "probe_account", fake_probe)

    exit_code = cam.cmd_list(SimpleNamespace(json=False, refresh_all=True))
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "live-a11111@example.com [a11111]" in out
    assert "quota=live-message-a11111" in out
    assert "beta@example.com [b22222]" in out


def test_doctor_report_detects_cli_mismatch(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    codex_home = tmp_path / ".codex"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    active = _entry("a11111", "alpha", 0, email="alpha@example.com", source="device_code", account_id="acct-alpha")
    backup = _entry("b22222", "beta", 1, email="beta@example.com", account_id="acct-beta")
    _seed_pool(active, backup)
    cam.save_manager_state({"active_credential_id": "a11111", "active_credential_changed_at": None, "last_auto_switch_at": None, "last_auto_switch_from_credential_id": None, "last_auto_switch_to_credential_id": None, "last_probe": {}, "alerts": {}})
    _save_codex_tokens(
        {
            "access_token": active.access_token,
            "refresh_token": active.refresh_token or "",
            "account_id": "acct-alpha",
        },
        last_refresh="2026-04-13T00:00:00Z",
    )
    cam._write_codex_cli_tokens(
        backup.access_token,
        backup.refresh_token or "",
        last_refresh="2026-04-13T00:00:00Z",
        account_id="acct-beta",
    )

    report = cam.doctor_report()

    assert report["overall_status"] == "warn"
    assert report["active"]["id"] == "a11111"
    assert report["resolved_active"]["id"] == "b22222"
    assert report["resolved_active_source"] == "codex_cli_auth"
    assert report["checks"]["pool_first_matches_active"] is True
    assert report["checks"]["hermes_matches_active"] is True
    assert report["checks"]["cli_matches_active"] is False
    assert any("Codex CLI" in issue for issue in report["issues"])


def test_doctor_fix_rewrites_cli_auth_to_active_account(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    codex_home = tmp_path / ".codex"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    active = _entry("a11111", "alpha", 0, email="alpha@example.com", source="device_code", account_id="acct-alpha")
    backup = _entry("b22222", "beta", 1, email="beta@example.com", account_id="acct-beta")
    _seed_pool(active, backup)
    cam.save_manager_state({"active_credential_id": "a11111", "active_credential_changed_at": None, "last_auto_switch_at": None, "last_auto_switch_from_credential_id": None, "last_auto_switch_to_credential_id": None, "last_probe": {}, "alerts": {}})
    _save_codex_tokens(
        {
            "access_token": active.access_token,
            "refresh_token": active.refresh_token or "",
            "account_id": "acct-alpha",
        },
        last_refresh="2026-04-13T00:00:00Z",
    )
    cam._write_codex_cli_tokens(
        backup.access_token,
        backup.refresh_token or "",
        last_refresh="2026-04-13T00:00:00Z",
        account_id="acct-beta",
    )

    fixed = cam.doctor_fix()

    assert fixed["fixed"] is True
    assert fixed["before"]["checks"]["cli_matches_active"] is False
    assert fixed["after"]["overall_status"] == "ok"
    assert fixed["after"]["checks"]["cli_matches_active"] is True
    assert fixed["after"]["checks"]["hermes_matches_active"] is True


def test_entry_quota_bits_reads_usage_fields_from_extra_metadata():
    entry = _entry("a11111", "alpha", 0)
    entry = cam._entry_metadata_patch(
        entry,
        primary_used_percent=12,
        secondary_used_percent=34,
        rate_limit_allowed=True,
        primary_reset_at="2026-04-13T01:02:03Z",
    )

    bits = cam._entry_quota_bits(entry)

    assert bits == [
        "主窗口已用 12%",
        "次窗口已用 34%",
        "允许请求",
        "主窗口重置=2026-04-13T01:02:03Z",
    ]


def test_entry_snapshot_reads_account_id_from_extra_metadata():
    entry = _entry("a11111", "alpha", 0, email="alpha@example.com")
    entry = cam._entry_metadata_patch(entry, account_id="acct-alpha")

    snapshot = cam._entry_snapshot(entry)

    assert snapshot is not None
    assert snapshot["account_id"] == "acct-alpha"


def test_probe_all_auto_switches_when_active_account_unhealthy(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    monkeypatch.setattr(cam, "DEFAULT_NOTIFY_EMAIL", "")
    monkeypatch.setattr(cam, "_save_codex_tokens", lambda tokens, last_refresh=None: None)
    monkeypatch.setattr(cam, "_write_codex_cli_tokens", lambda access, refresh, last_refresh=None, account_id=None, id_token=None: None)
    monkeypatch.setattr(cam, "maybe_send_invalid_alert", lambda result, notify_email: False)
    monkeypatch.setattr(cam, "maybe_send_plan_expiry_alert", lambda result, notify_email: False)

    first = _entry("a11111", "alpha", 0)
    second = _entry("b22222", "beta", 1)
    _seed_pool(first, second)
    cam.save_manager_state({"active_credential_id": "a11111", "active_credential_changed_at": None, "last_auto_switch_at": None, "last_auto_switch_from_credential_id": None, "last_auto_switch_to_credential_id": None, "last_probe": {}, "alerts": {}})

    call_counts = {"a11111": 0, "b22222": 0}

    def fake_probe(entry, *, model=cam.DEFAULT_MODEL, skip_request=False):
        call_counts[entry.id] += 1
        if entry.id == "a11111":
            return {
                "id": entry.id,
                "label": entry.label,
                "email": "alpha@example.com",
                "plan_type": "plus",
                "plan_expires_at": None,
                "status": "quota_exhausted",
                "status_code": 402,
                "message": "额度已用完",
                "reset_at": None,
                "checked_at": cam.now_iso(),
                "active": False,
            }
        return {
            "id": entry.id,
            "label": entry.label,
            "email": "beta@example.com",
            "plan_type": "plus",
            "plan_expires_at": None,
            "status": "ok",
            "status_code": 200,
            "message": "ok",
            "reset_at": None,
            "checked_at": cam.now_iso(),
            "active": False,
        }

    monkeypatch.setattr(cam, "probe_account", fake_probe)

    summary = cam.probe_all(auto_switch=True, skip_request=True)
    state = cam.load_manager_state()

    assert summary["active_source"] == "state"
    assert summary["switched_to"] == {"id": "b22222", "label": "beta"}
    assert summary["confirmed_status"] == "quota_exhausted"
    assert summary["confirmation_probe"]["id"] == "a11111"
    assert summary["auto_switch_skipped"] is None
    assert call_counts["a11111"] == 2
    assert state["active_credential_id"] == "b22222"
    assert state["last_auto_switch_from_credential_id"] == "a11111"
    assert state["last_auto_switch_to_credential_id"] == "b22222"
    assert state["last_auto_switch_at"] is not None


def test_probe_all_does_not_auto_switch_when_confirmation_recovers(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    monkeypatch.setattr(cam, "DEFAULT_NOTIFY_EMAIL", "")
    monkeypatch.setattr(cam, "maybe_send_invalid_alert", lambda result, notify_email: False)
    monkeypatch.setattr(cam, "maybe_send_plan_expiry_alert", lambda result, notify_email: False)

    first = _entry("a11111", "alpha", 0)
    second = _entry("b22222", "beta", 1)
    _seed_pool(first, second)
    cam.save_manager_state({"active_credential_id": "a11111", "active_credential_changed_at": None, "last_auto_switch_at": None, "last_auto_switch_from_credential_id": None, "last_auto_switch_to_credential_id": None, "last_probe": {}, "alerts": {}})

    call_counts = {"a11111": 0, "b22222": 0}

    def fake_probe(entry, *, model=cam.DEFAULT_MODEL, skip_request=False):
        call_counts[entry.id] += 1
        if entry.id == "a11111" and call_counts[entry.id] == 1:
            return {
                "id": entry.id,
                "label": entry.label,
                "email": "alpha@example.com",
                "plan_type": "plus",
                "plan_expires_at": None,
                "status": "quota_exhausted",
                "status_code": 402,
                "message": "额度已用完",
                "reset_at": None,
                "checked_at": cam.now_iso(),
                "active": False,
            }
        if entry.id == "a11111":
            return {
                "id": entry.id,
                "label": entry.label,
                "email": "alpha@example.com",
                "plan_type": "plus",
                "plan_expires_at": None,
                "status": "ok",
                "status_code": 200,
                "message": "恢复正常",
                "reset_at": None,
                "checked_at": cam.now_iso(),
                "active": False,
            }
        return {
            "id": entry.id,
            "label": entry.label,
            "email": "beta@example.com",
            "plan_type": "plus",
            "plan_expires_at": None,
            "status": "ok",
            "status_code": 200,
            "message": "ok",
            "reset_at": None,
            "checked_at": cam.now_iso(),
            "active": False,
        }

    monkeypatch.setattr(cam, "probe_account", fake_probe)

    summary = cam.probe_all(auto_switch=True, skip_request=True)

    assert summary["switched_to"] is None
    assert summary["confirmed_status"] == "ok"
    assert summary["auto_switch_skipped"] == "confirmation:ok"
    assert call_counts["a11111"] == 2
    assert cam.load_manager_state()["active_credential_id"] == "a11111"


def test_probe_all_respects_auto_switch_cooldown(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    monkeypatch.setattr(cam, "DEFAULT_NOTIFY_EMAIL", "")
    monkeypatch.setattr(cam, "maybe_send_invalid_alert", lambda result, notify_email: False)
    monkeypatch.setattr(cam, "maybe_send_plan_expiry_alert", lambda result, notify_email: False)

    first = _entry("a11111", "alpha", 0)
    second = _entry("b22222", "beta", 1)
    _seed_pool(first, second)
    cam.save_manager_state({
        "active_credential_id": "a11111",
        "active_credential_changed_at": None,
        "last_auto_switch_at": cam.now_iso(),
        "last_auto_switch_from_credential_id": "a11111",
        "last_auto_switch_to_credential_id": "b22222",
        "last_probe": {},
        "alerts": {},
    })

    calls = []

    def fake_probe(entry, *, model=cam.DEFAULT_MODEL, skip_request=False):
        calls.append(entry.id)
        if entry.id == "a11111":
            return {
                "id": entry.id,
                "label": entry.label,
                "email": "alpha@example.com",
                "plan_type": "plus",
                "plan_expires_at": None,
                "status": "rate_limited",
                "status_code": 429,
                "message": "请求频率限制",
                "reset_at": cam.now_iso(),
                "checked_at": cam.now_iso(),
                "active": False,
            }
        return {
            "id": entry.id,
            "label": entry.label,
            "email": "beta@example.com",
            "plan_type": "plus",
            "plan_expires_at": None,
            "status": "ok",
            "status_code": 200,
            "message": "ok",
            "reset_at": None,
            "checked_at": cam.now_iso(),
            "active": False,
        }

    monkeypatch.setattr(cam, "probe_account", fake_probe)

    summary = cam.probe_all(auto_switch=True, skip_request=True)

    assert summary["switched_to"] is None
    assert summary["auto_switch_skipped"] == "cooldown"
    assert summary["confirmation_probe"] is None
    assert calls == ["a11111", "b22222"]
    assert cam.load_manager_state()["active_credential_id"] == "a11111"


def test_probe_all_auto_switch_prefers_lowest_usage_healthy_account(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    monkeypatch.setattr(cam, "DEFAULT_NOTIFY_EMAIL", "")
    monkeypatch.setattr(cam, "_save_codex_tokens", lambda tokens, last_refresh=None: None)
    monkeypatch.setattr(cam, "_write_codex_cli_tokens", lambda access, refresh, last_refresh=None, account_id=None, id_token=None: None)
    monkeypatch.setattr(cam, "maybe_send_invalid_alert", lambda result, notify_email: False)
    monkeypatch.setattr(cam, "maybe_send_plan_expiry_alert", lambda result, notify_email: False)

    first = _entry("a11111", "alpha", 0)
    second = _entry("b22222", "beta", 1)
    third = _entry("c33333", "gamma", 2)
    _seed_pool(first, second, third)
    cam.save_manager_state({"active_credential_id": "a11111", "active_credential_changed_at": None, "last_auto_switch_at": None, "last_auto_switch_from_credential_id": None, "last_auto_switch_to_credential_id": None, "last_probe": {}, "alerts": {}})

    def fake_probe(entry, *, model=cam.DEFAULT_MODEL, skip_request=False):
        mapping = {
            "a11111": {
                "id": "a11111",
                "label": "alpha",
                "email": "alpha@example.com",
                "plan_type": "team",
                "plan_expires_at": None,
                "status": "rate_limited",
                "status_code": 429,
                "message": "当前不允许请求",
                "reset_at": "2026-04-13T17:42:31Z",
                "checked_at": cam.now_iso(),
                "active": False,
                "primary_used_percent": 100,
                "secondary_used_percent": 40,
                "rate_limit_allowed": False,
            },
            "b22222": {
                "id": "b22222",
                "label": "beta",
                "email": "beta@example.com",
                "plan_type": "plus",
                "plan_expires_at": None,
                "status": "ok",
                "status_code": 200,
                "message": "ok",
                "reset_at": None,
                "checked_at": cam.now_iso(),
                "active": False,
                "primary_used_percent": 42,
                "secondary_used_percent": 22,
                "rate_limit_allowed": True,
            },
            "c33333": {
                "id": "c33333",
                "label": "gamma",
                "email": "gamma@example.com",
                "plan_type": "team",
                "plan_expires_at": None,
                "status": "ok",
                "status_code": 200,
                "message": "ok",
                "reset_at": None,
                "checked_at": cam.now_iso(),
                "active": False,
                "primary_used_percent": 3,
                "secondary_used_percent": 36,
                "rate_limit_allowed": True,
            },
        }
        return mapping[entry.id]

    monkeypatch.setattr(cam, "probe_account", fake_probe)

    summary = cam.probe_all(auto_switch=True, skip_request=True)

    assert summary["active_source"] == "state"
    assert summary["switched_to"] == {"id": "c33333", "label": "gamma"}
    assert cam.load_manager_state()["active_credential_id"] == "c33333"


def test_invalid_alert_email_includes_specific_account_email(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    monkeypatch.setattr(cam, "DEFAULT_NOTIFY_EMAIL", "notify@example.com")
    sent = []
    monkeypatch.setattr(cam, "send_email", lambda subject, body, to_email: sent.append((subject, body, to_email)))

    ok = cam.maybe_send_invalid_alert(
        {
            "id": "abc123",
            "label": "备用号",
            "email": "real@example.com",
            "plan_type": "plus",
            "status": "auth_invalid",
            "status_code": 401,
            "message": "refresh_token_reused",
        },
        None,
    )

    assert ok is True
    assert sent
    subject, body, to_email = sent[0]
    assert to_email == "notify@example.com"
    assert "real@example.com" in subject
    assert "账号邮箱: real@example.com" in body
    assert "账号标识: 备用号 (abc123)" in body


def test_plan_expiry_alert_sent_when_plus_or_team_expires_within_3_days(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    monkeypatch.setattr(cam, "DEFAULT_NOTIFY_EMAIL", "notify@example.com")
    sent = []
    monkeypatch.setattr(cam, "send_email", lambda subject, body, to_email: sent.append((subject, body, to_email)))
    plan_expires_at = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat().replace("+00:00", "Z")

    ok = cam.maybe_send_plan_expiry_alert(
        {
            "id": "team01",
            "label": "team01",
            "email": "team@example.com",
            "plan_type": "team",
            "plan_expires_at": plan_expires_at,
        },
        None,
    )

    assert ok is True
    assert sent
    subject, body, to_email = sent[0]
    assert to_email == "notify@example.com"
    assert "team@example.com" in subject
    assert "Plus/Team 资格小于 3 天" in body
    assert plan_expires_at in body


def test_execute_command_with_auto_switch_retries_in_same_workdir_and_env(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    monkeypatch.setattr(cam, "DEFAULT_NOTIFY_EMAIL", "")
    monkeypatch.setattr(cam, "_save_codex_tokens", lambda tokens, last_refresh=None: None)
    monkeypatch.setattr(cam, "_write_codex_cli_tokens", lambda access, refresh, last_refresh=None, account_id=None, id_token=None: None)
    monkeypatch.setattr(cam, "maybe_send_invalid_alert", lambda result, notify_email: False)

    first = _entry("a11111", "alpha", 0, email="alpha@example.com")
    second = _entry("b22222", "beta", 1, email="beta@example.com")
    _seed_pool(first, second)
    cam.save_manager_state({"active_credential_id": "a11111", "active_credential_changed_at": None, "last_auto_switch_at": None, "last_auto_switch_from_credential_id": None, "last_auto_switch_to_credential_id": None, "last_probe": {}, "alerts": {}})

    calls = []

    def fake_run(command, shell, text, capture_output, env, cwd):
        calls.append({"command": command, "env": env, "cwd": cwd})
        if len(calls) == 1:
            return SimpleNamespace(returncode=429, stdout="quota hit", stderr="Too Many Requests")
        return SimpleNamespace(returncode=0, stdout="second account ok", stderr="")

    monkeypatch.setattr(cam.subprocess, "run", fake_run)
    monkeypatch.setattr(cam, "probe_all", lambda auto_switch=False, notify_email=None, skip_request=True: {
        "results": [
            {"id": "a11111", "label": "alpha", "status": "rate_limited", "rate_limit_allowed": False, "primary_used_percent": 100, "secondary_used_percent": 80, "priority": 0},
            {"id": "b22222", "label": "beta", "status": "ok", "rate_limit_allowed": True, "primary_used_percent": 1, "secondary_used_percent": 5, "priority": 1},
        ]
    })

    returncode, output = cam.execute_command_with_auto_switch(
        "codex exec 'fix bug'",
        cwd=str(tmp_path / "repo"),
        env={"FOO": "bar"},
        stream_output=False,
    )

    assert returncode == 0
    assert "quota hit" in output
    assert "second account ok" in output
    assert len(calls) == 2
    assert all(call["command"] == "codex exec 'fix bug'" for call in calls)
    assert all(call["cwd"] == str(tmp_path / "repo") for call in calls)
    assert all(call["env"]["FOO"] == "bar" for call in calls)
    assert cam.load_manager_state()["active_credential_id"] == "b22222"
