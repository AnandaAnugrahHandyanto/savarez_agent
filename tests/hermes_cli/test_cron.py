"""Tests for hermes_cli.cron command handling."""

from argparse import Namespace

import pytest

from cli import HermesCLI
from cron.jobs import create_job, get_job, list_jobs
from hermes_cli.cron import cron_command


@pytest.fixture()
def tmp_cron_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("cron.jobs.CRON_DIR", tmp_path / "cron")
    monkeypatch.setattr("cron.jobs.JOBS_FILE", tmp_path / "cron" / "jobs.json")
    monkeypatch.setattr("cron.jobs.OUTPUT_DIR", tmp_path / "cron" / "output")
    return tmp_path


class TestCronCommandLifecycle:
    def test_pause_resume_run(self, tmp_cron_dir, capsys):
        job = create_job(prompt="Check server status", schedule="every 1h")

        cron_command(Namespace(cron_command="pause", job_id=job["id"]))
        paused = get_job(job["id"])
        assert paused["state"] == "paused"

        cron_command(Namespace(cron_command="resume", job_id=job["id"]))
        resumed = get_job(job["id"])
        assert resumed["state"] == "scheduled"

        cron_command(Namespace(cron_command="run", job_id=job["id"]))
        triggered = get_job(job["id"])
        assert triggered["state"] == "scheduled"

        out = capsys.readouterr().out
        assert "Paused job" in out
        assert "Resumed job" in out
        assert "Triggered job" in out

    def test_edit_can_replace_and_clear_skills(self, tmp_cron_dir, capsys):
        job = create_job(
            prompt="Combine skill outputs",
            schedule="every 1h",
            skill="blogwatcher",
        )

        cron_command(
            Namespace(
                cron_command="edit",
                job_id=job["id"],
                schedule="every 2h",
                prompt="Revised prompt",
                name="Edited Job",
                deliver=None,
                repeat=None,
                skill=None,
                skills=["find-nearby", "blogwatcher"],
                clear_skills=False,
            )
        )
        updated = get_job(job["id"])
        assert updated["skills"] == ["find-nearby", "blogwatcher"]
        assert updated["name"] == "Edited Job"
        assert updated["prompt"] == "Revised prompt"
        assert updated["schedule_display"] == "every 120m"

        cron_command(
            Namespace(
                cron_command="edit",
                job_id=job["id"],
                schedule=None,
                prompt=None,
                name=None,
                deliver=None,
                repeat=None,
                skill=None,
                skills=None,
                clear_skills=True,
            )
        )
        cleared = get_job(job["id"])
        assert cleared["skills"] == []
        assert cleared["skill"] is None

        out = capsys.readouterr().out
        assert "Updated job" in out

    def test_create_with_multiple_skills(self, tmp_cron_dir, capsys):
        cron_command(
            Namespace(
                cron_command="create",
                schedule="every 1h",
                prompt="Use both skills",
                name="Skill combo",
                deliver=None,
                repeat=None,
                skill=None,
                skills=["blogwatcher", "find-nearby"],
            )
        )
        out = capsys.readouterr().out
        assert "Created job" in out

        jobs = list_jobs()
        assert len(jobs) == 1
        assert jobs[0]["skills"] == ["blogwatcher", "find-nearby"]
        assert jobs[0]["name"] == "Skill combo"

    def test_create_rejects_swallowed_cli_flags_in_prompt(self, tmp_cron_dir, capsys):
        result = cron_command(
            Namespace(
                cron_command="create",
                schedule="2m",
                prompt="Reply with exactly: CRON HISTORY TEST 1 --into-history",
                name="bad prompt",
                deliver="origin",
                into_history=None,
                repeat=None,
                skill=None,
                skills=None,
                script=None,
            )
        )

        out = capsys.readouterr().out
        assert result == 1
        assert "accidentally placed inside the prompt" in out
        assert len(list_jobs()) == 0

    def test_create_allows_real_into_history_flag(self, tmp_cron_dir, capsys):
        result = cron_command(
            Namespace(
                cron_command="create",
                schedule="2m",
                prompt="Reply with exactly: CRON HISTORY TEST 1",
                name="good prompt",
                deliver="origin",
                into_history=True,
                repeat=None,
                skill=None,
                skills=None,
                script=None,
            )
        )

        out = capsys.readouterr().out
        assert result == 0
        assert "Created job" in out
        jobs = list_jobs()
        assert len(jobs) == 1
        assert jobs[0]["into_history"] is True

    def test_slash_cron_add_parses_into_history_flag(self, tmp_cron_dir, capsys):
        cli = HermesCLI.__new__(HermesCLI)
        cli._handle_cron_command(
            '/cron add 2m "Reply with exactly: TEST_HISTORY_201A" --deliver origin --into-history --name history-test-201a'
        )

        out = capsys.readouterr().out
        assert "Created job" in out
        jobs = list_jobs()
        assert len(jobs) == 1
        assert jobs[0]["into_history"] is True
        assert jobs[0]["deliver"] == "origin"
