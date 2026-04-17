import sqlite3
import warnings

from education.db import EducationDB, SCHEMA_VERSION
from education.paths import question_bank_db_path


def test_education_db_initializes_under_hermes_home(tmp_path, monkeypatch):
    fake_home = tmp_path / "custom_hermes_home"
    fake_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(fake_home))

    db = EducationDB()
    try:
        assert db.db_path == question_bank_db_path()
        assert db.db_path.exists()
    finally:
        db.close()


def test_education_db_enables_wal_and_foreign_keys(tmp_path, monkeypatch):
    fake_home = tmp_path / "custom_hermes_home"
    fake_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(fake_home))

    db = EducationDB()
    try:
        journal_mode = db.conn.execute("PRAGMA journal_mode").fetchone()[0]
        foreign_keys = db.conn.execute("PRAGMA foreign_keys").fetchone()[0]

        assert str(journal_mode).lower() == "wal"
        assert foreign_keys == 1
    finally:
        db.close()


def test_education_db_creates_expected_tables_and_schema_version(tmp_path, monkeypatch):
    fake_home = tmp_path / "custom_hermes_home"
    fake_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(fake_home))

    db = EducationDB()
    try:
        with sqlite3.connect(db.db_path) as conn:
            table_names = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            version = conn.execute("SELECT version FROM schema_version").fetchone()[0]

        assert "schema_version" in table_names
        assert "documents" in table_names
        assert "ingest_jobs" in table_names
        assert "artifacts" in table_names
        assert "source_blocks" in table_names
        assert "questions" in table_names
        assert "question_citations" in table_names
        assert version == SCHEMA_VERSION
    finally:
        db.close()


def test_create_document_avoids_named_placeholder_binding_warnings(tmp_path, monkeypatch):
    fake_home = tmp_path / "custom_hermes_home"
    fake_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(fake_home))

    db = EducationDB()
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", DeprecationWarning)
            db.create_document(
                id="doc_test_0001",
                sha256="abc123",
                source_uri="/tmp/sample.pdf",
                source_type="local_file",
                original_filename="sample.pdf",
                raw_artifact_path="/tmp/raw/sample.pdf",
                status="pending",
            )

        sqlite_warnings = [
            warning
            for warning in caught
            if "named parameter" in str(warning.message)
        ]
        assert sqlite_warnings == []

        row = db.get_document("doc_test_0001")
        assert row is not None
        assert row["id"] == "doc_test_0001"
        assert row["sha256"] == "abc123"
        assert row["original_filename"] == "sample.pdf"
    finally:
        db.close()
