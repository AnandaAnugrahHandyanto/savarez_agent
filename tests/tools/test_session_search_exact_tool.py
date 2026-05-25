from __future__ import annotations

import json

import pytest
from hermes_state import SessionDB


@pytest.fixture()
def db(tmp_path):
    db_path = tmp_path / "test_state.db"
    session_db = SessionDB(db_path=db_path)
    yield session_db
    session_db.close()


def test_exact_token_hit_returns_raw_snippet(db):
    from tools.session_search_exact_tool import session_search_exact

    db.create_session(session_id="s1", source="feishu")
    db.append_message("s1", role="assistant", content="management key is c61f7999114fe65e099f5c0ca7af851e")

    payload = json.loads(session_search_exact(query="c61f7999114fe65e099f5c0ca7af851e", db=db))

    assert payload["success"] is True
    assert payload["mode"] == "exact"
    assert payload["count"] == 1
    assert payload["results"][0]["session_id"] == "s1"
    assert "c61f7999114fe65e099f5c0ca7af851e" in payload["results"][0]["snippet"]


def test_group_by_session_false_preserves_multiple_hits(db):
    from tools.session_search_exact_tool import session_search_exact

    db.create_session(session_id="s1", source="cli")
    db.append_message("s1", role="user", content="uuid 123e4567-e89b-12d3-a456-426614174000")
    db.append_message("s1", role="assistant", content="same uuid 123e4567-e89b-12d3-a456-426614174000 again")

    payload = json.loads(
        session_search_exact(
            query="123e4567-e89b-12d3-a456-426614174000",
            group_by_session=False,
            limit=10,
            db=db,
        )
    )

    assert payload["success"] is True
    assert payload["count"] >= 2
    assert all(item["session_id"] == "s1" for item in payload["results"])


def test_group_by_session_true_dedupes_session_hits(db):
    from tools.session_search_exact_tool import session_search_exact

    db.create_session(session_id="s1", source="cli")
    db.append_message("s1", role="user", content="remote-management.secret-key is enabled")
    db.append_message("s1", role="assistant", content="I repeated remote-management.secret-key for validation")

    payload = json.loads(
        session_search_exact(
            query='"remote-management.secret-key"',
            group_by_session=True,
            limit=10,
            db=db,
        )
    )

    assert payload["success"] is True
    assert payload["count"] == 1
    assert payload["results"][0]["session_id"] == "s1"


def test_source_and_role_filters_apply(db):
    from tools.session_search_exact_tool import session_search_exact

    db.create_session(session_id="s1", source="feishu")
    db.append_message("s1", role="assistant", content="error path /var/log/app/error.log")

    db.create_session(session_id="s2", source="cli")
    db.append_message("s2", role="user", content="error path /var/log/app/error.log")

    payload = json.loads(
        session_search_exact(
            query="/var/log/app/error.log",
            source_filter="feishu",
            role_filter="assistant",
            db=db,
        )
    )

    assert payload["success"] is True
    assert payload["count"] == 1
    assert payload["match_mode"] == "substring"
    assert payload["results"][0]["source"] == "feishu"
    assert payload["results"][0]["role"] == "assistant"


def test_auto_mode_prefers_real_content_over_query_echo_noise(db):
    from tools.session_search_exact_tool import session_search_exact

    db.create_session(session_id="s1", source="feishu")
    db.append_message("s1", role="assistant", content="real key c61f7999114fe65e099f5c0ca7af851e stored here")
    db.append_message("s1", role="assistant", content="")

    payload = json.loads(session_search_exact(query="c61f7999114fe65e099f5c0ca7af851e", db=db))

    assert payload["success"] is True
    assert payload["count"] >= 1
    assert any(
        "real key c61f7999114fe65e099f5c0ca7af851e" in (
            (item.get("snippet") or "")
            .replace(">>>", "")
            .replace("<<<", "")
            or (item.get("content") or "")
            or " ".join(ctx.get("content", "") for ctx in item.get("context") or [])
        )
        for item in payload["results"]
    )


def test_ranking_demotes_tool_call_echoes(db):
    from tools.session_search_exact_tool import session_search_exact

    db.create_session(session_id="s1", source="feishu")
    db.append_message("s1", role="assistant", content='[{"id":"call_1","function":{"name":"session_search","arguments":"{\\"query\\":\\"c61f7999114fe65e099f5c0ca7af851e\\"}"}}]')
    db.append_message("s1", role="assistant", content="管理密钥就是 c61f7999114fe65e099f5c0ca7af851e")

    payload = json.loads(session_search_exact(query="c61f7999114fe65e099f5c0ca7af851e", group_by_session=False, db=db))

    assert payload["success"] is True
    assert payload["count"] >= 1
    top = payload["results"][0]
    top_text = (top.get("snippet") or "") + " " + (top.get("content") or "")
    assert "管理密钥就是" in top_text


def test_invalid_match_mode_returns_error(db):
    from tools.session_search_exact_tool import session_search_exact

    payload = json.loads(session_search_exact(query="docker", match_mode="boom", db=db))
    assert payload["success"] is False
    assert "match_mode must be one of" in payload["error"]


def test_missing_query_returns_error(db):
    from tools.session_search_exact_tool import session_search_exact

    payload = json.loads(session_search_exact(query="", db=db))
    assert payload["success"] is False
    assert "query is required" in payload["error"]
