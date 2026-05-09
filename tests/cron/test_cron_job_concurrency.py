"""Tests for concurrent access safety in cron job CRUD operations.

Regression test for #22761: mass cron job model/provider field corruption
during rapid updates. The fix adds _jobs_file_lock to update_job(),
create_job(), and remove_job() so they serialize with the scheduler's
mark_job_run() / advance_next_run() / get_due_jobs() calls.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest


@pytest.fixture()
def tmp_cron_dir(tmp_path, monkeypatch):
    """Isolate cron job storage into a temp dir so tests don't stomp on real jobs."""
    monkeypatch.setattr("cron.jobs.CRON_DIR", tmp_path / "cron")
    monkeypatch.setattr("cron.jobs.JOBS_FILE", tmp_path / "cron" / "jobs.json")
    monkeypatch.setattr("cron.jobs.OUTPUT_DIR", tmp_path / "cron" / "output")
    return tmp_path


def _create_test_job(tmp_cron_dir, job_id="test-job-1", model="gpt-5.5", provider="openai-codex"):
    """Helper: create a job with known model/provider fields."""
    from cron.jobs import create_job
    job = create_job(
        prompt="test prompt",
        schedule="every 10m",
        name="test job",
        model=model,
        provider=provider,
    )
    return job


class TestConcurrentUpdateSafety:
    """Verify that concurrent update_job() calls don't corrupt other jobs."""

    def test_rapid_updates_preserve_model_provider(self, tmp_cron_dir):
        """Multiple rapid sequential updates to one job must not null out
        model/provider on that job or any other job in the store."""
        from cron.jobs import create_job, get_job, update_job

        # Create 5 jobs with distinct model/provider values
        job_ids = []
        for i in range(5):
            job = create_job(
                prompt=f"job {i} prompt",
                schedule="every 10m",
                name=f"job-{i}",
                model=f"model-{i}",
                provider=f"provider-{i}",
            )
            job_ids.append(job["id"])

        # Rapid sequential updates to job 0 — different field combos,
        # never touching model/provider
        for field_update in [
            {"skills": ["skill-a"]},
            {"enabled_toolsets": ["terminal", "file"]},
            {"prompt": "updated prompt"},
            {"skills": ["skill-b"], "enabled_toolsets": ["terminal"]},
        ]:
            update_job(job_ids[0], field_update)

        # Verify all jobs retain their original model/provider
        for i, jid in enumerate(job_ids):
            job = get_job(jid)
            assert job is not None, f"Job {jid} disappeared"
            assert job["model"] == f"model-{i}", (
                f"Job {jid} model corrupted: expected 'model-{i}', got '{job['model']}'"
            )
            assert job["provider"] == f"provider-{i}", (
                f"Job {jid} provider corrupted: expected 'provider-{i}', got '{job['provider']}'"
            )

    def test_concurrent_thread_updates_no_corruption(self, tmp_cron_dir):
        """Concurrent threads updating different jobs must not corrupt each other."""
        from cron.jobs import create_job, get_job, update_job

        # Create 10 jobs
        job_ids = []
        for i in range(10):
            job = create_job(
                prompt=f"job {i}",
                schedule="every 10m",
                name=f"job-{i}",
                model=f"model-{i}",
                provider=f"provider-{i}",
            )
            job_ids.append(job["id"])

        errors = []

        def update_job_thread(idx):
            try:
                for _ in range(5):
                    update_job(job_ids[idx], {"prompt": f"updated-{idx}"})
            except Exception as e:
                errors.append(e)

        # Launch concurrent updaters
        threads = [threading.Thread(target=update_job_thread, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert not errors, f"Concurrent updates raised errors: {errors}"

        # Verify no corruption
        for i, jid in enumerate(job_ids):
            job = get_job(jid)
            assert job is not None, f"Job {jid} disappeared after concurrent updates"
            assert job["model"] == f"model-{i}", (
                f"Job {jid} model corrupted: expected 'model-{i}', got '{job['model']}'"
            )
            assert job["provider"] == f"provider-{i}", (
                f"Job {jid} provider corrupted: expected 'provider-{i}', got '{job['provider']}'"
            )

    def test_concurrent_create_and_update_no_corruption(self, tmp_cron_dir):
        """Concurrent create and update operations must not corrupt existing jobs."""
        from cron.jobs import create_job, get_job, update_job

        # Pre-create some jobs
        existing_ids = []
        for i in range(5):
            job = create_job(
                prompt=f"existing-{i}",
                schedule="every 10m",
                name=f"existing-{i}",
                model=f"model-{i}",
                provider=f"provider-{i}",
            )
            existing_ids.append(job["id"])

        errors = []
        new_ids = []

        def creator():
            try:
                for i in range(5):
                    job = create_job(
                        prompt=f"new-{i}",
                        schedule="every 10m",
                        name=f"new-{i}",
                        model=f"new-model-{i}",
                        provider=f"new-provider-{i}",
                    )
                    new_ids.append(job["id"])
            except Exception as e:
                errors.append(e)

        def updater():
            try:
                for jid in existing_ids:
                    update_job(jid, {"prompt": "concurrently-updated"})
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=creator)
        t2 = threading.Thread(target=updater)
        t1.start()
        t2.start()
        t1.join(timeout=30)
        t2.join(timeout=30)

        assert not errors, f"Concurrent operations raised errors: {errors}"

        # Verify existing jobs are intact
        for i, jid in enumerate(existing_ids):
            job = get_job(jid)
            assert job is not None, f"Existing job {jid} disappeared"
            assert job["model"] == f"model-{i}", (
                f"Existing job {jid} model corrupted: expected 'model-{i}', got '{job['model']}'"
            )
            assert job["provider"] == f"provider-{i}", (
                f"Existing job {jid} provider corrupted: expected 'provider-{i}', got '{job['provider']}'"
            )


class TestCreateJobLocking:
    """Verify create_job() is safe under concurrent access."""

    def test_create_job_serialized(self, tmp_cron_dir):
        """Concurrent create_job() calls must not corrupt the job list."""
        from cron.jobs import create_job, list_jobs

        errors = []
        created = []

        def creator(idx):
            try:
                for i in range(3):
                    job = create_job(
                        prompt=f"concurrent-{idx}-{i}",
                        schedule="every 10m",
                        name=f"job-{idx}-{i}",
                        model=f"model-{idx}-{i}",
                        provider=f"provider-{idx}-{i}",
                    )
                    created.append(job["id"])
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=creator, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert not errors, f"Concurrent create_job raised errors: {errors}"
        assert len(created) == 15, f"Expected 15 jobs created, got {len(created)}"

        # All jobs must be present and have correct fields
        all_jobs = list_jobs(include_disabled=True)
        assert len(all_jobs) == 15, f"Expected 15 jobs in store, got {len(all_jobs)}"
        for job in all_jobs:
            assert job["model"] is not None, f"Job {job['id']} has null model"
            assert job["provider"] is not None, f"Job {job['id']} has null provider"


class TestRemoveJobLocking:
    """Verify remove_job() is safe under concurrent access."""

    def test_remove_job_serialized(self, tmp_cron_dir):
        """Concurrent remove_job() calls must not corrupt the job list."""
        from cron.jobs import create_job, list_jobs, remove_job

        # Create 10 jobs
        job_ids = []
        for i in range(10):
            job = create_job(
                prompt=f"to-remove-{i}",
                schedule="every 10m",
                name=f"remove-{i}",
            )
            job_ids.append(job["id"])

        errors = []

        def remover(jid):
            try:
                remove_job(jid)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=remover, args=(jid,)) for jid in job_ids]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert not errors, f"Concurrent remove_job raised errors: {errors}"

        all_jobs = list_jobs(include_disabled=True)
        assert len(all_jobs) == 0, f"Expected 0 jobs after removing all, got {len(all_jobs)}"
