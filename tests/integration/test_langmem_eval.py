import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


ARTIFACT_PATH = Path("tmp/langmem-eval/latest.json")


def _make_provider(tmp_path, user_id="nick", session_id="sess-eval"):
    from plugins.memory.langmem import LangMemMemoryProvider
    from plugins.memory.langmem.store import LangMemStore

    provider = LangMemMemoryProvider()
    provider._store = LangMemStore(tmp_path / "langmem.sqlite3")
    provider._store_path = tmp_path / "langmem.sqlite3"
    provider._user_id = user_id
    provider._session_id = session_id
    provider._model = "anthropic:claude-3-5-haiku-latest"
    provider._enable_deletes = True
    provider._max_existing = 50
    provider._debounce_seconds = 0.0
    return provider


def _score(ok: bool) -> float:
    return 1.0 if ok else 0.0


def _write_results(results: dict) -> None:
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")


def _explicit_preference_write_scenario(tmp_path) -> dict:
    provider = _make_provider(tmp_path, session_id="sess-explicit")
    response = json.loads(
        provider.handle_tool_call(
            "langmem_conclude",
            {"conclusion": "Nick prefers concise responses"},
        )
    )
    row = provider._store.get_memory("nick", response["id"])
    meta = json.loads(row["metadata_json"])
    search = json.loads(provider.handle_tool_call("langmem_search", {"query": "concise responses", "top_k": 5}))
    profile = json.loads(provider.handle_tool_call("langmem_profile", {}))

    extraction_ok = row["content"] == "Nick prefers concise responses"
    reconciliation_ok = meta["lane"] == "preferences" and meta["source_type"] == "conclude"
    retrieval_ok = any(item["id"] == response["id"] for item in search.get("results", []))
    injection_ok = "Nick prefers concise responses" in profile.get("result", "")

    return {
        "scenario": "explicit_preference_write",
        "extraction_score": _score(extraction_ok),
        "reconciliation_score": _score(reconciliation_ok),
        "retrieval_score": _score(retrieval_ok),
        "injection_usefulness_score": _score(injection_ok),
        "notes": {
            "stored_id": response["id"],
            "profile_kind": profile.get("kind", "fallback"),
        },
    }


def _preference_correction_scenario(tmp_path) -> dict:
    provider = _make_provider(tmp_path, session_id="sess-correct-1")
    old_response = json.loads(
        provider.handle_tool_call(
            "langmem_conclude",
            {"conclusion": "Nick prefers long essays"},
        )
    )
    provider._store.delete_memory("nick", old_response["id"])
    provider._session_id = "sess-correct-2"
    new_response = json.loads(
        provider.handle_tool_call(
            "langmem_conclude",
            {"conclusion": "Nick prefers concise responses"},
        )
    )

    old_live = provider._store.get_memory("nick", old_response["id"])
    all_rows = {row["id"]: row for row in provider._store.list_memories("nick", include_deleted=True)}
    new_row = provider._store.get_memory("nick", new_response["id"])
    search_new = json.loads(provider.handle_tool_call("langmem_search", {"query": "concise responses", "top_k": 5}))
    search_old = json.loads(provider.handle_tool_call("langmem_search", {"query": "long essays", "top_k": 5}))
    profile = json.loads(provider.handle_tool_call("langmem_profile", {}))
    profile_text = profile.get("result", "")

    extraction_ok = new_row is not None and new_row["content"] == "Nick prefers concise responses"
    reconciliation_ok = old_live is None and all_rows[old_response["id"]]["deleted_at"] is not None
    retrieval_ok = any(item["id"] == new_response["id"] for item in search_new.get("results", [])) and search_old.get("count", 0) == 0
    injection_ok = "Nick prefers concise responses" in profile_text and "Nick prefers long essays" not in profile_text

    return {
        "scenario": "preference_correction_supersession",
        "extraction_score": _score(extraction_ok),
        "reconciliation_score": _score(reconciliation_ok),
        "retrieval_score": _score(retrieval_ok),
        "injection_usefulness_score": _score(injection_ok),
        "notes": {
            "old_id": old_response["id"],
            "new_id": new_response["id"],
        },
    }


def _cross_session_recall_scenario(tmp_path) -> dict:
    provider_a = _make_provider(tmp_path, session_id="sess-a")
    response = json.loads(
        provider_a.handle_tool_call(
            "langmem_conclude",
            {"conclusion": "Nick wants browser-verified fixes"},
        )
    )

    provider_b = _make_provider(tmp_path, session_id="sess-b")
    provider_b._store = provider_a._store
    provider_b._store_path = provider_a._store_path
    search = json.loads(provider_b.handle_tool_call("langmem_search", {"query": "browser verified fixes", "top_k": 5}))
    profile = json.loads(provider_b.handle_tool_call("langmem_profile", {}))
    row = provider_b._store.get_memory("nick", response["id"])

    extraction_ok = row is not None
    reconciliation_ok = row is not None and row["deleted_at"] is None
    retrieval_ok = any(item["id"] == response["id"] for item in search.get("results", []))
    injection_ok = "Nick wants browser-verified fixes" in profile.get("result", "")

    return {
        "scenario": "cross_session_recall",
        "extraction_score": _score(extraction_ok),
        "reconciliation_score": _score(reconciliation_ok),
        "retrieval_score": _score(retrieval_ok),
        "injection_usefulness_score": _score(injection_ok),
        "notes": {
            "stored_id": response["id"],
        },
    }


def _lexical_ambiguity_scenario(tmp_path) -> dict:
    provider = _make_provider(tmp_path, session_id="sess-lexical")
    provider._store.upsert_many(
        "nick",
        [{"id": "pref", "content": "Nick prefers concise responses", "metadata": {"lane": "preferences", "source_type": "sync_turn"}}],
        session_id="sess-lexical-1",
    )
    provider._store.upsert_many(
        "nick",
        [{"id": "pref", "content": "Nick prefers concise responses", "metadata": {"lane": "preferences", "source_type": "sync_turn"}}],
        session_id="sess-lexical-2",
    )
    provider._store.upsert_many(
        "nick",
        [{"id": "music", "content": "Nick likes concise techno mixes", "metadata": {"lane": "preferences", "source_type": "sync_turn"}}],
        session_id="sess-lexical-1",
    )

    row_pref = provider._store.get_memory("nick", "pref")
    row_music = provider._store.get_memory("nick", "music")
    meta_pref = json.loads(row_pref["metadata_json"])
    meta_music = json.loads(row_music["metadata_json"])
    search = json.loads(provider.handle_tool_call("langmem_search", {"query": "concise", "top_k": 5}))
    top_memory = search.get("results", [{}])[0].get("memory", "") if search.get("results") else ""

    extraction_ok = row_pref is not None and row_music is not None
    reconciliation_ok = meta_pref["confirmation_count"] > meta_music["confirmation_count"]
    retrieval_ok = search.get("results", [{}])[0].get("id") == "pref"
    injection_ok = "concise responses" in top_memory

    return {
        "scenario": "retrieval_under_lexical_ambiguity",
        "extraction_score": _score(extraction_ok),
        "reconciliation_score": _score(reconciliation_ok),
        "retrieval_score": _score(retrieval_ok),
        "injection_usefulness_score": _score(injection_ok),
        "notes": {
            "top_result": top_memory,
        },
    }


def run_langmem_eval_harness(tmp_path) -> dict:
    scenario_results = [
        _explicit_preference_write_scenario(tmp_path / "explicit"),
        _preference_correction_scenario(tmp_path / "correction"),
        _cross_session_recall_scenario(tmp_path / "cross-session"),
        _lexical_ambiguity_scenario(tmp_path / "lexical"),
    ]
    summary = {
        "scenario_count": len(scenario_results),
        "average_extraction_score": sum(item["extraction_score"] for item in scenario_results) / len(scenario_results),
        "average_reconciliation_score": sum(item["reconciliation_score"] for item in scenario_results) / len(scenario_results),
        "average_retrieval_score": sum(item["retrieval_score"] for item in scenario_results) / len(scenario_results),
        "average_injection_usefulness_score": sum(item["injection_usefulness_score"] for item in scenario_results) / len(scenario_results),
    }
    results = {
        "scenarios": scenario_results,
        "summary": summary,
    }
    _write_results(results)
    return results


def test_langmem_eval_harness_writes_latest_results(tmp_path):
    results = run_langmem_eval_harness(tmp_path)

    assert results["summary"]["scenario_count"] == 4
    scenario_names = {scenario["scenario"] for scenario in results["scenarios"]}
    assert scenario_names == {
        "explicit_preference_write",
        "preference_correction_supersession",
        "cross_session_recall",
        "retrieval_under_lexical_ambiguity",
    }
    for scenario in results["scenarios"]:
        assert set(scenario) >= {
            "scenario",
            "extraction_score",
            "reconciliation_score",
            "retrieval_score",
            "injection_usefulness_score",
        }
        assert scenario["extraction_score"] == 1.0
        assert scenario["reconciliation_score"] == 1.0
        assert scenario["retrieval_score"] == 1.0
        assert scenario["injection_usefulness_score"] == 1.0

    assert ARTIFACT_PATH.exists()
    artifact = json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))
    assert artifact["summary"]["scenario_count"] == 4
