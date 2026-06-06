import pytest

from hermex.core.embedding import embed_text
from hermex.core.store import CoreStore, SQLiteStoreConfig, build_sqlite_core_store
from hermex.core.store.base import (
    AbstractPatternStore,
    AbstractSessionStore,
    AbstractSkillRegistry,
    AbstractTelemetryStore,
    TelemetryEvent,
)


@pytest.mark.asyncio
async def test_sqlite_store_implements_core_store_contracts(tmp_path):
    store = build_sqlite_core_store(SQLiteStoreConfig(path=tmp_path / "hermex.sqlite3"))

    assert isinstance(store, CoreStore)
    assert isinstance(store.patterns, AbstractPatternStore)
    assert isinstance(store.telemetry, AbstractTelemetryStore)
    assert isinstance(store.sessions, AbstractSessionStore)
    assert isinstance(store.skills, AbstractSkillRegistry)

    session = await store.sessions.load_or_create("session-a")
    session.metadata["model"] = "anthropic/claude-3.5-sonnet"
    await store.sessions.save(session)

    reloaded = await store.sessions.load_or_create("session-a")
    assert reloaded.session_id == "session-a"
    assert reloaded.metadata["model"] == "anthropic/claude-3.5-sonnet"


@pytest.mark.asyncio
async def test_sqlite_telemetry_searches_similar_events_and_excludes_current_session(tmp_path):
    store = build_sqlite_core_store(SQLiteStoreConfig(path=tmp_path / "hermex.sqlite3"))
    embedding = embed_text("fix openrouter proxy streaming error")
    await store.telemetry.emit(
        TelemetryEvent(
            session_id="session-a",
            summary="OpenRouter proxy streaming failed because the upstream base URL was malformed.",
            embedding=embedding,
            tool_name="hermex_proxy",
            success=False,
            failure_reason="malformed upstream base URL",
        )
    )

    hits = await store.telemetry.search_similar(
        embed_text("openrouter upstream streaming failure"),
        top_k=5,
        exclude_session="session-b",
    )
    assert [hit.session_id for hit in hits] == ["session-a"]
    assert "OpenRouter proxy streaming failed" in hits[0].summary

    excluded = await store.telemetry.search_similar(
        embed_text("openrouter upstream streaming failure"),
        top_k=5,
        exclude_session="session-a",
    )
    assert excluded == []


@pytest.mark.asyncio
async def test_sqlite_failure_search_returns_known_failure_modes(tmp_path):
    store = build_sqlite_core_store(SQLiteStoreConfig(path=tmp_path / "hermex.sqlite3"))
    await store.telemetry.emit(
        TelemetryEvent(
            session_id="session-a",
            summary="Tool call failed when sqlite database was locked.",
            embedding=embed_text("sqlite database locked tool failure"),
            tool_name="shell",
            success=False,
            failure_reason="database locked",
        )
    )

    failures = await store.telemetry.search_failures(
        embed_text("shell sqlite locked"),
        top_k=3,
    )
    assert len(failures) == 1
    assert failures[0].tool_name == "shell"
    assert failures[0].failure_reason == "database locked"


@pytest.mark.asyncio
async def test_sqlite_pattern_store_counts_repeated_patterns(tmp_path):
    store = build_sqlite_core_store(SQLiteStoreConfig(path=tmp_path / "hermex.sqlite3"))

    first = await store.patterns.increment(("read_file", "run_tests"), "session-a")
    second = await store.patterns.increment(("read_file", "run_tests"), "session-b")

    assert first == 1
    assert second == 2
    patterns = await store.patterns.get_above_threshold(2)
    assert len(patterns) == 1
    assert patterns[0].pattern_key == ("read_file", "run_tests")
    assert set(patterns[0].session_ids) == {"session-a", "session-b"}
