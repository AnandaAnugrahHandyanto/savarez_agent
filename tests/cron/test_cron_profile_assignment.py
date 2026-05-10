"""Tests for global cron per-job profile assignment."""

from __future__ import annotations

import importlib
import os
from pathlib import Path

import pytest


@pytest.fixture
def root_with_profiles(tmp_path, monkeypatch):
    """Use a synthetic Hermes root with a global home plus named profiles."""
    root = tmp_path / ".hermes"
    root.mkdir()
    (root / "cron").mkdir()
    (root / "scripts").mkdir()
    profiles = root / "profiles"
    profiles.mkdir()
    for name in ("dev", "nova"):
        home = profiles / name
        (home / "cron").mkdir(parents=True)
        (home / "scripts").mkdir()
        (home / "skills").mkdir()

    monkeypatch.setenv("HERMES_HOME", str(root))

    import hermes_constants
    importlib.reload(hermes_constants)
    import cron.jobs
    importlib.reload(cron.jobs)
    import cron.scheduler
    importlib.reload(cron.scheduler)

    return root


def test_create_job_stores_canonical_profile(root_with_profiles):
    from cron.jobs import create_job, get_job

    job = create_job(
        prompt="say hi",
        schedule="every 5m",
        deliver="local",
        profile="dev",
    )

    assert job["profile"] == "dev"
    assert get_job(job["id"])["profile"] == "dev"


def test_create_job_rejects_profile_path_escape(root_with_profiles):
    from cron.jobs import create_job

    with pytest.raises(ValueError, match="simple profile name|unsupported characters"):
        create_job(
            prompt="say hi",
            schedule="every 5m",
            deliver="local",
            profile="../dev",
        )


def test_run_job_no_agent_uses_assigned_profile_home_and_restores_env(root_with_profiles):
    from cron.jobs import create_job
    from cron.scheduler import run_job

    global_script = root_with_profiles / "scripts" / "whoami.sh"
    global_script.write_text("#!/bin/bash\necho global\n")
    profile_script = root_with_profiles / "profiles" / "dev" / "scripts" / "whoami.sh"
    profile_script.write_text("#!/bin/bash\nprintf 'home=%s\\n' \"$HERMES_HOME\"\n")

    original_home = os.environ["HERMES_HOME"]
    job = create_job(
        prompt=None,
        schedule="every 5m",
        script="whoami.sh",
        no_agent=True,
        deliver="local",
        profile="dev",
    )

    success, doc, final_response, error = run_job(job)

    assert success is True
    assert error is None
    assert str(root_with_profiles / "profiles" / "dev") in final_response
    assert "global" not in final_response
    assert os.environ["HERMES_HOME"] == original_home


def test_tick_serializes_profile_jobs_and_leaves_plain_jobs_parallel(root_with_profiles):
    from cron.scheduler import _job_profile_name

    assert _job_profile_name({"profile": "nova"}) == "nova"
    assert _job_profile_name({"agent_id": "dev"}) == "dev"
    assert _job_profile_name({}) == ""
