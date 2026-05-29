from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "validate_memory_schema.py"
MODULE_SPEC = spec_from_file_location("validate_memory_schema_test_module", MODULE_PATH)
assert MODULE_SPEC and MODULE_SPEC.loader
validate_memory_schema = module_from_spec(MODULE_SPEC)

import sys

sys.modules[MODULE_SPEC.name] = validate_memory_schema
MODULE_SPEC.loader.exec_module(validate_memory_schema)


def test_materialize_schema_creates_world_readable_copy(tmp_path):
    schema = tmp_path / "schema.sql"
    schema.write_text("select 1;\n")

    copied = validate_memory_schema.materialize_schema(schema)
    try:
        assert copied.exists()
        assert copied.read_text() == "select 1;\n"
        assert oct(copied.stat().st_mode & 0o777) == "0o644"
    finally:
        copied.unlink(missing_ok=True)


def test_validate_loads_schema_and_cleans_up_temp_copy(tmp_path, monkeypatch, capsys):
    schema = tmp_path / "schema.sql"
    schema.write_text("create table demo(id int);\n")

    calls: list[tuple[str, object]] = []

    def fake_require_commands(*commands: str) -> None:
        calls.append(("require", commands))

    def fake_pick_runner() -> list[str]:
        return ["sudo", "-u", "postgres"]

    def fake_create_database(runner: list[str], db_name: str) -> None:
        calls.append(("create", (runner, db_name)))

    def fake_load_schema(runner: list[str], db_name: str, schema_path: Path) -> None:
        calls.append(("load", (runner, db_name, schema_path)))
        assert schema_path.exists()

    def fake_query_scalar(runner: list[str], db_name: str, sql: str) -> str:
        calls.append(("query", (runner, db_name, sql)))
        if "pg_tables" in sql:
            return "memory_decisions,memory_entities,memory_episodes,memory_event_log,memory_facts,memory_sources,memory_summaries"
        if "pg_trigger" in sql:
            return "1"
        raise AssertionError(sql)

    def fake_drop_database(runner: list[str], db_name: str) -> None:
        calls.append(("drop", (runner, db_name)))

    monkeypatch.setattr(validate_memory_schema, "require_commands", fake_require_commands)
    monkeypatch.setattr(validate_memory_schema, "pick_runner", fake_pick_runner)
    monkeypatch.setattr(validate_memory_schema, "create_database", fake_create_database)
    monkeypatch.setattr(validate_memory_schema, "load_schema", fake_load_schema)
    monkeypatch.setattr(validate_memory_schema, "query_scalar", fake_query_scalar)
    monkeypatch.setattr(validate_memory_schema, "drop_database", fake_drop_database)

    validate_memory_schema.validate(schema)

    out = capsys.readouterr().out
    assert "schema valid:" in out
    assert any(name == "create" for name, _ in calls)
    assert any(name == "load" for name, _ in calls)
    assert any(name == "query" for name, _ in calls)
    assert any(name == "drop" for name, _ in calls)

    loaded_schema = next(payload[2] for name, payload in calls if name == "load")
    assert loaded_schema.exists() is False
