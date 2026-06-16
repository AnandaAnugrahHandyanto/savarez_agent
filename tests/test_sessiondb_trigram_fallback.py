"""Test that SessionDB gracefully handles missing trigram tokenizer.

Regression test for https://github.com/NousResearch/hermes-agent/issues/47002
"""

import sqlite3
from unittest.mock import patch

import pytest

from hermes_state import SessionDB


class _NoTrigramCursor(sqlite3.Cursor):
    """A cursor that rejects trigram DDL, simulating SQLite without the tokenizer."""

    def executescript(self, sql_script):
        if "tokenize='trigram'" in sql_script:
            raise sqlite3.OperationalError("no such tokenizer: trigram")
        return super().executescript(sql_script)


def test_is_fts5_unavailable_error_matches_trigram():
    """_is_fts5_unavailable_error should match 'no such tokenizer' errors."""
    exc = sqlite3.OperationalError("no such tokenizer: trigram")
    assert SessionDB._is_fts5_unavailable_error(exc) is True


def test_is_fts5_unavailable_error_matches_no_module():
    """_is_fts5_unavailable_error should still match 'no such module: fts5'."""
    exc = sqlite3.OperationalError("no such module: fts5")
    assert SessionDB._is_fts5_unavailable_error(exc) is True


def test_is_fts5_unavailable_error_rejects_other():
    """_is_fts5_unavailable_error should not match unrelated errors."""
    exc = sqlite3.OperationalError("table already exists")
    assert SessionDB._is_fts5_unavailable_error(exc) is False


def test_is_trigram_only_error():
    """_is_trigram_only_error should distinguish tokenizer-specific errors."""
    trigram_exc = sqlite3.OperationalError("no such tokenizer: trigram")
    module_exc = sqlite3.OperationalError("no such module: fts5")

    assert SessionDB._is_trigram_only_error(trigram_exc) is True
    assert SessionDB._is_trigram_only_error(module_exc) is False


def test_sessiondb_init_survives_no_trigram(tmp_path):
    """SessionDB.__init__ should not crash when trigram tokenizer is absent.

    The base FTS5 table should still work; only trigram search falls back to LIKE.
    """
    db_path = tmp_path / "test_sessions.db"

    # Patch sqlite3.Cursor to reject trigram DDL
    original_cursor = sqlite3.Connection.cursor

    def _patched_cursor(self, *args, **kwargs):
        return _NoTrigramCursor(self)

    with patch.object(sqlite3.Connection, "cursor", _patched_cursor):
        # This should NOT raise — the trigram failure is caught gracefully
        try:
            db = SessionDB(str(db_path))
            # Base FTS should still be enabled
            assert db._fts_enabled is True
        except sqlite3.OperationalError as exc:
            if "no such tokenizer" in str(exc):
                pytest.fail(
                    f"SessionDB.__init__ crashed on missing trigram tokenizer: {exc}"
                )
            raise
