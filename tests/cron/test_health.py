"""Tests for cron/health.py — built-in Hermes health checks."""

import json
import os

import pytest

from cron.health import (
    self_config_health,
    skills_integrity,
    cron_job_integrity,
    run_all,
)


# =========================================================================
# self_config_health
# =========================================================================


class TestSelfConfigHealth:
    def test_returns_dict_with_name_and_status(self, monkeypatch, tmp_path):
        monkeypatch.setattr("cron.health.get_hermes_home", lambda: tmp_path)
        # Create config.yaml and .env so they exist
        (tmp_path / "config.yaml").write_text("key: value")
        (tmp_path / ".env").write_text("SECRET=x")
        result = self_config_health()
        assert result["name"] == "self_config_health"
        assert result["status"] in ("ok", "degraded", "failed")

    def test_degraded_when_files_missing(self, monkeypatch, tmp_path):
        monkeypatch.setattr("cron.health.get_hermes_home", lambda: tmp_path)
        # No files created
        result = self_config_health()
        assert result["status"] == "degraded"


# =========================================================================
# skills_integrity
# =========================================================================


class TestSkillsIntegrity:
    def test_returns_degraded_for_empty_skills_dir(self, monkeypatch, tmp_path):
        monkeypatch.setattr("cron.health.get_hermes_home", lambda: tmp_path)
        (tmp_path / "skills").mkdir(parents=True)
        result = skills_integrity()
        assert result["status"] == "degraded"  # 0 skills → degraded

    def test_returns_failed_when_skills_dir_missing(self, monkeypatch, tmp_path):
        monkeypatch.setattr("cron.health.get_hermes_home", lambda: tmp_path)
        result = skills_integrity()
        assert result["status"] == "failed"
        assert "not found" in result["message"]

    def test_ok_for_valid_skill(self, monkeypatch, tmp_path):
        monkeypatch.setattr("cron.health.get_hermes_home", lambda: tmp_path)
        skill_dir = tmp_path / "skills" / "my-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: my-skill\ndescription: test\n---\n\n# My Skill\n"
        )
        result = skills_integrity()
        assert result["status"] == "ok"

    def test_broken_for_missing_skill_md(self, monkeypatch, tmp_path):
        monkeypatch.setattr("cron.health.get_hermes_home", lambda: tmp_path)
        skill_dir = tmp_path / "skills" / "broken-skill"
        skill_dir.mkdir(parents=True)
        # No SKILL.md
        result = skills_integrity()
        assert result["status"] == "failed"
        assert result["detail"]["broken"][0]["name"] == "broken-skill"


# =========================================================================
# cron_job_integrity
# =========================================================================


class TestCronJobIntegrity:
    def test_returns_ok_when_no_jobs_file(self, monkeypatch, tmp_path):
        monkeypatch.setattr("cron.health.get_hermes_home", lambda: tmp_path)
        result = cron_job_integrity()
        assert result["status"] == "ok"

    def test_ok_for_empty_jobs_list(self, monkeypatch, tmp_path):
        monkeypatch.setattr("cron.health.get_hermes_home", lambda: tmp_path)
        cron_dir = tmp_path / "cron"
        cron_dir.mkdir(parents=True)
        (cron_dir / "jobs.json").write_text("[]")
        result = cron_job_integrity()
        assert result["status"] == "ok"

    def test_ok_for_valid_jobs(self, monkeypatch, tmp_path):
        monkeypatch.setattr("cron.health.get_hermes_home", lambda: tmp_path)
        cron_dir = tmp_path / "cron"
        cron_dir.mkdir(parents=True)
        jobs = [
            {"id": "j1", "schedule": "0 9 * * *", "skills": [], "script": None},
            {"id": "j2", "schedule": "every 30m", "skills": [], "script": None},
        ]
        (cron_dir / "jobs.json").write_text(json.dumps(jobs))
        result = cron_job_integrity()
        assert result["status"] == "ok"

    def test_degraded_for_missing_skill(self, monkeypatch, tmp_path):
        monkeypatch.setattr("cron.health.get_hermes_home", lambda: tmp_path)
        cron_dir = tmp_path / "cron"
        cron_dir.mkdir(parents=True)
        jobs = [
            {"id": "j1", "schedule": "0 9 * * *", "skills": ["nonexistent-skill"]},
        ]
        (cron_dir / "jobs.json").write_text(json.dumps(jobs))
        result = cron_job_integrity()
        assert result["status"] == "degraded"


# =========================================================================
# run_all
# =========================================================================


class TestRunAll:
    def test_returns_list_of_three_results(self, monkeypatch, tmp_path):
        monkeypatch.setattr("cron.health.get_hermes_home", lambda: tmp_path)
        (tmp_path / "config.yaml").write_text("key: value")
        (tmp_path / ".env").write_text("SECRET=x")
        results = run_all()
        assert len(results) == 3
        names = {r["name"] for r in results}
        assert "self_config_health" in names
        assert "skills_integrity" in names
        assert "cron_job_integrity" in names

    def test_each_result_has_required_fields(self, monkeypatch, tmp_path):
        monkeypatch.setattr("cron.health.get_hermes_home", lambda: tmp_path)
        (tmp_path / "config.yaml").write_text("key: value")
        (tmp_path / ".env").write_text("SECRET=x")
        for r in run_all():
            assert "name" in r
            assert "status" in r
            assert "message" in r
            assert r["status"] in ("ok", "degraded", "failed")
