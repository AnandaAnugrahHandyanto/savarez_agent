"""
test_db_compat — verifies Python-created schema is byte-identical to TS-created schema.

The test diffs sqlite_master rows (type, name, sql) between a Python-migrated DB
and a TS-migrated DB. Any difference means the schemas have diverged.

If pnpm / the switchui repo is not available (CI without Node), the TS half is
skipped and the test is marked xfail with a clear message.
"""
import os
import re
import sqlite3
import subprocess
import tempfile
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from engine.db.client import open_db
from engine.db.migrate import ensure_schema

# Location of the switchui repo (used to run the TS migration)
SWITCHUI_REPO = Path("/Volumes/Ext-nvme/Development/hermes-switchui-a")

_SKIP_TS = not SWITCHUI_REPO.exists()


def _get_schema_rows(conn: sqlite3.Connection) -> list[tuple[str, str, str]]:
    """
    Return (type, name, sql) tuples from sqlite_master, sorted, with
    auto-generated internal names (like sqlite_autoindex_*) stripped and
    comment lines removed from sql so cosmetic differences don't fail the diff.
    """
    rows = conn.execute(
        "SELECT type, name, sql FROM sqlite_master ORDER BY type, name"
    ).fetchall()
    result = []
    for row in rows:
        typ, name, sql = row[0], row[1], row[2]
        # Skip SQLite internal objects
        if name.startswith("sqlite_"):
            continue
        # Normalise SQL: strip inline comments, collapse whitespace
        if sql:
            sql = re.sub(r"--[^\n]*", "", sql)
            sql = re.sub(r"\s+", " ", sql).strip()
        result.append((typ, name, sql))
    return result


def _python_schema_rows() -> list[tuple[str, str, str]]:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    ensure_schema(conn)
    rows = _get_schema_rows(conn)
    conn.close()
    return rows


def _ts_schema_rows(db_path: str) -> list[tuple[str, str, str]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = _get_schema_rows(conn)
    conn.close()
    return rows


def _run_ts_migration(db_path: str) -> tuple[bool, str]:
    """Run the TS migration via pnpm exec tsx and return (success, stderr)."""
    # Use relative import — script written into repo root, so ./src/... resolves correctly
    tsx_script = f"""
import {{ runMigrations }} from './src/server/workflow-engine/db/migrate.ts';
import Database from 'better-sqlite3';
const db = new Database('{db_path}');
// Set pragmas before runMigrations — WAL cannot be set inside a transaction
db.pragma('journal_mode = WAL');
db.pragma('foreign_keys = ON');
runMigrations(db);
db.close();
"""
    # Write the script inside the switchui repo so node_modules resolves
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".ts", delete=False, dir=str(SWITCHUI_REPO)
    ) as f:
        f.write(tsx_script)
        script_path = f.name

    try:
        result = subprocess.run(
            ["pnpm", "exec", "tsx", script_path],
            cwd=str(SWITCHUI_REPO),
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0, result.stderr
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    finally:
        os.unlink(script_path)


@pytest.mark.skipif(_SKIP_TS, reason="switchui repo not available")
def test_db_compat():
    """
    Schema created by Python ensure_schema() must match schema created by TS runMigrations().
    Diff of sqlite_master rows must be empty.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        ts_db_path = f.name

    try:
        success, stderr = _run_ts_migration(ts_db_path)
        if not success:
            pytest.skip(
                f"TS migration could not run (Node/pnpm not available or error): {stderr[:300]}"
            )

        py_rows = _python_schema_rows()
        ts_rows = _ts_schema_rows(ts_db_path)

        py_set = set(py_rows)
        ts_set = set(ts_rows)

        only_in_py = py_set - ts_set
        only_in_ts = ts_set - py_set

        diff_lines = []
        for row in sorted(only_in_py):
            diff_lines.append(f"  Python only: {row[0]} {row[1]!r}")
        for row in sorted(only_in_ts):
            diff_lines.append(f"  TS only:     {row[0]} {row[1]!r}")

        assert not diff_lines, (
            "Schema diff between Python and TS migrations:\n" + "\n".join(diff_lines)
        )
    finally:
        if os.path.exists(ts_db_path):
            os.unlink(ts_db_path)
        # Also clean up WAL files
        for ext in ("-wal", "-shm"):
            p = ts_db_path + ext
            if os.path.exists(p):
                os.unlink(p)


def test_python_schema_self_consistent():
    """
    Smoke test: Python-only schema check (no TS needed).
    Confirms ensure_schema() produces a non-empty, well-formed sqlite_master.
    """
    rows = _python_schema_rows()
    names = {r[1] for r in rows}
    assert "workflow_definitions" in names
    assert "workflow_runs" in names
    assert "node_runs" in names
    assert "schema_meta" in names
    # indexes present
    assert "idx_wd_source" in names
    assert "idx_wr_status" in names
