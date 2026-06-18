"""Regression tests for bounded/lazy CLI MCP startup."""

from __future__ import annotations

from argparse import Namespace
import sys
import threading
import time
import types

import pytest

import cli as cli_mod
from hermes_cli import main as main_mod
from hermes_cli import mcp_startup


@pytest.fixture(autouse=True)
def _reset_mcp_startup_state():
    saved_started = mcp_startup._mcp_discovery_started
    saved_thread = mcp_startup._mcp_discovery_thread
    saved_late = getattr(mcp_startup, "_mcp_late_refresh_thread", None)
    try:
        mcp_startup._mcp_discovery_started = False
        mcp_startup._mcp_discovery_thread = None
        mcp_startup._mcp_late_refresh_thread = None
        yield
    finally:
        thread = mcp_startup._mcp_discovery_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)
        late = mcp_startup._mcp_late_refresh_thread
        if late is not None and late.is_alive():
            late.join(timeout=2.0)
        mcp_startup._mcp_discovery_started = saved_started
        mcp_startup._mcp_discovery_thread = saved_thread
        mcp_startup._mcp_late_refresh_thread = saved_late


def _agent_args(**overrides) -> Namespace:
    base = {
        "accept_hooks": False,
        "command": "chat",
        "cron_command": None,
        "gateway_command": None,
        "mcp_action": None,
        "tui": False,
    }
    base.update(overrides)
    return Namespace(**base)


def test_prepare_agent_startup_backgrounds_blocking_mcp_for_chat(monkeypatch):
    stop = threading.Event()
    calls = {"mcp": 0}

    def _blocking_discover():
        calls["mcp"] += 1
        stop.wait()

    monkeypatch.setitem(
        sys.modules,
        "hermes_cli.plugins",
        types.SimpleNamespace(discover_plugins=lambda: None),
    )
    monkeypatch.setitem(
        sys.modules,
        "hermes_cli.config",
        types.SimpleNamespace(
            read_raw_config=lambda: {"mcp_servers": {"demo": {"transport": "stdio"}}},
            load_config=lambda: {},
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "agent.shell_hooks",
        types.SimpleNamespace(register_from_config=lambda *_a, **_k: None),
    )
    monkeypatch.setitem(
        sys.modules,
        "tools.mcp_tool",
        types.SimpleNamespace(discover_mcp_tools=_blocking_discover),
    )

    try:
        start = time.monotonic()
        main_mod._prepare_agent_startup(_agent_args())
        elapsed = time.monotonic() - start
        assert elapsed < 0.2
        assert calls["mcp"] == 1
        assert mcp_startup._mcp_discovery_thread is not None
        assert mcp_startup._mcp_discovery_thread.is_alive()
    finally:
        stop.set()


def test_prepare_agent_startup_skips_mcp_bootstrap_for_tui_chat(monkeypatch):
    calls = {"mcp": 0}

    monkeypatch.setitem(
        sys.modules,
        "hermes_cli.plugins",
        types.SimpleNamespace(discover_plugins=lambda: None),
    )
    monkeypatch.setitem(
        sys.modules,
        "hermes_cli.config",
        types.SimpleNamespace(load_config=lambda: {}),
    )
    monkeypatch.setitem(
        sys.modules,
        "agent.shell_hooks",
        types.SimpleNamespace(register_from_config=lambda *_a, **_k: None),
    )
    monkeypatch.setitem(
        sys.modules,
        "tools.mcp_tool",
        types.SimpleNamespace(
            discover_mcp_tools=lambda: calls.__setitem__("mcp", calls["mcp"] + 1)
        ),
    )

    main_mod._prepare_agent_startup(_agent_args(tui=True))

    assert calls["mcp"] == 0
    assert mcp_startup._mcp_discovery_thread is None


def test_cli_get_tool_definitions_briefly_waits_for_fast_mcp_thread(monkeypatch):
    thread = threading.Thread(target=lambda: time.sleep(0.05), daemon=True)
    thread.start()
    mcp_startup._mcp_discovery_thread = thread

    monkeypatch.setitem(
        sys.modules,
        "model_tools",
        types.SimpleNamespace(get_tool_definitions=lambda *_a, **_k: ["ok"]),
    )

    start = time.monotonic()
    result = cli_mod.get_tool_definitions(enabled_toolsets=["web"], quiet_mode=True)
    elapsed = time.monotonic() - start

    assert result == ["ok"]
    assert elapsed >= 0.04
    assert not thread.is_alive()


def test_init_agent_waits_for_mcp_discovery_before_agent_build(monkeypatch):
    waited = {"done": False}

    cli = cli_mod.HermesCLI(compact=True)
    cli._session_db = object()
    cli._resumed = False
    cli.conversation_history = []
    cli._install_tool_callbacks = lambda: None
    cli._ensure_tirith_security = lambda: None
    cli._ensure_runtime_credentials = lambda: True

    monkeypatch.setattr(
        mcp_startup,
        "wait_for_mcp_discovery",
        lambda timeout=0.75: waited.__setitem__("done", True),
    )

    def _fake_agent(*_a, **_k):
        assert waited["done"] is True
        return types.SimpleNamespace()

    monkeypatch.setattr(cli_mod, "AIAgent", _fake_agent)

    assert cli._init_agent() is True


# ── spawn_late_mcp_refresh tests ──────────────────────────────────────


class _FakeAgent:
    """Minimal agent stub for late-refresh tests."""

    def __init__(self, tools=None, valid_tool_names=None):
        self.tools = tools or []
        self.valid_tool_names = valid_tool_names or set()


def _make_tool_def(name):
    return {"function": {"name": name, "parameters": {}, "description": ""}}


def test_late_refresh_inline_when_discovery_already_done():
    """When discovery thread is None/finished, do an inline refresh check."""
    agent = _FakeAgent(tools=[_make_tool_def("existing")], valid_tool_names={"existing"})
    new_tools = [_make_tool_def("existing"), _make_tool_def("new_tool")]
    callback_calls = []

    mcp_startup._mcp_discovery_thread = None

    mcp_startup.spawn_late_mcp_refresh(
        agent=agent,
        logger=types.SimpleNamespace(debug=lambda *a, **k: None, info=lambda *a, **k: None),
        get_tool_definitions_fn=lambda quiet_mode=False: new_tools,
        on_refreshed=lambda added, total: callback_calls.append((added, total)),
    )

    assert "new_tool" in agent.valid_tool_names
    assert len(agent.tools) == 2
    assert callback_calls == [(1, 2)]


def test_late_refresh_inline_no_new_tools():
    """When no new tools appeared, agent is not modified."""
    agent = _FakeAgent(tools=[_make_tool_def("a")], valid_tool_names={"a"})
    original_tools = agent.tools

    mcp_startup._mcp_discovery_thread = None

    mcp_startup.spawn_late_mcp_refresh(
        agent=agent,
        logger=types.SimpleNamespace(debug=lambda *a, **k: None, info=lambda *a, **k: None),
        get_tool_definitions_fn=lambda quiet_mode=False: [_make_tool_def("a")],
    )

    assert agent.tools is original_tools  # not replaced


def test_late_refresh_background_thread_adds_tools():
    """When discovery is still running, a background thread waits and refreshes."""
    stop = threading.Event()

    def _slow_discover():
        stop.wait(timeout=5)

    discover_thread = threading.Thread(target=_slow_discover, daemon=True)
    discover_thread.start()
    mcp_startup._mcp_discovery_thread = discover_thread

    agent = _FakeAgent(tools=[_make_tool_def("existing")], valid_tool_names={"existing"})
    new_tools = [_make_tool_def("existing"), _make_tool_def("slow_tool")]
    callback_calls = []
    logged = []

    def _log_info(msg, *args):
        logged.append(msg % args if args else msg)

    mcp_startup.spawn_late_mcp_refresh(
        agent=agent,
        logger=types.SimpleNamespace(
            debug=lambda *a, **k: None,
            info=_log_info,
        ),
        get_tool_definitions_fn=lambda quiet_mode=False: new_tools,
        on_refreshed=lambda added, total: callback_calls.append((added, total)),
    )

    assert mcp_startup._mcp_late_refresh_thread is not None

    # Let discovery finish
    stop.set()
    mcp_startup._mcp_late_refresh_thread.join(timeout=5)

    assert "slow_tool" in agent.valid_tool_names
    assert len(agent.tools) == 2
    assert callback_calls == [(1, 2)]
    assert any("slow_tool" in msg for msg in logged)


def test_late_refresh_no_duplicate_threads():
    """Calling spawn_late_mcp_refresh twice only creates one thread."""
    stop = threading.Event()

    def _slow_discover():
        stop.wait(timeout=5)

    discover_thread = threading.Thread(target=_slow_discover, daemon=True)
    discover_thread.start()
    mcp_startup._mcp_discovery_thread = discover_thread

    agent = _FakeAgent()

    mcp_startup.spawn_late_mcp_refresh(
        agent=agent,
        logger=types.SimpleNamespace(debug=lambda *a, **k: None, info=lambda *a, **k: None),
        get_tool_definitions_fn=lambda quiet_mode=False: [],
    )
    first_thread = mcp_startup._mcp_late_refresh_thread

    mcp_startup.spawn_late_mcp_refresh(
        agent=agent,
        logger=types.SimpleNamespace(debug=lambda *a, **k: None, info=lambda *a, **k: None),
        get_tool_definitions_fn=lambda quiet_mode=False: [],
    )
    second_thread = mcp_startup._mcp_late_refresh_thread

    assert first_thread is second_thread

    stop.set()
    first_thread.join(timeout=5)


def test_late_refresh_background_timeout_skips():
    """If discovery hangs beyond timeout, late refresh gives up."""
    def _hang_forever():
        time.sleep(999)

    discover_thread = threading.Thread(target=_hang_forever, daemon=True)
    discover_thread.start()
    mcp_startup._mcp_discovery_thread = discover_thread

    agent = _FakeAgent(tools=[_make_tool_def("a")], valid_tool_names={"a"})
    logged = []
    original_timeout = mcp_startup._LATE_REFRESH_DISCOVERY_TIMEOUT_S

    try:
        mcp_startup._LATE_REFRESH_DISCOVERY_TIMEOUT_S = 0.1  # 100ms for test speed

        mcp_startup.spawn_late_mcp_refresh(
            agent=agent,
            logger=types.SimpleNamespace(
                debug=lambda msg, *args: logged.append(msg % args if args else msg),
                info=lambda *a, **k: None,
            ),
            get_tool_definitions_fn=lambda quiet_mode=False: [_make_tool_def("a"), _make_tool_def("b")],
        )

        mcp_startup._mcp_late_refresh_thread.join(timeout=5)

        assert "b" not in agent.valid_tool_names  # not updated
        assert any("skipping late refresh" in msg for msg in logged)
    finally:
        mcp_startup._LATE_REFRESH_DISCOVERY_TIMEOUT_S = original_timeout


def test_late_refresh_callback_failure_is_swallowed():
    """If on_refreshed raises, it doesn't crash the refresh thread."""
    agent = _FakeAgent(tools=[_make_tool_def("old")], valid_tool_names={"old"})
    mcp_startup._mcp_discovery_thread = None

    def _bad_callback(added, total):
        raise RuntimeError("boom")

    # Should not raise
    mcp_startup.spawn_late_mcp_refresh(
        agent=agent,
        logger=types.SimpleNamespace(debug=lambda *a, **k: None, info=lambda *a, **k: None),
        get_tool_definitions_fn=lambda quiet_mode=False: [_make_tool_def("old"), _make_tool_def("new")],
        on_refreshed=_bad_callback,
    )

    assert "new" in agent.valid_tool_names
