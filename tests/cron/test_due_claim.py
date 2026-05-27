"""Durable due-claim behavior for the live cron scheduler."""

from __future__ import annotations

import importlib
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest


@pytest.fixture()
def cron_home(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    (home / "cron").mkdir(parents=True)
    monkeypatch.setenv("HERMES_HOME", str(home))
    import hermes_constants
    import cron.jobs
    import cron.scheduler

    importlib.reload(hermes_constants)
    importlib.reload(cron.jobs)
    importlib.reload(cron.scheduler)
    return home


def _freeze(monkeypatch, when: datetime):
    import cron.jobs as jobs
    import cron.scheduler as scheduler

    monkeypatch.setattr(jobs, "_hermes_now", lambda: when)
    monkeypatch.setattr(scheduler, "_hermes_now", lambda: when)


def test_claim_due_jobs_atomically_marks_and_advances_recurring_cron(cron_home, monkeypatch):
    """A live tick claims due jobs and advances recurring schedules before execution."""
    from cron.jobs import claim_due_jobs, create_job, get_job, update_job

    ny = ZoneInfo("America/New_York")
    created_at = datetime(2026, 5, 27, 8, 30, tzinfo=ny)
    due_at = datetime(2026, 5, 27, 9, 0, tzinfo=ny)
    tick_at = datetime(2026, 5, 27, 9, 1, tzinfo=ny)

    _freeze(monkeypatch, created_at)
    job = create_job(prompt="say hi", schedule="0 9 * * *", deliver="local")
    update_job(job["id"], {"next_run_at": due_at.isoformat()})

    _freeze(monkeypatch, tick_at)
    claimed = claim_due_jobs(owner_id="tick-1")

    assert [j["id"] for j in claimed] == [job["id"]]
    claimed_job = claimed[0]
    assert claimed_job["claimed_run_at"] == due_at.isoformat()
    assert claimed_job["claim"]["owner_id"] == "tick-1"

    stored = get_job(job["id"])
    assert stored["claim"]["owner_id"] == "tick-1"
    assert stored["claim"]["run_at"] == due_at.isoformat()
    assert stored["next_run_at"] == datetime(2026, 5, 28, 9, 0, tzinfo=ny).isoformat()

    # A second scheduler process must not see the same run while the lease is live.
    assert claim_due_jobs(owner_id="tick-2") == []


def test_claim_due_jobs_recovers_expired_claim_without_double_advancing(cron_home, monkeypatch):
    """Restart recovery reclaims expired leases using the original claimed run time."""
    from cron.jobs import claim_due_jobs, create_job, get_job, update_job

    utc = ZoneInfo("UTC")
    _freeze(monkeypatch, datetime(2026, 5, 27, 8, 0, tzinfo=utc))
    job = create_job(prompt="say hi", schedule="every 10m", deliver="local")

    due_at = datetime(2026, 5, 27, 9, 0, tzinfo=utc)
    update_job(
        job["id"],
        {
            "next_run_at": datetime(2026, 5, 27, 9, 10, tzinfo=utc).isoformat(),
            "claim": {
                "owner_id": "dead-process",
                "claimed_at": datetime(2026, 5, 27, 9, 0, tzinfo=utc).isoformat(),
                "expires_at": datetime(2026, 5, 27, 9, 5, tzinfo=utc).isoformat(),
                "run_at": due_at.isoformat(),
            },
        },
    )

    _freeze(monkeypatch, datetime(2026, 5, 27, 9, 6, tzinfo=utc))
    claimed = claim_due_jobs(owner_id="after-restart")

    assert [j["id"] for j in claimed] == [job["id"]]
    assert claimed[0]["claimed_run_at"] == due_at.isoformat()
    stored = get_job(job["id"])
    assert stored["claim"]["owner_id"] == "after-restart"
    assert stored["next_run_at"] == datetime(2026, 5, 27, 9, 10, tzinfo=utc).isoformat()


def test_claim_due_jobs_recovers_missing_recurring_next_run_at(cron_home, monkeypatch):
    """Jobs with missing next_run_at are repaired during claim-based live ticks."""
    from cron.jobs import claim_due_jobs, create_job, get_job, update_job

    utc = ZoneInfo("UTC")
    _freeze(monkeypatch, datetime(2026, 5, 27, 8, 0, tzinfo=utc))
    job = create_job(prompt="say hi", schedule="every 10m", deliver="local")
    update_job(job["id"], {"next_run_at": None})

    _freeze(monkeypatch, datetime(2026, 5, 27, 9, 0, tzinfo=utc))
    assert claim_due_jobs(owner_id="tick") == []

    stored = get_job(job["id"])
    assert stored is not None
    assert stored["next_run_at"] == datetime(2026, 5, 27, 9, 10, tzinfo=utc).isoformat()
    assert stored.get("claim") is None


def test_claim_due_jobs_marks_recurring_error_when_next_run_cannot_advance(cron_home, monkeypatch):
    """Recurring jobs fail closed if a due-claim cannot compute the following run."""
    from cron.jobs import claim_due_jobs, create_job, get_job, update_job
    import cron.jobs as jobs

    utc = ZoneInfo("UTC")
    _freeze(monkeypatch, datetime(2026, 5, 27, 8, 0, tzinfo=utc))
    job = create_job(prompt="say hi", schedule="every 10m", deliver="local")
    update_job(job["id"], {"next_run_at": datetime(2026, 5, 27, 9, 0, tzinfo=utc).isoformat()})
    monkeypatch.setattr(jobs, "_next_after_claimed_run", lambda *_args, **_kwargs: None)

    _freeze(monkeypatch, datetime(2026, 5, 27, 9, 1, tzinfo=utc))
    assert claim_due_jobs(owner_id="tick") == []

    stored = get_job(job["id"])
    assert stored is not None
    assert stored["state"] == "error"
    assert "Failed to compute next run" in stored["last_error"]
    assert stored.get("claim") is None


def test_mark_job_run_ignores_stale_completion_after_claim_reclaimed(cron_home, monkeypatch):
    """A runner whose lease expired must not clear a newer runner's live claim."""
    from cron.jobs import claim_due_jobs, create_job, get_job, mark_job_run, update_job

    utc = ZoneInfo("UTC")
    due_at = datetime(2026, 5, 27, 9, 0, tzinfo=utc)
    _freeze(monkeypatch, datetime(2026, 5, 27, 8, 0, tzinfo=utc))
    job = create_job(prompt="say hi", schedule="every 10m", deliver="local")
    update_job(job["id"], {"next_run_at": due_at.isoformat()})

    _freeze(monkeypatch, datetime(2026, 5, 27, 9, 1, tzinfo=utc))
    first = claim_due_jobs(owner_id="runner-1")[0]

    _freeze(monkeypatch, datetime(2026, 5, 27, 9, 7, tzinfo=utc))
    second = claim_due_jobs(owner_id="runner-2")[0]
    assert second["claim"]["owner_id"] == "runner-2"

    mark_job_run(
        job["id"],
        True,
        claim_owner_id=first["claim"]["owner_id"],
        claimed_run_at=first["claimed_run_at"],
    )

    stored = get_job(job["id"])
    assert stored is not None
    assert stored["claim"]["owner_id"] == "runner-2"
    assert stored["last_run_at"] is None


def test_tick_uses_due_claim_substrate_and_clears_claim_after_run(cron_home, monkeypatch):
    """scheduler.tick() executes claimed jobs and mark_job_run clears the durable lease."""
    from cron.jobs import create_job, get_job, update_job
    import cron.scheduler as scheduler

    utc = ZoneInfo("UTC")
    _freeze(monkeypatch, datetime(2026, 5, 27, 8, 0, tzinfo=utc))
    job = create_job(prompt="say hi", schedule="every 15m", deliver="local")
    update_job(job["id"], {"next_run_at": datetime(2026, 5, 27, 9, 0, tzinfo=utc).isoformat()})

    ran = []

    def fake_run_job(job_dict):
        ran.append(job_dict["claimed_run_at"])
        return True, "output", "final", None

    monkeypatch.setattr(scheduler, "run_job", fake_run_job)
    monkeypatch.setattr(scheduler, "save_job_output", lambda job_id, output: cron_home / "cron" / "output.md")
    monkeypatch.setattr(scheduler, "_deliver_result", lambda *a, **k: None)
    _freeze(monkeypatch, datetime(2026, 5, 27, 9, 1, tzinfo=utc))

    assert scheduler.tick(verbose=False) == 1
    assert ran == [datetime(2026, 5, 27, 9, 0, tzinfo=utc).isoformat()]
    stored = get_job(job["id"])
    assert stored.get("claim") is None
    assert stored["next_run_at"] == datetime(2026, 5, 27, 9, 15, tzinfo=utc).isoformat()


def test_claimed_one_shot_is_completed_after_successful_tick(cron_home, monkeypatch):
    from cron.jobs import create_job, get_job, update_job
    import cron.scheduler as scheduler

    utc = ZoneInfo("UTC")
    due_at = datetime(2026, 5, 27, 9, 0, tzinfo=utc)
    _freeze(monkeypatch, datetime(2026, 5, 27, 8, 0, tzinfo=utc))
    job = create_job(prompt="once", schedule="2026-05-27T09:00:00+00:00", deliver="local")
    update_job(job["id"], {"next_run_at": due_at.isoformat()})

    monkeypatch.setattr(scheduler, "run_job", lambda job_dict: (True, "output", "final", None))
    monkeypatch.setattr(scheduler, "save_job_output", lambda job_id, output: cron_home / "cron" / "output.md")
    monkeypatch.setattr(scheduler, "_deliver_result", lambda *a, **k: None)
    _freeze(monkeypatch, datetime(2026, 5, 27, 9, 1, tzinfo=utc))

    assert scheduler.tick(verbose=False) == 1
    assert get_job(job["id"]) is None
