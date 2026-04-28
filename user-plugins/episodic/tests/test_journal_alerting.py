import os
import sys
import time
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
    db_path = tmp_path / "test_index.db"
    store = EpisodicStore(db_path=db_path)
    store.ensure_session("test-session-1", source="test")
    return store


def test_on_session_end_writes_failure_artifact_when_journal_raises(tmp_path):
    from episodic.provider import EpisodicMemoryProvider

    store = make_store(tmp_path)
    try:
        provider = EpisodicMemoryProvider()
        provider._store = store
        provider._available = True
        provider._session_id = "test-session-1"
        provider._platform = "telegram"

        with patch("episodic.provider.get_hermes_home", return_value=tmp_path), \
             patch("episodic.journal.write_session_journal", side_effect=RuntimeError("boom")), \
             patch.object(provider, "_send_telegram_alert") as mock_alert:
            provider.on_session_end([])

        artifacts = list((tmp_path / "tmp" / "episodic-failures").glob("journal-failure_test-session-1_*.md"))
        assert len(artifacts) == 1
        content = artifacts[0].read_text()
        assert "journal_write_failed" in content
        assert "boom" in content
        mock_alert.assert_called_once()
    finally:
        store.close()


def test_find_missing_journal_sessions_returns_orphaned_jsonl(tmp_path):
    from episodic.provider import EpisodicMemoryProvider

    sessions_dir = tmp_path / "memory" / "sessions"
    sessions_dir.mkdir(parents=True)
    journals_dir = tmp_path / "wiki" / "session-recordings"
    journals_dir.mkdir(parents=True)

    orphan = sessions_dir / "orphan-session.jsonl"
    orphan.write_text('{"role":"user","content":"hello","timestamp":1}\n')
    old_ts = time.time() - 900
    os.utime(orphan, (old_ts, old_ts))

    provider = EpisodicMemoryProvider()

    with patch("episodic.provider.SESSIONS_DIR", sessions_dir), \
         patch("episodic.provider.JOURNAL_DIR", journals_dir):
        missing = provider._find_missing_journal_sessions(grace_seconds=300)

    assert len(missing) == 1
    assert missing[0]["session_id"] == "orphan-session"
