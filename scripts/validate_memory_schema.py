#!/usr/bin/env python3
"""Validate the canonical memory schema in a temporary Postgres database.

Usage:
  python scripts/validate_memory_schema.py
  python scripts/validate_memory_schema.py --schema docs/architecture/memory-schema.sql

The script creates a throwaway database, loads the schema, checks the core
relations/trigger, and drops the database again.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = ROOT / "docs" / "architecture" / "memory-schema.sql"


class ValidationError(RuntimeError):
    pass


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise ValidationError(
            f"Command failed ({proc.returncode}): {' '.join(cmd)}\n"
            f"stdout: {proc.stdout.strip()}\n"
            f"stderr: {proc.stderr.strip()}"
        )
    return proc


def pick_runner() -> list[str]:
    if shutil.which("sudo"):
        return ["sudo", "-u", "postgres"]
    return []


def require_commands(*commands: str) -> None:
    missing = [cmd for cmd in commands if shutil.which(cmd) is None]
    if missing:
        raise ValidationError(f"Missing required commands: {', '.join(missing)}")


def create_database(runner: list[str], db_name: str) -> None:
    run(runner + ["createdb", db_name])


def drop_database(runner: list[str], db_name: str) -> None:
    run(runner + ["dropdb", "--if-exists", db_name], check=False)


def load_schema(runner: list[str], db_name: str, schema_path: Path) -> None:
    run(runner + ["psql", "-v", "ON_ERROR_STOP=1", "-d", db_name, "-f", str(schema_path)])


def materialize_schema(schema_path: Path) -> Path:
    temp_file = tempfile.NamedTemporaryFile("w", suffix=".sql", prefix="hermes_schema_", delete=False)
    try:
        temp_file.write(schema_path.read_text())
        temp_file.flush()
    finally:
        temp_file.close()
    temp_path = Path(temp_file.name)
    temp_path.chmod(0o644)
    return temp_path


def query_scalar(runner: list[str], db_name: str, sql: str) -> str:
    proc = run(runner + ["psql", "-Atqc", sql, "-d", db_name])
    return proc.stdout.strip()


def validate(schema_path: Path) -> None:
    if not schema_path.exists():
        raise ValidationError(f"Schema not found: {schema_path}")

    require_commands("createdb", "dropdb", "psql")
    runner = pick_runner()
    if not runner and os.geteuid() != 0:
        raise ValidationError("Need either root access or sudo to create a temporary database")

    db_name = f"hermes_schema_check_{os.getpid()}_{int(time.time())}"
    temp_schema = materialize_schema(schema_path)
    try:
        create_database(runner, db_name)
        load_schema(runner, db_name, temp_schema)

        tables = query_scalar(
            runner,
            db_name,
            "SELECT string_agg(tablename, ',' ORDER BY tablename) FROM pg_tables WHERE schemaname = 'public'",
        )
        expected = {
            "memory_decisions",
            "memory_entities",
            "memory_episodes",
            "memory_event_log",
            "memory_facts",
            "memory_sources",
            "memory_summaries",
        }
        found = set(filter(None, tables.split(",")))
        missing_tables = sorted(expected - found)
        if missing_tables:
            raise ValidationError(f"Missing tables after schema load: {', '.join(missing_tables)}")

        trigger_exists = query_scalar(
            runner,
            db_name,
            "SELECT count(*)::text FROM pg_trigger WHERE tgname = 'trg_memory_event_log_no_update' AND NOT tgisinternal",
        )
        if trigger_exists != "1":
            raise ValidationError("Append-only trigger missing from memory_event_log")

        print(f"schema valid: {schema_path}")
    finally:
        drop_database(runner, db_name)
        try:
            temp_schema.unlink()
        except FileNotFoundError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA, help="Path to the SQL schema file")
    args = parser.parse_args()

    try:
        validate(args.schema)
    except ValidationError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
