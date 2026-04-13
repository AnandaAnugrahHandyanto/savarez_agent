"""F-007 regression tests: jobs whose next_run_at cannot be computed must
be marked as error-state (not silently skipped forever) and must remain
visible in the default `hermes cron list` output so the operator can fix
them.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@pytest.fixture
def cron_env(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    (hermes_home / "cron").mkdir()
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    import cron.jobs as jobs_mod
    monkeypatch.setattr(jobs_mod, "HERMES_DIR", hermes_home)
    monkeypatch.setattr(jobs_mod, "CRON_DIR", hermes_home / "cron")
    monkeypatch.setattr(jobs_mod, "JOBS_FILE", hermes_home / "cron" / "jobs.json")
    monkeypatch.setattr(jobs_mod, "OUTPUT_DIR", hermes_home / "cron" / "output")

    return hermes_home


class TestNullNextRunAtErrorState:
    def test_cron_job_with_uncomputable_next_run_is_error_state(self, cron_env):
        """When compute_next_run returns None for a cron job, the job must
        be disabled AND marked state=error with an error_reason — not
        silently skipped."""
        from cron.jobs import get_due_jobs, save_jobs

        # Hand-craft a job with null next_run_at and a schedule whose
        # compute_next_run we force to None.
        job = {
            "id": "broken-1",
            "name": "broken daily",
            "prompt": "do thing",
            "schedule": {"kind": "cron", "expr": "0 9 * * *"},
            "schedule_display": "0 9 * * *",
            "enabled": True,
            "state": "scheduled",
            "next_run_at": None,
            "created_at": "2026-01-01T00:00:00+05:30",
        }
        save_jobs([job])

        with patch("cron.jobs.compute_next_run", return_value=None):
            due = get_due_jobs()

        # The broken job must not be in the due list (it can't run).
        assert all(j["id"] != "broken-1" for j in due), "broken job must not fire"

        # But it MUST have been persisted as error-state.
        from cron.jobs import get_job
        persisted = get_job("broken-1")
        assert persisted is not None
        assert persisted["enabled"] is False
        assert persisted["state"] == "error"
        assert "error_reason" in persisted
        assert "compute_next_run returned None" in persisted["error_reason"]

    def test_error_state_job_visible_in_default_list(self, cron_env):
        """Default list (include_disabled=False) must still show error-state
        jobs so the operator can see and fix them."""
        from cron.jobs import list_jobs, save_jobs

        save_jobs([
            {
                "id": "broken-2",
                "name": "broken",
                "prompt": "x",
                "schedule": {"kind": "cron", "expr": "0 9 * * *"},
                "schedule_display": "0 9 * * *",
                "enabled": False,  # auto-disabled
                "state": "error",
                "error_reason": "compute_next_run returned None",
                "created_at": "2026-01-01T00:00:00+05:30",
            },
            {
                "id": "normal-disabled",
                "name": "user-paused",
                "prompt": "x",
                "schedule": {"kind": "cron", "expr": "0 9 * * *"},
                "schedule_display": "0 9 * * *",
                "enabled": False,
                "state": "paused",
                "created_at": "2026-01-01T00:00:00+05:30",
            },
        ])

        listed = list_jobs(include_disabled=False)
        ids = {j["id"] for j in listed}
        assert "broken-2" in ids, "error-state job must be visible by default"
        assert "normal-disabled" not in ids, (
            "user-disabled/paused jobs are still hidden by default"
        )
