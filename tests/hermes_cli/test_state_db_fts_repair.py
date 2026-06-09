"""Repair malformed state.db FTS schema rows without losing sessions."""

from __future__ import annotations

import contextlib
import io
import os
import sqlite3
import subprocess
import sys
import types
from argparse import Namespace
from pathlib import Path

import hermes_cli.doctor as doctor_mod
from hermes_state import SessionDB, repair_state_db_fts_schema


def _seed_state_db(db_path: Path) -> None:
    db = SessionDB(db_path=db_path)
    try:
        db.create_session("s1", source="cli")
        db.append_message("s1", role="user", content="the quick brown fox")
        db.append_message("s1", role="assistant", content="the lazy dog")
    finally:
        db.close()


def _inject_duplicate_messages_fts_schema_row(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA writable_schema=ON")
        conn.execute(
            "INSERT INTO sqlite_schema(type, name, tbl_name, rootpage, sql) "
            "VALUES ('table', 'messages_fts', 'messages_fts', 0, ?) ",
            ("CREATE TABLE messages_fts(x)",),
        )
        conn.commit()
    finally:
        conn.close()


def _assert_duplicate_fts_schema_breaks_raw_sqlite(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        try:
            conn.execute("PRAGMA journal_mode").fetchall()
        except sqlite3.DatabaseError as exc:
            assert "malformed database schema" in str(exc)
            assert "table messages_fts already exists" in str(exc)
        else:  # pragma: no cover - defensive assertion message
            raise AssertionError("corrupt duplicate messages_fts schema row should break SQLite prepare")
    finally:
        conn.close()


def _setup_doctor_env(monkeypatch, tmp_path: Path) -> Path:
    home = tmp_path / ".hermes"
    home.mkdir(parents=True, exist_ok=True)
    (home / "config.yaml").write_text("memory: {}\n", encoding="utf-8")

    project = tmp_path / "project"
    project.mkdir(exist_ok=True)
    venv_bin_dir = project / "venv" / "bin"
    venv_bin_dir.mkdir(parents=True, exist_ok=True)
    hermes_bin = venv_bin_dir / "hermes"
    hermes_bin.write_text("#!/usr/bin/env python\n# entry point\n", encoding="utf-8")
    hermes_bin.chmod(0o755)

    monkeypatch.setattr(doctor_mod, "HERMES_HOME", home)
    monkeypatch.setattr(doctor_mod, "PROJECT_ROOT", project)
    monkeypatch.setattr(doctor_mod, "_DHH", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    fake_model_tools = types.SimpleNamespace(
        check_tool_availability=lambda *a, **kw: ([], []),
        TOOLSET_REQUIREMENTS={},
    )
    monkeypatch.setitem(sys.modules, "model_tools", fake_model_tools)

    try:
        from hermes_cli import auth as _auth_mod

        monkeypatch.setattr(_auth_mod, "get_nous_auth_status", lambda: {})
        monkeypatch.setattr(_auth_mod, "get_codex_auth_status", lambda: {})
        monkeypatch.setattr(_auth_mod, "get_gemini_oauth_auth_status", lambda: {})
        monkeypatch.setattr(_auth_mod, "get_minimax_oauth_auth_status", lambda: {})
        monkeypatch.setattr(_auth_mod, "get_xai_oauth_auth_status", lambda: {})
    except Exception:
        pass

    try:
        import httpx

        monkeypatch.setattr(
            httpx,
            "get",
            lambda *a, **kw: types.SimpleNamespace(status_code=200),
        )
    except Exception:
        pass

    return home


def test_repair_state_db_fts_schema_recovers_duplicate_virtual_table_row(tmp_path):
    db_path = tmp_path / "state.db"
    _seed_state_db(db_path)
    _inject_duplicate_messages_fts_schema_row(db_path)
    _assert_duplicate_fts_schema_breaks_raw_sqlite(db_path)

    result = repair_state_db_fts_schema(db_path)

    assert result.repaired is True
    assert result.messages_indexed == 2
    assert result.trigram_messages_indexed == 2
    assert result.backup_path is not None
    assert result.backup_path.exists()

    db = SessionDB(db_path=db_path)
    try:
        assert db.session_count() == 1
        assert db.message_count() == 2
        hits = db.search_messages("quick", limit=5)
        assert any(hit["session_id"] == "s1" for hit in hits)
    finally:
        db.close()


def test_sessiondb_auto_repairs_duplicate_fts_schema_on_startup(tmp_path):
    db_path = tmp_path / "state.db"
    _seed_state_db(db_path)
    _inject_duplicate_messages_fts_schema_row(db_path)
    _assert_duplicate_fts_schema_breaks_raw_sqlite(db_path)

    db = SessionDB(db_path=db_path)
    try:
        assert db.session_count() == 1
        assert db.message_count() == 2
        hits = db.search_messages("quick", limit=5)
        assert any(hit["session_id"] == "s1" for hit in hits)
    finally:
        db.close()


def test_doctor_fix_repairs_duplicate_messages_fts_schema(monkeypatch, tmp_path):
    home = _setup_doctor_env(monkeypatch, tmp_path)
    db_path = home / "state.db"
    _seed_state_db(db_path)
    _inject_duplicate_messages_fts_schema_row(db_path)
    _assert_duplicate_fts_schema_breaks_raw_sqlite(db_path)

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        doctor_mod.run_doctor(Namespace(fix=True))
    output = buf.getvalue()

    assert "Rebuilt state.db FTS schema" in output
    assert "2 messages indexed" in output

    db = SessionDB(db_path=db_path)
    try:
        assert db.session_count() == 1
        assert db.message_count() == 2
    finally:
        db.close()



def test_sessions_repair_cli_check_only_and_repair(tmp_path):
    home = tmp_path / ".hermes"
    home.mkdir(parents=True, exist_ok=True)
    db_path = home / "state.db"
    _seed_state_db(db_path)
    _inject_duplicate_messages_fts_schema_row(db_path)
    _assert_duplicate_fts_schema_breaks_raw_sqlite(db_path)

    repo = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["HERMES_HOME"] = str(home)
    env["PYTHONPATH"] = str(repo)

    check = subprocess.run(
        [sys.executable, "-m", "hermes_cli.main", "sessions", "repair", "--check-only"],
        cwd=repo,
        env=env,
        text=True,
        capture_output=True,
        timeout=60,
    )
    assert check.returncode == 0, check.stderr
    assert "Repair needed; no changes made" in check.stdout
    _assert_duplicate_fts_schema_breaks_raw_sqlite(db_path)

    repair = subprocess.run(
        [sys.executable, "-m", "hermes_cli.main", "sessions", "repair"],
        cwd=repo,
        env=env,
        text=True,
        capture_output=True,
        timeout=60,
    )
    assert repair.returncode == 0, repair.stderr
    assert "Rebuilt FTS schema" in repair.stdout
    assert "2 messages indexed" in repair.stdout

    db = SessionDB(db_path=db_path)
    try:
        assert db.session_count() == 1
        assert db.message_count() == 2
    finally:
        db.close()
