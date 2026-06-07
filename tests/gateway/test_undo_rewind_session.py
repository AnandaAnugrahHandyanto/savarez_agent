"""Tests for SessionStore.rewind_session — the gateway /undo [N] primitive.

The gateway /undo backs up N user turns by soft-deleting the truncated rows
in state.db (active=0, kept for audit, hidden from re-prompts/search) via
SessionDB.rewind_to_message, rather than the old hard rewrite_transcript.
load_transcript returns only the active view. See issue #21910.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hermes_state import SessionDB
from gateway.config import GatewayConfig
from gateway.session import SessionStore


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    db = SessionDB(db_path=tmp_path / "state.db")
    s = SessionStore(sessions_dir=tmp_path / "sessions", config=GatewayConfig())
    s._db = db  # use the same DB instance the fixture seeds
    return s


def _seed(store, sid, source="telegram", turns=3):
    store._db.create_session(sid, source=source)
    for i in range(1, turns + 1):
        store._db.append_message(sid, "user", f"q{i}")
        store._db.append_message(sid, "assistant", f"a{i}")
    return sid


def test_rewind_default_one_turn(store):
    sid = _seed(store, "gw-1")
    res = store.rewind_session(sid)
    assert res["turns_undone"] == 1
    assert res["target_text"] == "q3"
    assert res["rewound_count"] == 2  # q3 + a3
    active = store.load_transcript(sid)
    assert [m["role"] for m in active] == ["user", "assistant", "user", "assistant"]


def test_rewind_n_turns(store):
    sid = _seed(store, "gw-2")
    res = store.rewind_session(sid, 2)
    assert res["turns_undone"] == 2
    assert res["target_text"] == "q2"
    assert res["rewound_count"] == 4  # q2,a2,q3,a3
    assert len(store.load_transcript(sid)) == 2  # q1,a1


def test_rewind_soft_deletes_rows_for_audit(store):
    sid = _seed(store, "gw-3")
    store.rewind_session(sid, 1)
    all_rows = store._db.get_messages(sid, include_inactive=True)
    assert len(all_rows) == 6  # nothing hard-deleted
    assert sum(1 for r in all_rows if r["active"] == 1) == 4
    assert store._db.get_session(sid)["rewind_count"] == 1


def test_rewind_clamps_to_oldest_turn(store):
    sid = _seed(store, "gw-4", turns=2)
    res = store.rewind_session(sid, 99)
    assert res["target_text"] == "q1"
    assert len(store.load_transcript(sid)) == 0


def test_rewind_empty_session_returns_none(store):
    store._db.create_session("gw-5", source="discord")
    assert store.rewind_session("gw-5") is None


def test_rewind_clamps_negative_count_to_one(store):
    sid = _seed(store, "gw-6")
    res = store.rewind_session(sid, -5)
    assert res["turns_undone"] == 1
    assert res["target_text"] == "q3"


# ---------------------------------------------------------------------------
# _handle_undo_command — memory provider notification parity with CLI /undo
# ---------------------------------------------------------------------------

def _make_undo_runner(store, session_id="undo-session-1"):
    """Minimal GatewayRunner fixture wired to the given SessionStore."""
    import collections
    import threading
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, MagicMock

    from gateway.config import GatewayConfig, Platform, PlatformConfig
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig(
        platforms={Platform.TELEGRAM: PlatformConfig(enabled=True, token="***")}
    )
    runner.session_store = store
    runner._agent_cache = collections.OrderedDict()
    runner._agent_cache_lock = threading.Lock()
    runner._running_agents = {}
    runner.hooks = SimpleNamespace(emit=AsyncMock(), loaded_hooks=False)
    runner.adapters = {}
    return runner, session_id


def _fake_session_entry(session_id: str):
    """Build a minimal SessionEntry-like object for test stubs."""
    from unittest.mock import MagicMock
    entry = MagicMock()
    entry.session_id = session_id
    entry.last_prompt_tokens = 0
    return entry


def test_undo_notifies_memory_manager_with_rewound(store):
    """_handle_undo_command must call memory_manager.on_session_switch(rewound=True).

    Mirrors CLI /undo which fires the same hook so per-turn document caches
    in memory providers invalidate after a rewind (#6672, #21910).
    """
    import asyncio
    from unittest.mock import MagicMock, patch

    from gateway.config import Platform
    from gateway.platforms.base import MessageEvent
    from gateway.session import SessionSource

    sid = _seed(store, "undo-mm-1", turns=2)
    runner, _ = _make_undo_runner(store)

    # Fake cached agent with a spy memory_manager.
    fake_mm = MagicMock()
    fake_agent = MagicMock()
    fake_agent._memory_manager = fake_mm
    runner._agent_cache["telegram:u1:c1:"] = (fake_agent,)

    source = SessionSource(
        platform=Platform.TELEGRAM,
        user_id="u1",
        chat_id="c1",
        user_name="tester",
        chat_type="dm",
    )
    event = MessageEvent(text="/undo", source=source, message_id="m1")

    fake_entry = _fake_session_entry(sid)

    with patch("gateway.run.build_session_key", return_value="telegram:u1:c1:"), \
         patch("gateway.run.t", side_effect=lambda key, **kw: key), \
         patch.object(runner.session_store, "get_or_create_session", return_value=fake_entry), \
         patch.object(runner.session_store, "rewind_session",
                      return_value={"rewound_count": 2, "turns_undone": 1, "target_text": "q2"}):
        result = asyncio.get_event_loop().run_until_complete(
            runner._handle_undo_command(event)
        )

    assert result == "gateway.undo.removed"
    fake_mm.on_session_switch.assert_called_once_with(
        sid,
        parent_session_id="",
        reset=False,
        rewound=True,
    )
    # Agent must have been evicted from cache.
    assert "telegram:u1:c1:" not in runner._agent_cache


def test_undo_no_cached_agent_still_succeeds(store):
    """_handle_undo_command works when there is no cached agent (cold session)."""
    import asyncio
    from unittest.mock import patch

    from gateway.config import Platform
    from gateway.platforms.base import MessageEvent
    from gateway.session import SessionSource

    sid = _seed(store, "undo-cold-1", turns=2)
    runner, _ = _make_undo_runner(store)
    # No entry in _agent_cache — cold session.

    source = SessionSource(
        platform=Platform.TELEGRAM,
        user_id="u2",
        chat_id="c2",
        user_name="tester",
        chat_type="dm",
    )
    event = MessageEvent(text="/undo", source=source, message_id="m2")

    fake_entry = _fake_session_entry(sid)

    with patch("gateway.run.build_session_key", return_value="telegram:u2:c2:"), \
         patch("gateway.run.t", side_effect=lambda key, **kw: key), \
         patch.object(runner.session_store, "get_or_create_session", return_value=fake_entry), \
         patch.object(runner.session_store, "rewind_session",
                      return_value={"rewound_count": 2, "turns_undone": 1, "target_text": "q2"}):
        result = asyncio.get_event_loop().run_until_complete(
            runner._handle_undo_command(event)
        )

    assert result == "gateway.undo.removed"
