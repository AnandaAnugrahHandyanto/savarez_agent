"""Tests for visible Telegram topic delegate helpers."""

from datetime import datetime, timezone

import pytest

from gateway.config import Platform
from gateway.session import SessionSource, build_session_key


def test_telegram_forum_topic_session_key_uses_chat_and_thread():
    source = SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="-1003933169427",
        chat_name="Hermes Sessions",
        chat_type="group",
        user_id="6605861022",
        thread_id="4",
    )

    assert build_session_key(source) == "agent:main:telegram:group:-1003933169427:4"


def test_telegram_forum_topic_session_key_shared_across_users_by_default():
    first = SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="-1001",
        chat_type="group",
        user_id="u1",
        thread_id="42",
    )
    second = SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="-1001",
        chat_type="group",
        user_id="u2",
        thread_id="42",
    )

    assert build_session_key(first) == build_session_key(second)


def test_sanitize_topic_name_limits_and_removes_newlines():
    from gateway.visible_sessions import sanitize_topic_name

    raw = "  PR Review\nSafe\tGateway\rRestart  "

    assert sanitize_topic_name(raw) == "PR Review Safe Gateway Restart"


def test_sanitize_topic_name_rejects_empty_after_cleanup():
    from gateway.visible_sessions import sanitize_topic_name

    with pytest.raises(ValueError, match="topic name"):
        sanitize_topic_name("\n\t   ")


def test_sanitize_topic_name_rejects_secret_like_values():
    from gateway.visible_sessions import sanitize_topic_name

    with pytest.raises(ValueError, match="secret"):
        sanitize_topic_name("sk-proj-abcdefghijklmnopqrstuvwxyz1234567890")


def test_sanitize_topic_name_truncates_without_trailing_separator():
    from gateway.visible_sessions import sanitize_topic_name

    raw = "A" * 80 + "   "

    assert sanitize_topic_name(raw) == "A" * 64


def test_parse_and_format_telegram_visible_handle():
    from gateway.visible_sessions import format_visible_handle, parse_visible_handle

    handle = parse_visible_handle("telegram:-1003933169427:14")

    assert handle.platform == "telegram"
    assert handle.chat_id == "-1003933169427"
    assert handle.thread_id == "14"
    assert format_visible_handle(handle.platform, handle.chat_id, handle.thread_id) == "telegram:-1003933169427:14"


def test_parse_visible_handle_rejects_missing_thread():
    from gateway.visible_sessions import parse_visible_handle

    with pytest.raises(ValueError, match="thread"):
        parse_visible_handle("telegram:-1003933169427")


def test_format_visible_seed_prompt_shows_prompt_in_visible_block():
    from gateway.visible_sessions import format_visible_seed_prompt

    visible = format_visible_seed_prompt("Reply exactly: VISIBLE_TOPIC_OK")

    assert visible.startswith("Seed prompt from parent to this child agent:")
    assert "```text\nReply exactly: VISIBLE_TOPIC_OK\n```" in visible


def test_format_visible_seed_prompt_uses_longer_fence_when_prompt_contains_backticks():
    from gateway.visible_sessions import format_visible_seed_prompt

    visible = format_visible_seed_prompt("include ``` fenced text")

    assert visible.startswith("Seed prompt from parent to this child agent:")
    assert visible.count("````") == 2
    assert "include ``` fenced text" in visible


def test_parse_visible_handle_rejects_extra_colons():
    from gateway.visible_sessions import parse_visible_handle

    with pytest.raises(ValueError, match="format"):
        parse_visible_handle("telegram:-1003933169427:14:extra")


def test_default_visible_session_registry_path_uses_hermes_home(tmp_path):
    from gateway.visible_sessions import default_visible_session_registry_path

    assert default_visible_session_registry_path(tmp_path) == tmp_path / "visible_sessions.json"


def test_visible_session_handle_round_trips_json():
    from gateway.visible_sessions import VisibleSessionHandle

    handle = VisibleSessionHandle(
        platform="telegram",
        chat_id="-1003933169427",
        thread_id="14",
        topic_name="PR - Safe Gateway Restart",
        session_key="agent:main:telegram:group:-1003933169427:14",
        session_id="20260513_150000_deadbeef",
        target="telegram:-1003933169427:14",
        created_by_session_key="agent:main:telegram:group:-1003933169427:1",
        created_by_user_id="6605861022",
        created_at=datetime(2026, 5, 13, 15, 0, tzinfo=timezone.utc),
    )

    assert VisibleSessionHandle.from_dict(handle.to_dict()) == handle


def test_visible_session_handle_save_load_roundtrip(tmp_path):
    from gateway.visible_sessions import (
        VisibleSessionHandle,
        load_visible_session_handles,
        save_visible_session_handles,
    )

    handle = VisibleSessionHandle(
        platform="telegram",
        chat_id="-1003933169427",
        thread_id="14",
        topic_name="PR - Safe Gateway Restart",
        session_key="agent:main:telegram:group:-1003933169427:14",
        session_id="20260513_150000_deadbeef",
        target="telegram:-1003933169427:14",
        created_by_session_key="agent:main:telegram:group:-1003933169427:1",
        created_by_user_id="6605861022",
        created_at=datetime(2026, 5, 13, 15, 0, tzinfo=timezone.utc),
    )
    registry_path = tmp_path / "nested" / "visible_sessions.json"

    save_visible_session_handles(registry_path, [handle])

    assert load_visible_session_handles(registry_path) == [handle]


def test_load_visible_session_handles_rejects_non_list_registry(tmp_path):
    from gateway.visible_sessions import load_visible_session_handles

    registry_path = tmp_path / "visible_sessions.json"
    registry_path.write_text('{"not": "a list"}', encoding="utf-8")

    with pytest.raises(ValueError, match="JSON list"):
        load_visible_session_handles(registry_path)
