from datetime import datetime
from unittest.mock import MagicMock

from gateway.config import GatewayConfig, Platform
from gateway.session import SessionEntry


def _make_runner():
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig(
        auto_resume_last_session=True,
        auto_resume_message_limit=40,
    )
    runner.session_store = MagicMock()
    runner._startup_resume_messages = [
        {"role": "user", "content": "earlier question"},
        {"role": "assistant", "content": "earlier answer"},
    ]
    runner._startup_resume_source_session_id = "old-session"
    runner._startup_resume_consumed = False
    return runner


def test_seed_startup_resume_history_rewrites_empty_new_session():
    runner = _make_runner()
    now = datetime.now()
    entry = SessionEntry(
        session_key="key-1",
        session_id="new-session",
        created_at=now,
        updated_at=now,
        platform=Platform.TELEGRAM,
        chat_type="dm",
    )

    history = runner._maybe_seed_startup_resume_history(entry, [])

    assert history == [
        {"role": "user", "content": "earlier question"},
        {"role": "assistant", "content": "earlier answer"},
    ]
    runner.session_store.rewrite_transcript.assert_called_once_with(
        "new-session",
        history,
    )
    assert runner._startup_resume_consumed is True
    assert runner._startup_resume_messages == []


def test_seed_startup_resume_history_skips_nonempty_history():
    runner = _make_runner()
    now = datetime.now()
    entry = SessionEntry(
        session_key="key-1",
        session_id="new-session",
        created_at=now,
        updated_at=now,
        platform=Platform.TELEGRAM,
        chat_type="dm",
    )
    existing = [{"role": "user", "content": "already there"}]

    history = runner._maybe_seed_startup_resume_history(entry, existing)

    assert history == existing
    runner.session_store.rewrite_transcript.assert_not_called()
    assert runner._startup_resume_consumed is False


def test_seed_startup_resume_history_skips_auto_reset_session():
    runner = _make_runner()
    now = datetime.now()
    entry = SessionEntry(
        session_key="key-1",
        session_id="new-session",
        created_at=now,
        updated_at=now,
        platform=Platform.TELEGRAM,
        chat_type="dm",
        was_auto_reset=True,
    )

    history = runner._maybe_seed_startup_resume_history(entry, [])

    assert history == []
    runner.session_store.rewrite_transcript.assert_not_called()
    assert runner._startup_resume_consumed is False
