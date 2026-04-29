import sys
from pathlib import Path
from unittest.mock import patch

PLUGIN_PARENT = Path(__file__).resolve().parents[2]
HERMES_AGENT = Path.home() / ".hermes" / "hermes-agent"
for p in (PLUGIN_PARENT, HERMES_AGENT):
    ps = str(p)
    if ps not in sys.path:
        sys.path.insert(0, ps)

from episodic.store import EpisodicStore


def make_store(tmp_path):
    db_path = tmp_path / "skill_candidates.db"
    store = EpisodicStore(db_path=db_path)
    store.ensure_session("session-1", source="test")
    return store


def test_get_skill_candidate_settings_defaults_when_config_missing():
    from episodic.config import get_skill_candidate_settings

    with patch("episodic.config.load_config", return_value={}):
        settings = get_skill_candidate_settings()

    assert settings["enabled"] is True
    assert settings["mode"] == "detect-only"
    assert settings["auto_publish"] is False
    assert settings["min_occurrences"] == 3
    assert settings["scan_source"] == "jsonl"


def test_get_skill_candidate_settings_coerces_invalid_values_safely():
    from episodic.config import get_skill_candidate_settings

    with patch(
        "episodic.config.load_config",
        return_value={
            "memory": {
                "episodic": {
                    "skill_candidates_enabled": "false",
                    "skill_candidate_mode": "bogus",
                    "skill_candidate_auto_publish": "no",
                    "skill_candidate_min_occurrences": "not-an-int",
                    "skill_candidate_review_limit": "also-bad",
                    "skill_candidate_scan_source": "sideways",
                }
            }
        },
    ):
        settings = get_skill_candidate_settings()

    assert settings["enabled"] is False
    assert settings["mode"] == "detect-only"
    assert settings["auto_publish"] is False
    assert settings["min_occurrences"] == 3
    assert settings["review_limit"] == 10
    assert settings["scan_source"] == "jsonl"


def test_store_upserts_and_lists_skill_candidates(tmp_path):
    store = make_store(tmp_path)
    try:
        first = store.upsert_skill_candidate(
            {
                "id": "cand-1",
                "fingerprint": "workflow:terminal>patch",
                "title": "Repeated terminal patch workflow",
                "pattern_type": "workflow",
                "confidence": 0.75,
                "occurrence_count": 3,
                "source_sessions": ["session-1"],
                "evidence": [{"type": "tool_sequence", "value": ["terminal", "patch"]}],
                "metadata": {"scan_source": "jsonl"},
            }
        )
        second = store.upsert_skill_candidate(
            {
                "id": "cand-2",
                "fingerprint": "workflow:terminal>patch",
                "title": "Repeated terminal patch workflow",
                "pattern_type": "workflow",
                "confidence": 0.82,
                "occurrence_count": 4,
                "source_sessions": ["session-1", "session-2"],
                "evidence": [{"type": "tool_sequence", "value": ["terminal", "patch"]}],
                "metadata": {"scan_source": "jsonl"},
            }
        )

        rows = store.list_skill_candidates()

        assert first["fingerprint"] == second["fingerprint"]
        assert len(rows) == 1
        assert rows[0]["occurrence_count"] == 4
        assert rows[0]["status"] == "detected"
        assert rows[0]["source_sessions_json"]
    finally:
        store.close()


def test_store_upsert_preserves_drafted_status_and_sets_draft_timestamp(tmp_path):
    store = make_store(tmp_path)
    try:
        created = store.upsert_skill_candidate(
            {
                "id": "cand-1",
                "fingerprint": "workflow:terminal>patch",
                "title": "Repeated terminal patch workflow",
                "pattern_type": "workflow",
                "confidence": 0.75,
                "occurrence_count": 3,
                "source_sessions": ["session-1"],
                "evidence": [{"type": "tool_sequence", "value": ["terminal", "patch"]}],
                "metadata": {"scan_source": "jsonl"},
            }
        )
        drafted = store.update_skill_candidate_status(
            created["id"],
            "drafted",
            draft_markdown="# Draft",
            draft_generated_at=123.0,
        )
        assert drafted["status"] == "drafted"
        assert drafted["draft_generated_at"] == 123.0

        updated = store.upsert_skill_candidate(
            {
                "id": "cand-2",
                "fingerprint": "workflow:terminal>patch",
                "title": "Repeated terminal patch workflow",
                "pattern_type": "workflow",
                "confidence": 0.91,
                "occurrence_count": 5,
                "source_sessions": ["session-1", "session-2", "session-3"],
                "evidence": [{"type": "tool_sequence", "value": ["terminal", "patch"]}],
                "metadata": {"scan_source": "jsonl"},
            }
        )

        assert updated["status"] == "drafted"
        assert updated["draft_generated_at"] == 123.0
    finally:
        store.close()


def test_on_session_end_detect_only_creates_candidate_without_llm(tmp_path):
    from episodic.provider import EpisodicMemoryProvider

    store = make_store(tmp_path)
    try:
        provider = EpisodicMemoryProvider()
        provider._store = store
        provider._available = True
        provider._session_id = "session-1"
        provider._platform = "telegram"

        with patch("episodic.provider.ENABLE_SESSION_JOURNAL", False), \
             patch("episodic.provider.get_skill_candidate_settings", return_value={
                 "enabled": True,
                 "mode": "detect-only",
                 "auto_publish": False,
                 "min_occurrences": 3,
                 "review_limit": 10,
                 "scan_source": "jsonl",
             }), \
             patch("episodic.skill_candidates.detect_skill_candidates_for_session", return_value=[{"id": "cand-1"}]) as mock_detect, \
             patch("episodic.skill_candidates.draft_skill_candidate") as mock_draft:
            provider.on_session_end([])

        mock_detect.assert_called_once()
        mock_draft.assert_not_called()
    finally:
        store.close()


def test_provider_exposes_skill_candidate_review_tools(tmp_path):
    from episodic.provider import EpisodicMemoryProvider

    store = make_store(tmp_path)
    try:
        provider = EpisodicMemoryProvider()
        provider._store = store
        provider._available = True

        tool_names = {tool["name"] for tool in provider.get_tool_schemas()}

        assert "memory_list_skill_candidates" in tool_names
        assert "memory_get_skill_candidate" in tool_names
        assert "memory_update_skill_candidate" in tool_names
    finally:
        store.close()


def test_provider_lists_gets_and_updates_skill_candidates(tmp_path):
    from episodic.provider import EpisodicMemoryProvider
    import json

    store = make_store(tmp_path)
    try:
        created = store.upsert_skill_candidate(
            {
                "id": "cand-1",
                "fingerprint": "workflow:terminal>patch",
                "title": "Repeated terminal patch workflow",
                "pattern_type": "workflow",
                "confidence": 0.75,
                "occurrence_count": 3,
                "source_sessions": ["session-1"],
                "evidence": [{"type": "tool_sequence", "value": ["terminal", "patch"]}],
                "metadata": {"scan_source": "jsonl"},
            }
        )
        provider = EpisodicMemoryProvider()
        provider._store = store
        provider._available = True

        listed = json.loads(provider.handle_tool_call("memory_list_skill_candidates", {"limit": 10}))
        fetched = json.loads(provider.handle_tool_call("memory_get_skill_candidate", {"candidate_id": created["id"]}))
        updated = json.loads(provider.handle_tool_call("memory_update_skill_candidate", {"candidate_id": created["id"], "action": "approve"}))

        assert listed["count"] == 1
        assert listed["candidates"][0]["id"] == created["id"]
        assert fetched["id"] == created["id"]
        assert updated["status"] == "approved"
    finally:
        store.close()


def test_provider_drafts_and_promotes_skill_candidate(tmp_path):
    from episodic.provider import EpisodicMemoryProvider
    import json

    store = make_store(tmp_path)
    try:
        created = store.upsert_skill_candidate(
            {
                "id": "cand-1",
                "fingerprint": "workflow:terminal>patch",
                "title": "Repeated terminal patch workflow",
                "pattern_type": "workflow",
                "confidence": 0.75,
                "occurrence_count": 3,
                "source_sessions": ["session-1"],
                "evidence": [{"type": "tool_sequence", "value": ["terminal", "patch"]}],
                "metadata": {"scan_source": "jsonl"},
            }
        )
        provider = EpisodicMemoryProvider()
        provider._store = store
        provider._available = True

        drafted = json.loads(provider.handle_tool_call("memory_draft_skill_candidate", {"candidate_id": created["id"]}))
        prepared = json.loads(provider.handle_tool_call("memory_prepare_skill_candidate_for_creation", {"candidate_id": created["id"], "skill_name": "repeated-terminal-patch-workflow"}))
        promoted = json.loads(provider.handle_tool_call("memory_promote_skill_candidate", {"candidate_id": created["id"], "skill_name": "repeated-terminal-patch-workflow"}))

        assert drafted["status"] == "drafted"
        assert drafted["draft_markdown"].startswith("# Repeated terminal patch workflow")
        assert drafted["draft_generated_at"]
        assert prepared["skill_name"] == "repeated-terminal-patch-workflow"
        assert prepared["content"].startswith("# Repeated terminal patch workflow")
        assert prepared["candidate"]["id"] == created["id"]
        assert promoted["status"] == "published"
        assert promoted["published_skill_name"] == "repeated-terminal-patch-workflow"
        assert promoted["draft_markdown"].startswith("# Repeated terminal patch workflow")
    finally:
        store.close()
