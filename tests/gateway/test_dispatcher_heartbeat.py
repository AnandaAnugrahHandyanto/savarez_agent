"""Tests for the kanban dispatcher heartbeat written by gateway.run.GatewayRunner.

The heartbeat is a stable contract for external observers (monitoring scripts,
future `hermes gateway status` integration). These tests pin the schema so
silent contract breaks fail loudly.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def runner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Construct a minimal GatewayRunner with a tmp HERMES_HOME."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    # Importing run.py is heavy (loads adapters); import here so the fixture
    # picks up the env override.
    from gateway import run as gateway_run

    # Reload module so the module-level _hermes_home picks up our tmp path.
    import importlib

    importlib.reload(gateway_run)

    instance = gateway_run.GatewayRunner.__new__(gateway_run.GatewayRunner)
    return instance, gateway_run, tmp_path


def test_heartbeat_writes_expected_schema_v1(runner) -> None:
    instance, _gateway_run, tmp_path = runner
    hb_path = tmp_path / "state" / "dispatcher_health.json"

    instance._write_dispatcher_heartbeat(
        heartbeat_path=hb_path,
        interval=60.0,
        cycles_since_start=5,
        cycle_started_at=1_780_000_000.0,
        any_spawned=True,
        spawned_total=3,
        ready_pending=False,
        bad_ticks=0,
        cycle_error=None,
    )

    assert hb_path.exists(), "heartbeat file should exist after write"
    data = json.loads(hb_path.read_text())

    # Schema-v1 required keys — any missing key = silent contract break.
    required = {
        "schema_version",
        "last_cycle_ts",
        "last_cycle_iso",
        "cycle_started_at",
        "cycle_duration_seconds",
        "interval_seconds",
        "cycles_since_start",
        "any_spawned_this_cycle",
        "spawned_total_this_cycle",
        "ready_pending",
        "consecutive_bad_ticks",
        "gateway_pid",
        "cycle_error",
    }
    assert required <= set(data.keys()), f"missing keys: {required - set(data.keys())}"

    # Type checks (catches refactors that change shape).
    assert data["schema_version"] == 1
    assert isinstance(data["last_cycle_ts"], (int, float))
    assert data["last_cycle_iso"].endswith("Z"), "iso should be UTC with Z suffix"
    assert data["interval_seconds"] == 60.0
    assert data["cycles_since_start"] == 5
    assert data["any_spawned_this_cycle"] is True
    assert data["spawned_total_this_cycle"] == 3
    assert data["ready_pending"] is False
    assert data["consecutive_bad_ticks"] == 0
    assert data["gateway_pid"] == os.getpid()
    assert data["cycle_error"] is None


def test_heartbeat_records_cycle_error(runner) -> None:
    instance, _gateway_run, tmp_path = runner
    hb_path = tmp_path / "state" / "dispatcher_health.json"

    instance._write_dispatcher_heartbeat(
        heartbeat_path=hb_path,
        interval=60.0,
        cycles_since_start=1,
        cycle_started_at=1_780_000_000.0,
        any_spawned=False,
        spawned_total=0,
        ready_pending=True,
        bad_ticks=2,
        cycle_error="RuntimeError: simulated provider auth crash",
    )

    data = json.loads(hb_path.read_text())
    assert data["cycle_error"] == "RuntimeError: simulated provider auth crash"
    assert data["consecutive_bad_ticks"] == 2
    assert data["any_spawned_this_cycle"] is False
    assert data["ready_pending"] is True


def test_heartbeat_overwrites_previous_atomic(runner) -> None:
    """Second write must replace the first, not append."""
    instance, _gateway_run, tmp_path = runner
    hb_path = tmp_path / "state" / "dispatcher_health.json"

    instance._write_dispatcher_heartbeat(
        heartbeat_path=hb_path,
        interval=60.0,
        cycles_since_start=1,
        cycle_started_at=1_780_000_000.0,
        any_spawned=False,
        spawned_total=0,
        ready_pending=False,
        bad_ticks=0,
        cycle_error=None,
    )
    instance._write_dispatcher_heartbeat(
        heartbeat_path=hb_path,
        interval=60.0,
        cycles_since_start=2,
        cycle_started_at=1_780_000_060.0,
        any_spawned=True,
        spawned_total=1,
        ready_pending=False,
        bad_ticks=0,
        cycle_error=None,
    )

    data = json.loads(hb_path.read_text())
    assert data["cycles_since_start"] == 2, "second write should replace first"
    assert data["any_spawned_this_cycle"] is True


def test_heartbeat_counter_starts_at_one_first_cycle(runner) -> None:
    """Contract pinned: the dispatcher's watcher increments cycles_since_start
    BEFORE the first cycle body runs, so the first heartbeat shows 1, not 0.
    Monitors should expect the smallest valid value to be 1; 0 means "never wrote."
    """
    instance, _gateway_run, tmp_path = runner
    hb_path = tmp_path / "state" / "dispatcher_health.json"

    # Simulate what the watcher does at the very first iteration.
    instance._write_dispatcher_heartbeat(
        heartbeat_path=hb_path,
        interval=60.0,
        cycles_since_start=1,  # ← contract: first cycle is 1
        cycle_started_at=1_780_000_000.0,
        any_spawned=False,
        spawned_total=0,
        ready_pending=False,
        bad_ticks=0,
        cycle_error=None,
    )

    data = json.loads(hb_path.read_text())
    assert data["cycles_since_start"] == 1, (
        "first heartbeat must report cycles_since_start=1 — monitors treat 0 as 'never wrote'"
    )


def test_heartbeat_creates_parent_state_dir_if_missing(runner) -> None:
    """state/ subdir may not exist on first gateway run — atomic_json_write should mkdir."""
    instance, _gateway_run, tmp_path = runner
    hb_path = tmp_path / "state" / "deep" / "nested" / "dispatcher_health.json"
    assert not hb_path.parent.exists()

    instance._write_dispatcher_heartbeat(
        heartbeat_path=hb_path,
        interval=60.0,
        cycles_since_start=1,
        cycle_started_at=1_780_000_000.0,
        any_spawned=False,
        spawned_total=0,
        ready_pending=False,
        bad_ticks=0,
        cycle_error=None,
    )

    assert hb_path.exists()
