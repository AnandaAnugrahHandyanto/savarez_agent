"""Tests for file-backed cron maintenance mode."""

from __future__ import annotations

import time
from datetime import timedelta

import pytest

from hermes_time import now as hermes_now


@pytest.fixture()
def maintenance_home(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    (home / "cron").mkdir(parents=True)
    monkeypatch.setenv("HERMES_HOME", str(home))
    return home


def test_start_status_stop_maintenance(maintenance_home):
    from cron.maintenance import (
        is_maintenance_active,
        maintenance_file,
        read_maintenance,
        start_maintenance,
        stop_maintenance,
    )

    until = (hermes_now() + timedelta(minutes=10)).isoformat()
    state = start_maintenance(until=until, reason="daily-maintenance", owner="pytest")

    assert maintenance_file().exists()
    assert state["reason"] == "daily-maintenance"
    loaded = read_maintenance()
    assert loaded is not None
    assert loaded["owner"] == "pytest"
    assert is_maintenance_active()
    assert stop_maintenance() is True
    assert not is_maintenance_active()


def test_expired_maintenance_is_inactive(maintenance_home):
    from cron.maintenance import is_maintenance_active, start_maintenance

    start_maintenance(until=(hermes_now() - timedelta(minutes=1)).isoformat())

    assert not is_maintenance_active()


def test_corrupt_maintenance_fails_closed(maintenance_home):
    from cron.maintenance import is_maintenance_active, maintenance_file, read_maintenance, MaintenanceStateError

    maintenance_file().write_text("{not-json", encoding="utf-8")

    assert is_maintenance_active()
    with pytest.raises(MaintenanceStateError):
        read_maintenance()


def test_record_running_job_lifecycle(maintenance_home):
    from cron.maintenance import list_running_jobs, record_job_finished, record_job_started, running_file

    record_job_started({"id": "job_1", "name": "Example", "schedule": {"value": "every 1h"}})

    jobs = list_running_jobs()
    assert [job["id"] for job in jobs] == ["job_1"]
    assert jobs[0]["name"] == "Example"
    assert running_file().exists()

    record_job_finished("job_1")

    assert list_running_jobs() == []
    assert not running_file().exists()


def test_drain_succeeds_when_empty_and_times_out_when_running(maintenance_home):
    from cron.maintenance import drain, record_job_started

    assert drain(timeout_seconds=0.1, poll_seconds=0.01)

    record_job_started({"id": "job_1", "name": "Long"})
    started = time.monotonic()

    assert not drain(timeout_seconds=0.05, poll_seconds=0.01)
    assert time.monotonic() - started >= 0.05


def test_tick_skips_due_jobs_during_maintenance(maintenance_home, monkeypatch):
    from cron.maintenance import start_maintenance
    from cron import scheduler

    start_maintenance(until=(hermes_now() + timedelta(minutes=5)).isoformat())

    def should_not_query_due_jobs():
        raise AssertionError("tick should not query due jobs during maintenance")

    monkeypatch.setattr(scheduler, "get_due_jobs", should_not_query_due_jobs)

    assert scheduler.tick(verbose=False, sync=True) == 0


def test_tick_records_running_jobs(maintenance_home, monkeypatch):
    from cron import scheduler
    from cron.maintenance import list_running_jobs

    seen_during_run = []
    job = {"id": "job_1", "name": "Tracked", "schedule": {"value": "every 1h"}}

    monkeypatch.setattr(scheduler, "get_due_jobs", lambda: [job])
    monkeypatch.setattr(scheduler, "advance_next_run", lambda job_id: None)
    monkeypatch.setattr(scheduler, "save_job_output", lambda job_id, output: maintenance_home / "cron" / "output.txt")
    monkeypatch.setattr(scheduler, "_deliver_result", lambda *args, **kwargs: None)
    monkeypatch.setattr(scheduler, "mark_job_run", lambda *args, **kwargs: None)
    monkeypatch.setattr(scheduler, "load_config", lambda: {"cron": {"max_parallel_jobs": 1}})

    def fake_run_job(running_job):
        seen_during_run.extend(job["id"] for job in list_running_jobs())
        return True, "output", "done", None

    monkeypatch.setattr(scheduler, "run_job", fake_run_job)

    assert scheduler.tick(verbose=False, sync=True) == 1
    assert seen_during_run == ["job_1"]
    assert list_running_jobs() == []
