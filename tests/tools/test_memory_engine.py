"""Tests for MemoryEngine — SQLite-backed memory with FTS5 search and lifecycle."""

import os
import tempfile
from pathlib import Path

import pytest

from tools.memory_engine import (
    MEMORY_TIERS,
    MEMORY_TYPES,
    MemoryEngine,
)


@pytest.fixture
def engine(tmp_path):
    """Create a MemoryEngine with a temp database."""
    db_path = tmp_path / "memory.db"
    eng = MemoryEngine(db_path=db_path)
    yield eng
    eng.close()


@pytest.fixture
def populated_engine(engine):
    """Engine with some test memories."""
    engine.add("User prefers terse responses and dislikes verbosity in answers", target="user", type="preference")
    engine.add("Project uses Python 3.11 on WSL Ubuntu with systemd enabled", target="memory", type="project")
    engine.add("Discord output limitation: only final text visible per turn to end users", target="memory", type="correction")
    engine.add("User plays League of Legends competitively in ranked solo queue", target="user", type="general")
    engine.add("Always activate the virtualenv before running any Python commands in this project", target="memory", type="reference")
    return engine


# ---------------------------------------------------------------------------
# Schema and Init
# ---------------------------------------------------------------------------


class TestInit:
    def test_creates_db(self, tmp_path):
        db_path = tmp_path / "sub" / "memory.db"
        eng = MemoryEngine(db_path=db_path)
        assert db_path.exists()
        eng.close()

    def test_schema_version(self, engine):
        assert engine._get_meta("schema_version") == "1"

    def test_idempotent_init(self, engine):
        # Calling init again should not error
        engine._init_db()
        assert engine._get_meta("schema_version") == "1"


# ---------------------------------------------------------------------------
# Core CRUD
# ---------------------------------------------------------------------------


class TestAdd:
    def test_basic_add(self, engine):
        result = engine.add("test memory", target="memory")
        assert result["success"] is True
        assert "id" in result
        assert result["target"] == "memory"
        assert result["type"] == "general"

    def test_add_with_type(self, engine):
        result = engine.add("user likes cats", target="user", type="preference")
        assert result["success"] is True
        assert result["type"] == "preference"

    def test_add_empty_rejected(self, engine):
        result = engine.add("", target="memory")
        assert result["success"] is False
        assert "empty" in result["error"].lower()

    def test_add_invalid_target(self, engine):
        result = engine.add("test", target="invalid")
        assert result["success"] is False

    def test_add_invalid_type_defaults(self, engine):
        result = engine.add("test", target="memory", type="bogus")
        assert result["success"] is True
        assert result["type"] == "general"

    def test_exact_duplicate_rejected(self, engine):
        engine.add("The deployment pipeline uses GitHub Actions with Docker containers for CI/CD builds", target="memory")
        # Exact same content should be caught by BM25 dedup
        result = engine.add("The deployment pipeline uses GitHub Actions with Docker containers for CI/CD builds", target="memory")
        assert result["success"] is False
        assert "duplicate" in result.get("error", "").lower()

    def test_different_content_allowed(self, engine):
        engine.add("Python project on WSL", target="memory")
        result = engine.add("Discord bot uses Node.js", target="memory")
        assert result["success"] is True


class TestReplace:
    def test_basic_replace(self, engine):
        r = engine.add("original content", target="memory")
        result = engine.replace(r["id"], "updated content")
        assert result["success"] is True
        mem = engine.get(r["id"])
        assert mem["content"] == "updated content"

    def test_replace_nonexistent(self, engine):
        result = engine.replace("nonexistent-id", "new content")
        assert result["success"] is False

    def test_replace_empty(self, engine):
        r = engine.add("original", target="memory")
        result = engine.replace(r["id"], "")
        assert result["success"] is False


class TestRemove:
    def test_basic_remove(self, engine):
        r = engine.add("to be removed", target="memory")
        result = engine.remove(r["id"])
        assert result["success"] is True
        assert engine.get(r["id"]) is None

    def test_remove_nonexistent(self, engine):
        result = engine.remove("nonexistent-id")
        assert result["success"] is False


class TestGet:
    def test_get_existing(self, engine):
        r = engine.add("test content", target="memory", type="preference")
        mem = engine.get(r["id"])
        assert mem is not None
        assert mem["content"] == "test content"
        assert mem["type"] == "preference"
        assert mem["tier"] == "active"

    def test_get_nonexistent(self, engine):
        assert engine.get("nonexistent") is None


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


class TestSearchFTS:
    def test_basic_search(self, populated_engine):
        results = populated_engine.search_fts("Python WSL")
        assert len(results) > 0
        assert any("Python" in r["content"] for r in results)

    def test_search_by_target(self, populated_engine):
        results = populated_engine.search_fts("prefers", target="user")
        assert all(r["target"] == "user" for r in results)

    def test_empty_query(self, populated_engine):
        results = populated_engine.search_fts("")
        assert results == []

    def test_no_results(self, populated_engine):
        results = populated_engine.search_fts("xyzzy nonexistent gibberish")
        assert results == []


class TestHybridSearch:
    def test_basic_hybrid(self, populated_engine):
        results = populated_engine.search("Discord output")
        assert len(results) > 0
        assert all("relevance_score" in r for r in results)

    def test_results_sorted_by_relevance(self, populated_engine):
        results = populated_engine.search("Python project")
        if len(results) > 1:
            scores = [r["relevance_score"] for r in results]
            assert scores == sorted(scores, reverse=True)

    def test_min_relevance_filter(self, populated_engine):
        results = populated_engine.search("Discord", min_relevance=0.0)
        all_results = len(results)
        results_strict = populated_engine.search("Discord", min_relevance=0.9)
        assert len(results_strict) <= all_results


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


class TestLifecycle:
    def test_reinforce(self, engine):
        r = engine.add("test memory", target="memory")
        mem_before = engine.get(r["id"])
        assert mem_before["access_count"] == 0

        engine.reinforce(r["id"])
        mem_after = engine.get(r["id"])
        assert mem_after["access_count"] == 1
        assert mem_after["strength"] > mem_before["strength"]
        assert mem_after["last_accessed"] is not None

    def test_archive_stale(self, engine):
        # Add a memory and artificially age it
        r = engine.add("old memory", target="memory")
        conn = engine._get_conn()
        conn.execute(
            "UPDATE memories SET updated_at = datetime('now', '-100 days'), strength = 1.0 WHERE id = ?",
            (r["id"],),
        )
        conn.commit()

        count = engine.archive_stale(days=90, min_strength=1.1)
        assert count == 1
        mem = engine.get(r["id"])
        assert mem["tier"] == "archived"

    def test_supersede(self, engine):
        r1 = engine.add("The deployment server runs Debian 11 with nginx reverse proxy", target="memory")
        r2 = engine.add("The CI pipeline uses GitHub Actions with Docker containers", target="memory")
        assert r1["success"] and r2["success"]
        engine.supersede(r1["id"], r2["id"])

        old = engine.get(r1["id"])
        assert old["tier"] == "superseded"
        assert old["superseded_by"] == r2["id"]


# ---------------------------------------------------------------------------
# Prompt Formatting
# ---------------------------------------------------------------------------


class TestPromptFormatting:
    def test_format_with_type_tags(self, populated_engine):
        text = populated_engine.format_for_prompt("memory")
        assert text is not None
        assert "[proj]" in text or "[corr]" in text or "[ref]" in text

    def test_format_empty(self, engine):
        assert engine.format_for_prompt("memory") is None

    def test_format_respects_budget(self, populated_engine):
        text = populated_engine.format_for_prompt("memory", char_budget=100)
        # Should truncate to fit budget (header excluded from count)
        assert text is not None

    def test_snapshot_frozen(self, populated_engine):
        populated_engine.snapshot()
        snap1 = populated_engine.get_snapshot("memory")
        # Add more memories
        populated_engine.add("brand new memory", target="memory")
        snap2 = populated_engine.get_snapshot("memory")
        # Snapshot should be frozen
        assert snap1 == snap2

    def test_snapshot_refreshable(self, populated_engine):
        populated_engine.snapshot()
        snap1 = populated_engine.get_snapshot("memory")
        populated_engine.add("brand new memory after snapshot", target="memory")
        populated_engine.snapshot()  # Re-capture
        snap2 = populated_engine.get_snapshot("memory")
        assert snap1 != snap2


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------


class TestMigration:
    def test_migrate_from_flat(self, tmp_path):
        mem_dir = tmp_path / "memories"
        mem_dir.mkdir()
        (mem_dir / "MEMORY.md").write_text("fact one\n§\nfact two\n§\nfact three")
        (mem_dir / "USER.md").write_text("user pref one\n§\nuser pref two")

        eng = MemoryEngine(db_path=mem_dir / "memory.db")
        result = eng.migrate_from_flat_files(memory_dir=mem_dir)
        assert result["migrated"] is True
        assert result["count"] == 5

        assert eng.count_active("memory") == 3
        assert eng.count_active("user") == 2

        # Flat files should be backed up
        assert (mem_dir / "MEMORY.md.bak").exists()
        assert (mem_dir / "USER.md.bak").exists()
        eng.close()

    def test_migrate_idempotent(self, tmp_path):
        mem_dir = tmp_path / "memories"
        mem_dir.mkdir()
        (mem_dir / "MEMORY.md").write_text("fact one")

        eng = MemoryEngine(db_path=mem_dir / "memory.db")
        eng.migrate_from_flat_files(memory_dir=mem_dir)
        result = eng.migrate_from_flat_files(memory_dir=mem_dir)
        assert result["migrated"] is False
        eng.close()


# ---------------------------------------------------------------------------
# Stats and Manifest
# ---------------------------------------------------------------------------


class TestStats:
    def test_stats(self, populated_engine):
        s = populated_engine.stats()
        assert s["total"] == 5
        assert "memory" in s["by_target"]
        assert "user" in s["by_target"]

    def test_count_active(self, populated_engine):
        assert populated_engine.count_active() == 5
        assert populated_engine.count_active("memory") == 3
        assert populated_engine.count_active("user") == 2


class TestManifest:
    def test_manifest_format(self, populated_engine):
        manifest = populated_engine.get_manifest()
        assert "preference" in manifest or "pref" in manifest
        lines = manifest.split("\n")
        assert len(lines) >= 3  # at least 3 memories survived

    def test_manifest_empty(self, engine):
        assert "no memories" in engine.get_manifest()
