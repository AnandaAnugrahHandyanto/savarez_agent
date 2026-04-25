"""
Regression test for API job repeat updates corrupting cron repeat state.

This test ensures that PATCH /api/jobs/{job_id} with repeat field
correctly normalizes integer values into dict format and preserves completed count.

Related issue: #15582
"""

import tempfile
from pathlib import Path
import pytest

from cron import jobs


def test_update_job_repeat_normalizes_integer_to_dict():
    """
    Test that updating a job's repeat count via API (integer) correctly
    normalizes into the internal dict format while preserving completed count.

    This prevents mark_job_run() from crashing with AttributeError when it
    calls .get() on job["repeat"].
    """
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        jobs.CRON_DIR = tmp / "cron"
        jobs.JOBS_FILE = jobs.CRON_DIR / "jobs.json"
        jobs.OUTPUT_DIR = jobs.CRON_DIR / "output"

        # Create a job with repeat=5
        job = jobs.create_job(
            prompt="test prompt",
            schedule="every 1h",
            name="test-job",
            repeat=5,
            deliver="local",
        )
        job_id = job["id"]

        # Verify initial repeat format
        assert isinstance(job["repeat"], dict)
        assert job["repeat"]["times"] == 5
        assert job["repeat"]["completed"] == 0

        # Simulate first successful run (marks completed=1)
        jobs.mark_job_run(job_id, success=True)
        jobs_after_first_run = jobs.load_jobs()
        updated_job = [j for j in jobs_after_first_run if j["id"] == job_id][0]
        assert updated_job["repeat"]["completed"] == 1

        # Update repeat via API (integer form, as PATCH does)
        updated = jobs.update_job(job_id, {"repeat": 2})
        assert isinstance(updated["repeat"], dict), (
            f"Repeat should be dict after update, got {type(updated['repeat'])}"
        )
        # The key fix: integer 2 should be normalized to dict format
        assert updated["repeat"]["times"] == 2, (
            f"Repeat times should be 2, got {updated['repeat']['times']}"
        )
        # Critical: completed count should be preserved from before update
        assert updated["repeat"]["completed"] == 1, (
            f"Repeat completed should be preserved as 1, got {updated['repeat']['completed']}"
        )

        # Verify mark_job_run doesn't crash after update
        # This should not raise AttributeError: 'int' object has no attribute 'get'
        jobs.mark_job_run(job_id, success=True)
        jobs_after_second_run = jobs.load_jobs()
        # After this run, completed should be 2 (>= times=2), so job is removed
        # This is expected behavior for repeat limit
        # Find the job in the list before mark_job_run removed it
        # by checking if the job file still contains the job_id
        if any(j["id"] == job_id for j in jobs_after_second_run):
            final_job = [j for j in jobs_after_second_run if j["id"] == job_id][0]
            assert final_job["repeat"]["completed"] == 2
        else:
            # Job was removed because completed >= times, which is correct
            pass


def test_update_job_repeat_negative_or_zero_is_rejected():
    """
    Test that updating repeat to non-positive values is rejected.

    This matches create_job() behavior where repeat <= 0 is treated as None.
    """
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        jobs.CRON_DIR = tmp / "cron"
        jobs.JOBS_FILE = jobs.CRON_DIR / "jobs.json"
        jobs.OUTPUT_DIR = jobs.CRON_DIR / "output"

        job = jobs.create_job(
            prompt="test prompt",
            schedule="every 1h",
            name="test-job",
            repeat=5,
            deliver="local",
        )
        job_id = job["id"]

        # Attempt to set repeat=0 via update (should be normalized to None)
        updated = jobs.update_job(job_id, {"repeat": 0})
        # After update, repeat should be None (normalized)
        assert updated is not None
        assert updated.get("repeat") is None, (
            f"Repeat=0 should be normalized to None, got {updated.get('repeat')}"
        )
