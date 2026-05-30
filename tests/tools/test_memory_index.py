from pathlib import Path

from tools.memory_tool import ENTRY_DELIMITER
from tools.memory_index import (
    MemoryIndexConfig,
    connect,
    dream_index,
    index_path,
    index_status,
    rebuild_index,
    search_index,
)


def _write_profile(home: Path, profile: str, target: str, entries: list[str]) -> Path:
    profile_home = home.parent / profile
    mem_dir = profile_home / "memories"
    mem_dir.mkdir(parents=True, exist_ok=True)
    filename = "USER.md" if target == "user" else "MEMORY.md"
    (mem_dir / filename).write_text(ENTRY_DELIMITER.join(entries), encoding="utf-8")
    return profile_home


def test_rebuild_and_search_profile_local_memory(tmp_path):
    hermes_home = tmp_path / "profiles" / "anulu"
    _write_profile(hermes_home, "anulu", "memory", [
        "Project Alpha uses FastAPI and Postgres",
        "User prefers concise terminal summaries",
    ])
    cfg = MemoryIndexConfig(enabled=True)

    result = rebuild_index(hermes_home=hermes_home, cfg=cfg)

    assert result["scanned"] == 2
    assert result["indexed"] == 2
    hits = search_index("FastAPI database", hermes_home=hermes_home, cfg=cfg)
    assert hits
    assert hits[0]["profile"] == "anulu"
    assert "FastAPI" in hits[0]["content"]


def test_rebuild_skips_sensitive_entries(tmp_path):
    hermes_home = tmp_path / "profiles" / "anulu"
    _write_profile(hermes_home, "anulu", "memory", [
        "Normal stable project convention",
        "api_key sk-1234567890abcdef1234567890abcdef should never be indexed",
    ])
    cfg = MemoryIndexConfig(enabled=True)

    result = rebuild_index(hermes_home=hermes_home, cfg=cfg)

    assert result["scanned"] == 2
    assert result["indexed"] == 1
    assert result["skipped_sensitive"] == 1
    hits = search_index("abcdef", hermes_home=hermes_home, cfg=cfg, include_cold=True)
    assert hits == []


def test_cross_profile_rebuild_is_denied_by_default(tmp_path):
    hermes_home = tmp_path / "profiles" / "anulu"
    _write_profile(hermes_home, "anulu", "memory", ["Anulu local fact"])
    _write_profile(hermes_home, "researcher", "memory", ["Researcher private fact"])
    cfg = MemoryIndexConfig(enabled=True, cross_profile_enabled=False)

    result = rebuild_index(hermes_home=hermes_home, profiles=("anulu", "researcher"), cfg=cfg)
    status = index_status(hermes_home=hermes_home, cfg=cfg)

    assert result["indexed"] == 1
    assert result["profiles"] == ["anulu"]
    assert status["counts"] == {"anulu:warm": 1}


def test_cross_profile_rebuild_requires_authorization(tmp_path):
    hermes_home = tmp_path / "profiles" / "anulu"
    _write_profile(hermes_home, "anulu", "memory", ["Anulu local fact"])
    _write_profile(hermes_home, "researcher", "memory", ["Researcher searchable fact"])
    cfg = MemoryIndexConfig(
        enabled=True,
        cross_profile_enabled=True,
        authorized_profiles=("researcher",),
    )

    result = rebuild_index(hermes_home=hermes_home, profiles=("researcher",), cfg=cfg)
    status = index_status(hermes_home=hermes_home, cfg=cfg)

    assert result["indexed"] == 1
    assert status["counts"] == {"researcher:warm": 1}


def test_search_records_usage_and_hot_tier_wins_order(tmp_path):
    hermes_home = tmp_path / "profiles" / "anulu"
    _write_profile(hermes_home, "anulu", "memory", [
        "FastAPI hot project uses Postgres",
        "FastAPI warm project uses SQLite",
    ])
    cfg = MemoryIndexConfig(enabled=True)
    rebuild_index(hermes_home=hermes_home, cfg=cfg)
    path = index_path(hermes_home, cfg)
    with connect(path) as conn:
        conn.execute(
            "UPDATE memory_index_entries SET tier = 'hot' WHERE content LIKE '%Postgres%'"
        )
        conn.execute(
            "UPDATE memory_index_entries SET tier = 'warm' WHERE content LIKE '%SQLite%'"
        )
        conn.commit()

    hits = search_index("FastAPI project", hermes_home=hermes_home, cfg=cfg)

    assert hits[0]["tier"] == "hot"
    assert "Postgres" in hits[0]["content"]
    with connect(path) as conn:
        used = conn.execute(
            "SELECT use_count, last_used_at, relevance FROM memory_index_entries WHERE id = ?",
            (hits[0]["id"],),
        ).fetchone()
    assert used["use_count"] == 1
    assert used["last_used_at"] is not None
    assert used["relevance"] > 0


def test_rebuild_preserves_updated_at_for_unchanged_entries(tmp_path):
    hermes_home = tmp_path / "profiles" / "anulu"
    _write_profile(hermes_home, "anulu", "memory", ["Stable old memory"])
    cfg = MemoryIndexConfig(enabled=True)
    rebuild_index(hermes_home=hermes_home, cfg=cfg)
    path = index_path(hermes_home, cfg)
    old_ts = 1000.0
    with connect(path) as conn:
        conn.execute("UPDATE memory_index_entries SET updated_at = ?", (old_ts,))
        conn.commit()

    rebuild_index(hermes_home=hermes_home, cfg=cfg)

    with connect(path) as conn:
        row = conn.execute("SELECT updated_at FROM memory_index_entries").fetchone()
    assert row["updated_at"] == old_ts


def test_rebuild_purges_deleted_and_edited_entries(tmp_path):
    hermes_home = tmp_path / "profiles" / "anulu"
    mem_dir = _write_profile(hermes_home, "anulu", "memory", ["Old secret-free fact", "Keep FastAPI fact"]) / "memories"
    cfg = MemoryIndexConfig(enabled=True)
    rebuild_index(hermes_home=hermes_home, cfg=cfg)

    (mem_dir / "MEMORY.md").write_text("Keep FastAPI fact" + ENTRY_DELIMITER + "New replacement fact", encoding="utf-8")
    rebuild_index(hermes_home=hermes_home, cfg=cfg)

    hits = search_index("Old secret-free fact", hermes_home=hermes_home, cfg=cfg, include_cold=True)
    assert all("Old secret-free fact" not in hit["content"] for hit in hits)
    with connect(index_path(hermes_home, cfg)) as conn:
        rows = conn.execute("SELECT content FROM memory_index_entries ORDER BY content").fetchall()
    assert [row["content"] for row in rows] == ["Keep FastAPI fact", "New replacement fact"]


def test_rebuild_purges_entry_that_becomes_sensitive(tmp_path):
    hermes_home = tmp_path / "profiles" / "anulu"
    mem_dir = _write_profile(hermes_home, "anulu", "memory", ["Normal project token note"]) / "memories"
    cfg = MemoryIndexConfig(enabled=True)
    rebuild_index(hermes_home=hermes_home, cfg=cfg)

    (mem_dir / "MEMORY.md").write_text("api_key sk-1234567890abcdef now sensitive", encoding="utf-8")
    result = rebuild_index(hermes_home=hermes_home, cfg=cfg)

    assert result["skipped_sensitive"] == 1
    with connect(index_path(hermes_home, cfg)) as conn:
        rows = conn.execute("SELECT content FROM memory_index_entries").fetchall()
    assert rows == []


def test_search_denies_unauthorized_profile_rows_already_in_db(tmp_path):
    hermes_home = tmp_path / "profiles" / "anulu"
    _write_profile(hermes_home, "researcher", "memory", ["Researcher private vector fact"])
    allowed_cfg = MemoryIndexConfig(enabled=True, cross_profile_enabled=True, authorized_profiles=("researcher",))
    rebuild_index(hermes_home=hermes_home, profiles=("researcher",), cfg=allowed_cfg)

    locked_cfg = MemoryIndexConfig(enabled=True, cross_profile_enabled=False)

    assert search_index("Researcher private", hermes_home=hermes_home, profile="researcher", cfg=locked_cfg) == []
    assert index_status(hermes_home=hermes_home, cfg=locked_cfg)["counts"] == {}


def test_dream_scopes_to_active_or_authorized_profiles(tmp_path):
    hermes_home = tmp_path / "profiles" / "anulu"
    _write_profile(hermes_home, "researcher", "memory", ["Researcher stale duplicate"])
    allowed_cfg = MemoryIndexConfig(enabled=True, cross_profile_enabled=True, authorized_profiles=("researcher",))
    rebuild_index(hermes_home=hermes_home, profiles=("researcher",), cfg=allowed_cfg)

    locked_report = dream_index(hermes_home=hermes_home, cfg=MemoryIndexConfig(enabled=True), apply=False)
    assert locked_report["tier_changes"] == []
    assert locked_report["duplicates"] == []
    assert locked_report["stale_candidates"] == []

    allowed_report = dream_index(hermes_home=hermes_home, cfg=allowed_cfg, apply=False)
    assert any("Researcher" in item["content_preview"] for item in allowed_report["tier_changes"])


def test_cross_profile_default_profile_resolves_to_root_home(tmp_path):
    hermes_home = tmp_path / "profiles" / "anulu"
    default_mem_dir = tmp_path / "memories"
    default_mem_dir.mkdir(parents=True)
    (default_mem_dir / "MEMORY.md").write_text("Default root profile memory", encoding="utf-8")
    cfg = MemoryIndexConfig(enabled=True, cross_profile_enabled=True, authorized_profiles=("default",))

    result = rebuild_index(hermes_home=hermes_home, profiles=("default",), cfg=cfg)

    assert result["indexed"] == 1
    hits = search_index("root profile", hermes_home=hermes_home, profile="default", cfg=cfg)
    assert hits and hits[0]["profile"] == "default"


def test_dream_reports_and_applies_tier_changes_without_deleting(tmp_path):
    hermes_home = tmp_path / "profiles" / "anulu"
    _write_profile(hermes_home, "anulu", "memory", ["Recently rebuilt memory should become hot"])
    cfg = MemoryIndexConfig(enabled=True)
    rebuild_index(hermes_home=hermes_home, cfg=cfg)

    report = dream_index(hermes_home=hermes_home, cfg=cfg, apply=False)
    assert report["apply"] is False
    assert report["tier_changes"]
    assert report["tier_changes"][0]["to"] == "hot"

    applied = dream_index(hermes_home=hermes_home, cfg=cfg, apply=True)
    assert applied["apply"] is True
    status = index_status(hermes_home=hermes_home, cfg=cfg)
    assert status["counts"] == {"anulu:hot": 1}
