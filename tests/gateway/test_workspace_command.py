"""Tests for gateway session-scoped workspace bindings."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from gateway.config import GatewayConfig, Platform
from gateway.platforms.base import MessageEvent
from gateway.session import SessionSource, SessionStore


class _FakeSessionDB:
    def __init__(self):
        self.calls: list[tuple] = []

    def create_session(self, **kwargs):
        self.calls.append(("create", kwargs))

    def end_session(self, session_id, reason):
        self.calls.append(("end", session_id, reason))

    def reopen_session(self, session_id):
        self.calls.append(("reopen", session_id))

    def update_session_cwd(self, session_id, cwd):
        self.calls.append(("update_cwd", session_id, cwd))


def _source(chat_id: str = "chat-1") -> SessionSource:
    return SessionSource(
        platform=Platform.TELEGRAM,
        chat_id=chat_id,
        chat_type="dm",
        user_id="user-1",
    )


def _event(text: str, source: SessionSource | None = None) -> MessageEvent:
    return MessageEvent(text=text, source=source or _source(), message_id="m1")


def _runner(tmp_path, monkeypatch):
    from gateway.run import GatewayRunner

    store = SessionStore(sessions_dir=tmp_path / "sessions", config=GatewayConfig())
    store._db = None
    runner = object.__new__(GatewayRunner)
    runner.session_store = store
    runner.config = GatewayConfig()
    runner._agent_cache = {}
    runner._agent_cache_lock = None
    runner._evict_cached_agent = MagicMock()
    runner._global_gateway_cwd = lambda: str(tmp_path / "global")
    monkeypatch.setattr("tools.terminal_tool.cleanup_vm", lambda *_a, **_kw: None)
    calls: list[tuple[str, str | None]] = []

    def _register(session_key, cwd, *, session_id=None):
        calls.append((session_key, cwd))
        if session_id:
            calls.append((session_id, cwd))

    runner._register_gateway_workspace_override = _register
    runner._workspace_calls = calls
    runner.adapters = {}
    runner.hooks = SimpleNamespace(emit=MagicMock())
    return runner


def test_sync_workspace_state_clears_stale_binding(tmp_path, monkeypatch):
    runner = _runner(tmp_path, monkeypatch)
    source = _source()
    project = tmp_path / "project"
    project.mkdir()
    entry = runner.session_store.get_or_create_session(source)
    runner.session_store.set_workspace_cwd(entry.session_key, str(project))
    project.rmdir()

    result = runner._sync_gateway_workspace_state(entry.session_key, entry)

    assert result is None
    assert entry.workspace_cwd is None
    assert (entry.session_key, None) in runner._workspace_calls
    assert (entry.session_id, None) in runner._workspace_calls
    runner._evict_cached_agent.assert_called_with(entry.session_key)


def test_sync_workspace_state_updates_current_session_id_db_and_override(tmp_path, monkeypatch):
    runner = _runner(tmp_path, monkeypatch)
    fake_db = _FakeSessionDB()
    runner.session_store._db = fake_db
    source = _source()
    project = tmp_path / "project"
    project.mkdir()
    entry = runner.session_store.get_or_create_session(source)
    runner.session_store.set_workspace_cwd(entry.session_key, str(project))
    entry.session_id = "split-session"

    result = runner._sync_gateway_workspace_state(entry.session_key, entry)

    assert result == str(project)
    assert (entry.session_key, str(project)) in runner._workspace_calls
    assert ("split-session", str(project)) in runner._workspace_calls
    assert ("update_cwd", "split-session", str(project)) in fake_db.calls


@pytest.mark.asyncio
async def test_workspace_status_uses_global_default(tmp_path, monkeypatch):
    runner = _runner(tmp_path, monkeypatch)

    result = await runner._handle_workspace_command(_event("/workspace"))

    assert "global default" in result
    assert str(tmp_path / "global") in result


@pytest.mark.asyncio
async def test_workspace_set_and_clear_are_session_scoped(tmp_path, monkeypatch):
    runner = _runner(tmp_path, monkeypatch)
    project = tmp_path / "project"
    project.mkdir()
    source = _source()

    set_result = await runner._handle_workspace_command(
        _event(f"/workspace {project}", source)
    )
    entry = runner.session_store.get_or_create_session(source)

    assert "Workspace set" in set_result
    assert entry.workspace_cwd == str(project)
    assert (entry.session_key, str(project)) in runner._workspace_calls
    assert (entry.session_id, str(project)) in runner._workspace_calls
    runner._evict_cached_agent.assert_called_with(entry.session_key)

    clear_result = await runner._handle_workspace_command(_event("/workspace clear", source))
    entry = runner.session_store.get_or_create_session(source)

    assert "cleared" in clear_result
    assert entry.workspace_cwd is None
    assert (entry.session_key, None) in runner._workspace_calls
    assert (entry.session_id, None) in runner._workspace_calls


@pytest.mark.asyncio
async def test_workspace_rejects_relative_and_missing_paths(tmp_path, monkeypatch):
    runner = _runner(tmp_path, monkeypatch)

    relative = await runner._handle_workspace_command(_event("/workspace project"))
    missing = await runner._handle_workspace_command(
        _event(f"/workspace {tmp_path / 'missing'}")
    )

    assert "absolute path" in relative
    assert "not an existing directory" in missing


def test_session_store_persists_workspace_across_reload_and_reset(tmp_path):
    source = _source()
    config = GatewayConfig()
    store = SessionStore(sessions_dir=tmp_path, config=config)
    store._db = None
    entry = store.get_or_create_session(source)
    store.set_workspace_cwd(entry.session_key, "/tmp/project")

    reloaded = SessionStore(sessions_dir=tmp_path, config=config)
    reloaded._db = None
    loaded_entry = reloaded.get_or_create_session(source)
    assert loaded_entry.workspace_cwd == "/tmp/project"

    reset_entry = reloaded.reset_session(loaded_entry.session_key)
    assert reset_entry is not None
    assert reset_entry.workspace_cwd == "/tmp/project"


def test_session_store_carries_workspace_across_session_switch(tmp_path):
    source = _source()
    fake_db = _FakeSessionDB()
    store = SessionStore(sessions_dir=tmp_path, config=GatewayConfig())
    store._db = fake_db

    entry = store.get_or_create_session(source)
    store.set_workspace_cwd(entry.session_key, "/tmp/project")

    switched = store.switch_session(entry.session_key, "resumed-session")

    assert switched is not None
    assert switched.workspace_cwd == "/tmp/project"
    assert ("reopen", "resumed-session") in fake_db.calls
    assert ("update_cwd", "resumed-session", "/tmp/project") in fake_db.calls
