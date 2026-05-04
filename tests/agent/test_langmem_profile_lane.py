"""Tests for the typed LangMem profile lane."""

import json


def test_langmem_profile_returns_structured_profile(tmp_path):
    from plugins.memory.langmem import LangMemMemoryProvider
    from plugins.memory.langmem.store import LangMemStore

    provider = LangMemMemoryProvider()
    provider._store = LangMemStore(tmp_path / "langmem.sqlite3")
    provider._user_id = "nick"
    provider._session_id = "sess-test"
    provider._store.upsert_profile(
        "nick",
        {"preferred_name": "Nick", "timezone": "America/Detroit"},
        session_id="sess-test",
    )

    result = json.loads(provider.handle_tool_call("langmem_profile", {}))
    assert result["kind"] == "profile"
    assert result["result"]["preferred_name"] == "Nick"
    assert result["result"]["timezone"] == "America/Detroit"


def test_langmem_profile_falls_back_when_profile_missing(tmp_path):
    from plugins.memory.langmem import LangMemMemoryProvider
    from plugins.memory.langmem.store import LangMemStore

    provider = LangMemMemoryProvider()
    provider._store = LangMemStore(tmp_path / "langmem.sqlite3")
    provider._user_id = "nick"
    provider._session_id = "sess-test"
    provider._store.upsert_many(
        "nick",
        [{"id": "m1", "content": "Nick prefers concise responses"}],
        session_id="sess-test",
    )

    result = json.loads(provider.handle_tool_call("langmem_profile", {}))
    assert result.get("kind") != "profile"
    assert "Nick prefers concise responses" in result["result"]
