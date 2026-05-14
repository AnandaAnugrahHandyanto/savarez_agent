from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

_repo = str(Path(__file__).resolve().parents[2])
if _repo not in sys.path:
    sys.path.insert(0, _repo)


class _FakeSessionDB:
    instances: list["_FakeSessionDB"] = []

    def __init__(self):
        self.closed = False
        _FakeSessionDB.instances.append(self)

    def list_sessions_rich(self, limit: int = 20, offset: int = 0):
        self.limit = limit
        self.offset = offset
        return [
            {
                "id": "session-1",
                "source": "cron",
                "model": "gpt-test",
                "title": "Large prompt session",
                "started_at": 1000.0,
                "ended_at": 1100.0,
                "last_active": 1100.0,
                "message_count": 3,
                "tool_call_count": 1,
                "input_tokens": 10,
                "output_tokens": 20,
                "preview": "hello",
                "parent_session_id": None,
                # These are intentionally large/private list-only payload bloat.
                "system_prompt": "x" * 100_000,
                "model_config": {"secret_shape": "not for list responses"},
                "handoff_state": {"verbose": True},
                "user_id": "operator",
            }
        ]

    def session_count(self):
        return 1

    def close(self):
        self.closed = True


def test_sessions_endpoint_returns_lightweight_summary(monkeypatch):
    """The dashboard session list must not ship full session blobs.

    The frontend SessionInfo contract only needs summary metadata; full prompts
    and model config belong on detail/history endpoints. This keeps the dashboard
    usable on long-running installs with thousands of cron sessions.
    """
    from hermes_cli import web_server

    _FakeSessionDB.instances.clear()
    monkeypatch.setitem(sys.modules, "hermes_state", SimpleNamespace(SessionDB=_FakeSessionDB))

    result = asyncio.run(web_server.get_sessions(limit=5000, offset=-10))

    assert result["limit"] == 100
    assert result["offset"] == 0
    assert result["total"] == 1
    assert _FakeSessionDB.instances[-1].limit == 100
    assert _FakeSessionDB.instances[-1].offset == 0
    assert _FakeSessionDB.instances[-1].closed

    session = result["sessions"][0]
    assert session == {
        "id": "session-1",
        "source": "cron",
        "model": "gpt-test",
        "title": "Large prompt session",
        "started_at": 1000.0,
        "ended_at": 1100.0,
        "last_active": 1100.0,
        "message_count": 3,
        "tool_call_count": 1,
        "input_tokens": 10,
        "output_tokens": 20,
        "preview": "hello",
        "parent_session_id": None,
        "is_active": False,
    }
    assert "system_prompt" not in session
    assert "model_config" not in session
    assert "handoff_state" not in session
    assert "user_id" not in session
