"""Gateway cron ticker also launches due managed plugin callbacks."""

from __future__ import annotations

import threading


def test_cron_ticker_launches_due_plugin_tasks(monkeypatch):
    from cron import scheduler
    from gateway import run
    from hermes_cli import plugins

    stop = threading.Event()
    calls = []

    def _cron_tick(**_):
        calls.append("cron")
        stop.set()

    def _plugin_tick(**_):
        calls.append("plugins")
        return []

    monkeypatch.setattr(scheduler, "tick", _cron_tick)
    monkeypatch.setattr(plugins, "run_due_plugin_periodic_tasks", _plugin_tick)

    run._start_cron_ticker(stop, interval=0)

    assert calls == ["cron", "plugins"]
