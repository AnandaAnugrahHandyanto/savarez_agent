"""Tests for the dispatch_in_gateway gate on _kanban_notifier_watcher.

Acceptance criteria covered:
- Non-dispatch gateways (dispatch_in_gateway=false) exit before opening any DB.
- Dispatch-owning gateways (dispatch_in_gateway=true) proceed past the gate.
- HERMES_KANBAN_DISPATCH_IN_GATEWAY env var disables without config load.
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from gateway.run import GatewayRunner


def _make_runner():
    runner = GatewayRunner.__new__(GatewayRunner)
    runner._running = True
    runner.adapters = {}
    runner._kanban_sub_fail_counts = {}
    return runner


def _fake_config(dispatch_in_gateway):
    return {"kanban": {"dispatch_in_gateway": dispatch_in_gateway}}


def test_notifier_watcher_skips_when_dispatch_disabled(monkeypatch):
    """With dispatch_in_gateway=false the watcher returns before opening any DB."""
    runner = _make_runner()

    with patch("hermes_cli.config.load_config", return_value=_fake_config(False)):
        with patch("hermes_cli.kanban_db.connect") as mock_connect:
            asyncio.run(runner._kanban_notifier_watcher())
            mock_connect.assert_not_called()


def test_notifier_watcher_no_db_handle_on_non_dispatch_gateway(monkeypatch):
    """After early return, kanban_db.connect was never called (negative test)."""
    runner = _make_runner()

    with patch("hermes_cli.config.load_config", return_value=_fake_config(False)):
        with patch("hermes_cli.kanban_db.connect") as mock_connect:
            asyncio.run(runner._kanban_notifier_watcher())

    mock_connect.assert_not_called()


def test_notifier_watcher_env_override_disables(monkeypatch):
    """HERMES_KANBAN_DISPATCH_IN_GATEWAY=false skips config load entirely."""
    runner = _make_runner()
    monkeypatch.setenv("HERMES_KANBAN_DISPATCH_IN_GATEWAY", "false")

    with patch("hermes_cli.config.load_config") as mock_load_config:
        with patch("hermes_cli.kanban_db.connect") as mock_connect:
            asyncio.run(runner._kanban_notifier_watcher())

    mock_load_config.assert_not_called()
    mock_connect.assert_not_called()


def test_notifier_watcher_env_override_zero_disables(monkeypatch):
    """HERMES_KANBAN_DISPATCH_IN_GATEWAY=0 also disables."""
    runner = _make_runner()
    monkeypatch.setenv("HERMES_KANBAN_DISPATCH_IN_GATEWAY", "0")

    with patch("hermes_cli.config.load_config") as mock_load_config:
        asyncio.run(runner._kanban_notifier_watcher())

    mock_load_config.assert_not_called()


def test_notifier_watcher_runs_when_dispatch_enabled(monkeypatch, tmp_path):
    """With dispatch_in_gateway=true the watcher proceeds past the gate.

    We verify it doesn't return early by checking that kanban_db.list_boards
    is called (the watcher fan-outs over boards after passing the gate).
    """
    runner = _make_runner()
    past_gate = []
    sleep_calls = []

    async def fake_sleep(delay):
        sleep_calls.append(delay)
        # First sleep is the 5s initial delay; stop running so the loop exits cleanly
        # without needing a second sleep, but we need to let _collect run first.
        # We stop after the second sleep (the per-interval sleep inside the loop).
        if len(sleep_calls) >= 2:
            runner._running = False

    async def fake_to_thread(fn, *args, **kwargs):
        # Run sync function directly in-thread
        return fn(*args, **kwargs)

    import hermes_cli.kanban_db as _kb

    with patch("hermes_cli.config.load_config", return_value=_fake_config(True)):
        with patch.object(
            _kb,
            "list_boards",
            side_effect=lambda *a, **kw: past_gate.append(True) or [],
        ):
            with patch("asyncio.sleep", side_effect=fake_sleep):
                with patch("asyncio.to_thread", side_effect=fake_to_thread):
                    asyncio.run(runner._kanban_notifier_watcher())

    assert past_gate, "list_boards should be called when dispatch_in_gateway=true"
