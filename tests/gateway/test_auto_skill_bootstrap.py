from datetime import datetime, timedelta
from types import SimpleNamespace

from gateway.run import _history_has_conversation_messages, _should_bootstrap_auto_skills


def test_history_has_conversation_messages_ignores_metadata_only_entries():
    history = [
        {"role": "session_meta", "content": "metadata"},
        {"role": "system", "content": "system prompt"},
    ]

    assert not _history_has_conversation_messages(history)


def test_history_has_conversation_messages_detects_real_user_content():
    assert _history_has_conversation_messages([{"role": "user", "content": "hello"}])


def test_should_bootstrap_auto_skills_for_existing_metadata_only_session():
    now = datetime.now()
    session_entry = SimpleNamespace(
        created_at=now - timedelta(minutes=1),
        updated_at=now,
        was_auto_reset=False,
    )
    history = [{"role": "session_meta", "content": "created"}]

    assert _should_bootstrap_auto_skills(session_entry, history)


def test_should_not_bootstrap_auto_skills_when_conversation_exists():
    now = datetime.now()
    session_entry = SimpleNamespace(
        created_at=now - timedelta(minutes=1),
        updated_at=now,
        was_auto_reset=False,
    )
    history = [{"role": "assistant", "content": "loaded"}]

    assert not _should_bootstrap_auto_skills(session_entry, history)
