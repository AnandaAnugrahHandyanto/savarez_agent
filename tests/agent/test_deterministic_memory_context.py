import sqlite3

import agent.deterministic_memory_context as deterministic_memory_context
from agent.deterministic_memory_context import build_deterministic_memory_context_block


def _init_db(path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE nodes (
            id TEXT PRIMARY KEY,
            scope TEXT NOT NULL,
            type TEXT NOT NULL,
            key TEXT NOT NULL,
            content TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            updated_at TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            UNIQUE (scope, type, key)
        );
        CREATE TABLE aliases (
            alias TEXT PRIMARY KEY,
            alias_norm TEXT NOT NULL,
            scope TEXT NOT NULL,
            type TEXT NOT NULL,
            key TEXT NOT NULL,
            node_id TEXT,
            canonical_address TEXT NOT NULL
        );
        CREATE TABLE triggers (
            trigger TEXT NOT NULL,
            trigger_norm TEXT NOT NULL,
            node_id TEXT NOT NULL,
            scope TEXT NOT NULL,
            type TEXT NOT NULL,
            key TEXT NOT NULL,
            PRIMARY KEY(trigger_norm, node_id)
        );
        CREATE TABLE facets (
            facet TEXT NOT NULL,
            facet_norm TEXT NOT NULL,
            node_id TEXT NOT NULL,
            PRIMARY KEY(facet_norm, node_id)
        );
        CREATE TABLE scope_defaults (
            scope TEXT NOT NULL,
            scope_norm TEXT NOT NULL,
            node_id TEXT NOT NULL,
            PRIMARY KEY(scope_norm, node_id)
        );
        """
    )
    return conn


def _insert_node(conn, node_id, key, content, *, status="active"):
    conn.execute(
        """
        INSERT INTO nodes(id, scope, type, key, content, status, updated_at, version)
        VALUES (?, 'user', 'preference', ?, ?, ?, '2026-05-02T00:00:00Z', 1)
        """,
        (node_id, key, content, status),
    )


def test_disabled_config_does_not_touch_db(monkeypatch):
    def fail_connect(*args, **kwargs):
        raise AssertionError("sqlite should not be touched when disabled")

    monkeypatch.setattr(sqlite3, "connect", fail_connect)

    block = build_deterministic_memory_context_block(
        "communication",
        {"enabled": False, "db_path": "/tmp/does-not-matter.db"},
    )

    assert block == ""


def test_enabled_config_injects_matching_trigger_node(tmp_path):
    db_path = tmp_path / "memory.db"
    conn = _init_db(db_path)
    _insert_node(
        conn,
        "mem.user.preference.tone",
        "communication.tone",
        "Prefer concise technical tone.",
    )
    conn.execute(
        """
        INSERT INTO triggers(trigger, trigger_norm, node_id, scope, type, key)
        VALUES ('communication tone', 'communication tone', 'mem.user.preference.tone',
                'user', 'preference', 'communication.tone')
        """
    )
    conn.commit()
    conn.close()

    block = build_deterministic_memory_context_block(
        "  COMMUNICATION   Tone ",
        {"enabled": True, "db_path": str(db_path), "max_results": 5, "max_chars": 2000},
    )

    assert "<deterministic-memory-context>" in block
    assert "matched_by: trigger" in block
    assert "mem.user.preference.tone" in block
    assert "Prefer concise technical tone." in block


def test_db_path_can_fall_back_to_memory_registry_env(tmp_path, monkeypatch):
    db_path = tmp_path / "memory.db"
    conn = _init_db(db_path)
    _insert_node(conn, "mem.user.preference.env", "env.path", "Loaded from env path.")
    conn.commit()
    conn.close()
    monkeypatch.setenv("MEMORY_REGISTRY_DB_PATH", str(db_path))

    block = build_deterministic_memory_context_block(
        "mem.user.preference.env",
        {"enabled": True, "db_path": ""},
    )

    assert "Loaded from env path." in block


def test_inactive_exact_id_match_does_not_inject_context(tmp_path):
    db_path = tmp_path / "memory.db"
    conn = _init_db(db_path)
    _insert_node(
        conn,
        "mem.user.preference.old",
        "old.preference",
        "Deprecated exact id content.",
        status="deprecated",
    )
    conn.commit()
    conn.close()

    block = build_deterministic_memory_context_block(
        "mem.user.preference.old",
        {"enabled": True, "db_path": str(db_path), "max_results": 5, "max_chars": 2000},
    )

    assert block == ""


def test_inactive_exact_address_match_does_not_inject_context(tmp_path):
    db_path = tmp_path / "memory.db"
    conn = _init_db(db_path)
    _insert_node(
        conn,
        "mem.user.preference.old_address",
        "old.address",
        "Superseded exact address content.",
        status="superseded",
    )
    conn.commit()
    conn.close()

    block = build_deterministic_memory_context_block(
        "user:preference:old.address",
        {"enabled": True, "db_path": str(db_path), "max_results": 5, "max_chars": 2000},
    )

    assert block == ""


def test_lookup_failure_is_non_fatal(tmp_path):
    broken_db = tmp_path / "broken.db"
    broken_db.write_text("not sqlite", encoding="utf-8")

    block = build_deterministic_memory_context_block(
        "anything",
        {"enabled": True, "db_path": str(broken_db)},
    )

    assert block == ""


def test_context_block_is_bounded_by_max_results_and_chars(tmp_path):
    db_path = tmp_path / "memory.db"
    conn = _init_db(db_path)
    for idx in range(3):
        node_id = f"mem.user.preference.{idx}"
        key = f"communication.{idx}"
        _insert_node(conn, node_id, key, f"Preference {idx} " + ("x" * 40))
        conn.execute(
            """
            INSERT INTO triggers(trigger, trigger_norm, node_id, scope, type, key)
            VALUES ('shared', 'shared', ?, 'user', 'preference', ?)
            """,
            (node_id, key),
        )
    conn.commit()
    conn.close()

    block = build_deterministic_memory_context_block(
        "shared",
        {"enabled": True, "db_path": str(db_path), "max_results": 2, "max_chars": 1000},
    )

    assert "included_candidates: 2" in block
    assert "has_more_candidates: true" in block
    assert "mem.user.preference.0" in block
    assert "mem.user.preference.1" in block
    assert "mem.user.preference.2" not in block
    assert len(block) <= 1000


def test_candidate_lookup_only_materializes_limit_plus_one_rows(tmp_path, monkeypatch):
    db_path = tmp_path / "memory.db"
    conn = _init_db(db_path)
    for idx in range(10):
        node_id = f"mem.user.preference.{idx}"
        key = f"communication.{idx}"
        _insert_node(conn, node_id, key, f"Preference {idx}")
        conn.execute(
            """
            INSERT INTO triggers(trigger, trigger_norm, node_id, scope, type, key)
            VALUES ('shared', 'shared', ?, 'user', 'preference', ?)
            """,
            (node_id, key),
        )
    conn.commit()
    conn.close()

    seen_node_rows = 0
    original_node_from_row = deterministic_memory_context._node_from_row

    def counting_node_from_row(row):
        nonlocal seen_node_rows
        if row is not None:
            seen_node_rows += 1
        return original_node_from_row(row)

    monkeypatch.setattr(deterministic_memory_context, "_node_from_row", counting_node_from_row)

    block = build_deterministic_memory_context_block(
        "shared",
        {"enabled": True, "db_path": str(db_path), "max_results": 2, "max_chars": 2000},
    )

    assert seen_node_rows == 3
    assert "included_candidates: 2" in block
    assert "has_more_candidates: true" in block
    assert "mem.user.preference.0" in block
    assert "mem.user.preference.1" in block
    assert "mem.user.preference.2" not in block
