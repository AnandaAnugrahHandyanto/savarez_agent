from __future__ import annotations

import json
from pathlib import Path

import pytest

import codex_windows_manager as cwm


@pytest.fixture
def win_env(tmp_path, monkeypatch):
    appdata = tmp_path / "AppData" / "Roaming"
    userprofile = tmp_path / "User"
    monkeypatch.setenv("APPDATA", str(appdata))
    monkeypatch.setenv("USERPROFILE", str(userprofile))
    return tmp_path


def _write_codex_auth(path: Path, *, access_token: str, refresh_token: str, id_token: str | None = None, account_id: str | None = None):
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "tokens": {
            "access_token": access_token,
            "refresh_token": refresh_token,
        }
    }
    if id_token:
        payload["tokens"]["id_token"] = id_token
    if account_id:
        payload["tokens"]["account_id"] = account_id
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _jwt(payload: dict) -> str:
    import base64

    def _enc(data: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")

    return f"{_enc({'alg': 'none', 'typ': 'JWT'})}.{_enc(payload)}.sig"


def test_windows_paths_prefer_appdata_and_userprofile(win_env):
    root = cwm.manager_root()

    assert root == win_env / "AppData" / "Roaming" / "CodexAccountManager"
    assert cwm.accounts_file() == root / "accounts.json"
    assert cwm.state_file() == root / "state.json"
    assert cwm.codex_auth_file() == win_env / "User" / ".codex" / "auth.json"



def test_add_current_account_imports_existing_codex_login_and_extracts_email(win_env):
    auth_path = cwm.codex_auth_file()
    id_token = _jwt({"email": "win@example.com"})
    _write_codex_auth(auth_path, access_token="access-1", refresh_token="refresh-1", id_token=id_token, account_id="acct-1")

    account = cwm.add_current_account(label=None)
    accounts = cwm.load_accounts()
    state = cwm.load_state()

    assert account.email == "win@example.com"
    assert account.label == "win@example.com"
    assert len(accounts) == 1
    assert state["active_account_id"] == account.id



def test_switch_account_writes_selected_tokens_back_to_codex_auth(win_env):
    first = cwm.StoredAccount(
        id="a1",
        label="one@example.com",
        email="one@example.com",
        access_token="access-a1",
        refresh_token="refresh-a1",
        id_token="id-a1",
        account_id="acct-a1",
        source="imported",
        created_at="2026-04-13T00:00:00Z",
        updated_at="2026-04-13T00:00:00Z",
    )
    second = cwm.StoredAccount(
        id="b2",
        label="two@example.com",
        email="two@example.com",
        access_token="access-b2",
        refresh_token="refresh-b2",
        id_token="id-b2",
        account_id="acct-b2",
        source="imported",
        created_at="2026-04-13T00:00:00Z",
        updated_at="2026-04-13T00:00:00Z",
    )
    cwm.save_accounts([first, second])
    cwm.save_state({"active_account_id": "a1", "updated_at": "2026-04-13T00:00:00Z"})

    selected = cwm.switch_account("two@example.com")
    payload = json.loads(cwm.codex_auth_file().read_text(encoding="utf-8"))
    state = cwm.load_state()

    assert selected.id == "b2"
    assert payload["tokens"]["access_token"] == "access-b2"
    assert payload["tokens"]["refresh_token"] == "refresh-b2"
    assert payload["tokens"]["id_token"] == "id-b2"
    assert payload["tokens"]["account_id"] == "acct-b2"
    assert state["active_account_id"] == "b2"



def test_remove_account_deletes_target_and_repoints_active_to_next(win_env):
    first = cwm.StoredAccount(
        id="a1",
        label="one@example.com",
        email="one@example.com",
        access_token="access-a1",
        refresh_token="refresh-a1",
        source="imported",
        created_at="2026-04-13T00:00:00Z",
        updated_at="2026-04-13T00:00:00Z",
    )
    second = cwm.StoredAccount(
        id="b2",
        label="two@example.com",
        email="two@example.com",
        access_token="access-b2",
        refresh_token="refresh-b2",
        source="imported",
        created_at="2026-04-13T00:00:00Z",
        updated_at="2026-04-13T00:00:00Z",
    )
    cwm.save_accounts([first, second])
    cwm.save_state({"active_account_id": "a1", "updated_at": "2026-04-13T00:00:00Z"})
    _write_codex_auth(cwm.codex_auth_file(), access_token="access-a1", refresh_token="refresh-a1")

    removed = cwm.remove_account("one@example.com")
    remaining = cwm.load_accounts()
    state = cwm.load_state()
    payload = json.loads(cwm.codex_auth_file().read_text(encoding="utf-8"))

    assert removed.id == "a1"
    assert [item.id for item in remaining] == ["b2"]
    assert state["active_account_id"] == "b2"
    assert payload["tokens"]["access_token"] == "access-b2"
    assert payload["tokens"]["refresh_token"] == "refresh-b2"



def test_remove_last_account_clears_active_state_and_deletes_codex_auth(win_env):
    only = cwm.StoredAccount(
        id="a1",
        label="one@example.com",
        email="one@example.com",
        access_token="access-a1",
        refresh_token="refresh-a1",
        source="imported",
        created_at="2026-04-13T00:00:00Z",
        updated_at="2026-04-13T00:00:00Z",
    )
    cwm.save_accounts([only])
    cwm.save_state({"active_account_id": "a1", "updated_at": "2026-04-13T00:00:00Z"})
    _write_codex_auth(cwm.codex_auth_file(), access_token="access-a1", refresh_token="refresh-a1")

    removed = cwm.remove_account("one@example.com")

    assert removed.id == "a1"
    assert cwm.load_accounts() == []
    assert cwm.load_state()["active_account_id"] is None
    assert not cwm.codex_auth_file().exists()



def test_write_codex_auth_preserves_existing_non_token_fields(win_env):
    auth_path = cwm.codex_auth_file()
    auth_path.parent.mkdir(parents=True, exist_ok=True)
    auth_path.write_text(
        json.dumps(
            {
                "tokens": {
                    "access_token": "old-access",
                    "refresh_token": "old-refresh",
                    "id_token": "old-id",
                },
                "last_refresh": "2026-04-12T00:00:00Z",
                "profile": {"name": "demo"},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    account = cwm.StoredAccount(
        id="b2",
        label="two@example.com",
        email="two@example.com",
        access_token="access-b2",
        refresh_token="refresh-b2",
        id_token="id-b2",
        account_id="acct-b2",
        source="imported",
        created_at="2026-04-13T00:00:00Z",
        updated_at="2026-04-13T00:00:00Z",
    )

    cwm.write_codex_auth(account)
    payload = json.loads(auth_path.read_text(encoding="utf-8"))

    assert payload["tokens"]["access_token"] == "access-b2"
    assert payload["tokens"]["refresh_token"] == "refresh-b2"
    assert payload["tokens"]["id_token"] == "id-b2"
    assert payload["tokens"]["account_id"] == "acct-b2"
    assert payload["last_refresh"] == "2026-04-12T00:00:00Z"
    assert payload["profile"] == {"name": "demo"}



def test_resolve_target_supports_index_id_email_and_label(win_env):
    first = cwm.StoredAccount(
        id="a1",
        label="Alpha",
        email="one@example.com",
        access_token="access-a1",
        refresh_token="refresh-a1",
        source="imported",
        created_at="2026-04-13T00:00:00Z",
        updated_at="2026-04-13T00:00:00Z",
    )
    second = cwm.StoredAccount(
        id="b2",
        label="Beta",
        email="two@example.com",
        access_token="access-b2",
        refresh_token="refresh-b2",
        source="imported",
        created_at="2026-04-13T00:00:00Z",
        updated_at="2026-04-13T00:00:00Z",
    )
    accounts = [first, second]

    assert cwm.resolve_account(accounts, "1").id == "a1"
    assert cwm.resolve_account(accounts, "b2").id == "b2"
    assert cwm.resolve_account(accounts, "two@example.com").id == "b2"
    assert cwm.resolve_account(accounts, "Beta").id == "b2"

    with pytest.raises(cwm.ManagerError):
        cwm.resolve_account(accounts, "missing")
