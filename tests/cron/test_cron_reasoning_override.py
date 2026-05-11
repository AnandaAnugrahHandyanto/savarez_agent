"""Tests for per-job cron reasoning_effort overrides."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cron.jobs import create_job, get_job, update_job
from cron.scheduler import run_job


@pytest.fixture
def cron_env(tmp_path, monkeypatch):
    """Isolated cron environment with temp HERMES_HOME."""
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    (hermes_home / "cron").mkdir()
    (hermes_home / "cron" / "output").mkdir()
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    import cron.jobs as jobs_mod

    monkeypatch.setattr(jobs_mod, "HERMES_DIR", hermes_home)
    monkeypatch.setattr(jobs_mod, "CRON_DIR", hermes_home / "cron")
    monkeypatch.setattr(jobs_mod, "JOBS_FILE", hermes_home / "cron" / "jobs.json")
    monkeypatch.setattr(jobs_mod, "OUTPUT_DIR", hermes_home / "cron" / "output")

    return hermes_home


class TestJobReasoningEffortField:
    def test_create_job_persists_reasoning_effort(self, cron_env):
        job = create_job(prompt="Think carefully", schedule="every 1h", reasoning_effort="high")
        assert job["reasoning_effort"] == "high"

        loaded = get_job(job["id"])
        assert loaded["reasoning_effort"] == "high"

    def test_update_job_reasoning_effort_can_be_cleared(self, cron_env):
        job = create_job(prompt="Think carefully", schedule="every 1h", reasoning_effort="high")

        updated = update_job(job["id"], {"reasoning_effort": None})
        assert updated.get("reasoning_effort") is None

        loaded = get_job(job["id"])
        assert loaded.get("reasoning_effort") is None


class TestCronjobToolReasoningEffort:
    def test_create_and_update_reasoning_effort(self, cron_env, monkeypatch):
        monkeypatch.setenv("HERMES_INTERACTIVE", "1")
        from tools.cronjob_tools import cronjob

        create_result = json.loads(
            cronjob(
                action="create",
                schedule="every 1h",
                prompt="Think carefully",
                reasoning_effort="high",
            )
        )
        assert create_result["success"] is True
        assert create_result["job"]["reasoning_effort"] == "high"

        update_result = json.loads(
            cronjob(
                action="update",
                job_id=create_result["job_id"],
                reasoning_effort="",
            )
        )
        assert update_result["success"] is True
        assert "reasoning_effort" not in update_result["job"]


class TestRunJobReasoningEffortOverride:
    def test_run_job_prefers_job_reasoning_effort_over_global_config(self, tmp_path):
        job = {
            "id": "reasoning-job",
            "name": "reasoning test",
            "prompt": "hello",
            "reasoning_effort": "high",
        }
        fake_db = MagicMock()

        with patch("cron.scheduler._hermes_home", tmp_path), \
             patch("cron.scheduler._resolve_origin", return_value=None), \
             patch("dotenv.load_dotenv"), \
             patch("hermes_state.SessionDB", return_value=fake_db), \
             patch(
                 "hermes_cli.config.load_config",
                 return_value={
                     "agent": {"reasoning_effort": "medium"},
                     "model": {"default": "gpt-5.4"},
                 },
             ), \
             patch(
                 "hermes_cli.runtime_provider.resolve_runtime_provider",
                 return_value={
                     "api_key": "test-key",
                     "base_url": "https://example.invalid/v1",
                     "provider": "openrouter",
                     "api_mode": "chat_completions",
                 },
             ), \
             patch("run_agent.AIAgent") as mock_agent_cls:
            mock_agent = MagicMock()
            mock_agent.run_conversation.return_value = {"final_response": "ok"}
            mock_agent_cls.return_value = mock_agent

            success, _output, final_response, error = run_job(job)

        assert success is True
        assert error is None
        assert final_response == "ok"
        kwargs = mock_agent_cls.call_args.kwargs
        assert kwargs["reasoning_config"] == {"enabled": True, "effort": "high"}
