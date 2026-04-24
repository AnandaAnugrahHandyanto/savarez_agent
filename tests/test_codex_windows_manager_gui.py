from __future__ import annotations

import json
from pathlib import Path

import codex_windows_manager as cwm
import pytest

import codex_windows_manager_gui as gui


@pytest.fixture
def win_env(tmp_path, monkeypatch):
    appdata = tmp_path / "AppData" / "Roaming"
    userprofile = tmp_path / "User"
    monkeypatch.setenv("APPDATA", str(appdata))
    monkeypatch.setenv("USERPROFILE", str(userprofile))
    return tmp_path


def _write_codex_auth(path: Path, *, access_token: str, refresh_token: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "tokens": {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _account(account_id: str, email: str, *, access: str, refresh: str) -> cwm.StoredAccount:
    return cwm.StoredAccount(
        id=account_id,
        label=email,
        email=email,
        access_token=access,
        refresh_token=refresh,
        source="imported",
        created_at="2026-04-13T00:00:00Z",
        updated_at="2026-04-13T00:00:00Z",
    )


def test_controller_load_rows_marks_active_account(win_env):
    first = _account("a1", "one@example.com", access="access-a1", refresh="refresh-a1")
    second = _account("b2", "two@example.com", access="access-b2", refresh="refresh-b2")
    cwm.save_accounts([first, second])
    cwm.save_state({"active_account_id": "b2", "updated_at": "2026-04-13T00:00:00Z"})

    controller = gui.CodexWindowsManagerController(manager=cwm)
    rows = controller.load_rows()

    assert [row["email"] for row in rows] == ["one@example.com", "two@example.com"]
    assert rows[0]["active"] is False
    assert rows[1]["active"] is True


def test_controller_switch_selected_row_updates_state_and_auth(win_env):
    first = _account("a1", "one@example.com", access="access-a1", refresh="refresh-a1")
    second = _account("b2", "two@example.com", access="access-b2", refresh="refresh-b2")
    cwm.save_accounts([first, second])
    cwm.save_state({"active_account_id": "a1", "updated_at": "2026-04-13T00:00:00Z"})
    _write_codex_auth(cwm.codex_auth_file(), access_token="access-a1", refresh_token="refresh-a1")

    controller = gui.CodexWindowsManagerController(manager=cwm)
    account = controller.switch_by_row_index(1)
    payload = json.loads(cwm.codex_auth_file().read_text(encoding="utf-8"))

    assert account.id == "b2"
    assert cwm.load_state()["active_account_id"] == "b2"
    assert payload["tokens"]["access_token"] == "access-b2"
    assert payload["tokens"]["refresh_token"] == "refresh-b2"


def test_controller_remove_selected_row_reloads_rows_and_repoints_active(win_env):
    first = _account("a1", "one@example.com", access="access-a1", refresh="refresh-a1")
    second = _account("b2", "two@example.com", access="access-b2", refresh="refresh-b2")
    cwm.save_accounts([first, second])
    cwm.save_state({"active_account_id": "a1", "updated_at": "2026-04-13T00:00:00Z"})
    _write_codex_auth(cwm.codex_auth_file(), access_token="access-a1", refresh_token="refresh-a1")

    controller = gui.CodexWindowsManagerController(manager=cwm)
    removed = controller.remove_by_row_index(0)
    rows = controller.load_rows()

    assert removed.id == "a1"
    assert [row["id"] for row in rows] == ["b2"]
    assert rows[0]["active"] is True


def test_controller_doctor_summary_reports_mismatch(win_env):
    first = _account("a1", "one@example.com", access="access-a1", refresh="refresh-a1")
    cwm.save_accounts([first])
    cwm.save_state({"active_account_id": "a1", "updated_at": "2026-04-13T00:00:00Z"})
    _write_codex_auth(cwm.codex_auth_file(), access_token="wrong-access", refresh_token="wrong-refresh")

    controller = gui.CodexWindowsManagerController(manager=cwm)
    summary = controller.doctor_summary()

    assert "one@example.com" in summary
    assert "不一致" in summary
