"""Tests for managed plugin periodic task registration and execution."""

from __future__ import annotations

import threading
import time

import pytest

from hermes_cli.plugins import (
    PeriodicTaskSpec,
    PluginContext,
    PluginManager,
    PluginManifest,
    get_due_plugin_periodic_tasks,
    get_plugin_periodic_tasks,
    run_due_plugin_periodic_tasks,
    run_plugin_periodic_task_once,
)


def _make_ctx(name: str = "test_plugin") -> tuple[PluginContext, PluginManager]:
    manager = PluginManager()
    manager._discovered = True
    manifest = PluginManifest(name=name)
    return PluginContext(manifest, manager), manager


def test_register_periodic_task_basic_and_due_lookup():
    ctx, manager = _make_ctx("plug_a")
    ctx.register_periodic_task(
        PeriodicTaskSpec(name="hb", interval_seconds=30, run_immediately=True),
        callback=lambda: None,
    )

    listing = manager.list_periodic_tasks()
    assert [item["name"] for item in listing] == ["hb"]
    assert listing[0]["plugin"] == "plug_a"
    now = time.monotonic()
    assert manager.get_due_periodic_task_names(now_monotonic=now + 1.0) == ["hb"]


def test_register_periodic_task_rejects_duplicate_name_across_plugins():
    manager = PluginManager()
    manager._discovered = True
    ctx_a = PluginContext(PluginManifest(name="plug_a"), manager)
    ctx_b = PluginContext(PluginManifest(name="plug_b"), manager)

    ctx_a.register_periodic_task(
        PeriodicTaskSpec(name="shared", interval_seconds=60),
        callback=lambda: None,
    )
    with pytest.raises(ValueError, match="already registered by plugin 'plug_a'"):
        ctx_b.register_periodic_task(
            PeriodicTaskSpec(name="shared", interval_seconds=60),
            callback=lambda: None,
        )


def test_periodic_task_defaults_to_no_overlap():
    ctx, manager = _make_ctx()
    blocker = threading.Event()

    def _callback():
        blocker.wait(timeout=2.0)

    ctx.register_periodic_task(
        PeriodicTaskSpec(name="serial_task", interval_seconds=1, run_immediately=True),
        callback=_callback,
    )
    try:
        now = time.monotonic()
        first = manager.run_due_periodic_tasks(now_monotonic=now + 1.0)
        second = manager.run_due_periodic_tasks(now_monotonic=now + 2.0)
        assert first == ["serial_task"]
        assert second == []
    finally:
        blocker.set()
        manager.shutdown_periodic_tasks(grace_seconds=1.0)


def test_periodic_task_can_allow_overlap():
    ctx, manager = _make_ctx()
    blocker = threading.Event()

    def _callback():
        blocker.wait(timeout=2.0)

    ctx.register_periodic_task(
        PeriodicTaskSpec(
            name="overlap_task",
            interval_seconds=1,
            run_immediately=True,
            allow_overlap=True,
        ),
        callback=_callback,
    )
    try:
        now = time.monotonic()
        first = manager.run_due_periodic_tasks(now_monotonic=now + 1.0)
        second = manager.run_due_periodic_tasks(now_monotonic=now + 3.0)
        assert first == ["overlap_task"]
        assert second == ["overlap_task"]
    finally:
        blocker.set()
        manager.shutdown_periodic_tasks(grace_seconds=1.0)


def test_periodic_task_exceptions_are_isolated():
    ctx, manager = _make_ctx()

    ctx.register_periodic_task(
        PeriodicTaskSpec(name="boom_task", interval_seconds=30, run_immediately=True),
        callback=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    result = manager.run_periodic_task_once("boom_task", now_monotonic=123.0)

    assert result.started is True
    assert result.success is False
    assert result.error == "boom"
    listing = manager.list_periodic_tasks()
    assert listing[0]["total_failures"] == 1
    assert listing[0]["in_flight"] == 0
    assert listing[0]["last_error"] == "boom"


def test_periodic_task_jitter_applies_to_next_schedule(monkeypatch):
    ctx, manager = _make_ctx()
    monkeypatch.setattr(manager, "_periodic_jitter", lambda spec: 1.5)

    ctx.register_periodic_task(
        PeriodicTaskSpec(name="jit", interval_seconds=5, jitter_seconds=2),
        callback=lambda: None,
    )
    result = manager.run_periodic_task_once("jit", now_monotonic=500.0)
    assert result.success is True

    info = manager.list_periodic_tasks()[0]
    delta = info["next_run_at"] - info["last_finished_at"]
    assert delta == pytest.approx(6.5)


def test_shutdown_stops_new_runs_and_returns_bounded_status():
    ctx, manager = _make_ctx()
    blocker = threading.Event()

    def _callback():
        blocker.wait(timeout=2.0)

    ctx.register_periodic_task(
        PeriodicTaskSpec(name="shutdown_task", interval_seconds=1, run_immediately=True),
        callback=_callback,
    )
    now = time.monotonic()
    started = manager.run_due_periodic_tasks(now_monotonic=now + 1.0)
    assert started == ["shutdown_task"]

    status = manager.shutdown_periodic_tasks(grace_seconds=0.01)
    assert status["total_threads"] >= 1
    assert status["alive_threads"] >= 1
    assert manager.run_due_periodic_tasks(now_monotonic=now + 2.0) == []

    skipped = manager.run_periodic_task_once("shutdown_task", now_monotonic=now + 2.0)
    assert skipped.started is False
    assert skipped.skipped_reason == "shutdown"

    blocker.set()
    manager.shutdown_periodic_tasks(grace_seconds=1.0)


def test_module_level_periodic_helpers_use_manager(monkeypatch):
    ctx, manager = _make_ctx("plug_x")
    blocker = threading.Event()

    ctx.register_periodic_task(
        PeriodicTaskSpec(name="helper_task", interval_seconds=2, run_immediately=True),
        callback=lambda: blocker.wait(timeout=2.0),
    )

    from hermes_cli import plugins as plugins_mod

    monkeypatch.setattr(plugins_mod, "_ensure_plugins_discovered", lambda force=False: manager)
    monkeypatch.setattr(plugins_mod, "get_plugin_manager", lambda: manager)

    now = time.monotonic()
    assert get_due_plugin_periodic_tasks(now_monotonic=now + 1.0) == ["helper_task"]
    assert run_due_plugin_periodic_tasks(now_monotonic=now + 1.0) == ["helper_task"]

    one_shot = run_plugin_periodic_task_once("helper_task", now_monotonic=now + 1.0)
    assert one_shot.started is False
    assert one_shot.skipped_reason == "in_flight"

    blocker.set()
    manager.shutdown_periodic_tasks(grace_seconds=1.0)
    tasks = get_plugin_periodic_tasks()
    assert [t["name"] for t in tasks] == ["helper_task"]
