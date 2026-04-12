"""Tests for first-class heartbeat management built on cron jobs."""

from cron.heartbeat import (
    DEFAULT_HEARTBEAT_NAME,
    DEFAULT_HEARTBEAT_SCHEDULE,
    build_heartbeat_prompt,
    disable_heartbeat,
    enable_heartbeat,
    get_heartbeat_job,
    heartbeat_status,
)


def _redirect_cron_storage(tmp_path, monkeypatch):
    monkeypatch.setattr("cron.jobs.CRON_DIR", tmp_path / "cron")
    monkeypatch.setattr("cron.jobs.JOBS_FILE", tmp_path / "cron" / "jobs.json")
    monkeypatch.setattr("cron.jobs.OUTPUT_DIR", tmp_path / "cron" / "output")


class TestHeartbeatPrompt:
    def test_prompt_includes_autonomous_guidance(self):
        prompt = build_heartbeat_prompt("Keep making yourself useful")
        assert "periodic autonomous heartbeat" in prompt.lower()
        assert "session_search" in prompt
        assert "[SILENT]" in prompt
        assert "Keep making yourself useful" in prompt


class TestHeartbeatLifecycle:
    def test_enable_creates_heartbeat_job(self, tmp_path, monkeypatch):
        _redirect_cron_storage(tmp_path, monkeypatch)

        job = enable_heartbeat()

        assert job["name"] == DEFAULT_HEARTBEAT_NAME
        assert job["schedule_display"] == DEFAULT_HEARTBEAT_SCHEDULE
        assert job["kind"] == "heartbeat"
        assert job["include_memory"] is True
        assert "session_search" in job["prompt"]

    def test_enable_updates_existing_job_in_place(self, tmp_path, monkeypatch):
        _redirect_cron_storage(tmp_path, monkeypatch)

        first = enable_heartbeat()
        updated = enable_heartbeat(schedule="every 4h", mission="Focus on follow-ups")

        assert updated["id"] == first["id"]
        assert updated["schedule_display"] == "every 240m"
        assert "Focus on follow-ups" in updated["prompt"]

    def test_status_reports_existing_job(self, tmp_path, monkeypatch):
        _redirect_cron_storage(tmp_path, monkeypatch)
        created = enable_heartbeat()

        status = heartbeat_status()

        assert status["enabled"] is True
        assert status["job_id"] == created["id"]
        assert status["name"] == DEFAULT_HEARTBEAT_NAME

    def test_disable_pauses_existing_job(self, tmp_path, monkeypatch):
        _redirect_cron_storage(tmp_path, monkeypatch)
        created = enable_heartbeat()

        paused = disable_heartbeat()
        fetched = get_heartbeat_job()

        assert paused["id"] == created["id"]
        assert paused["state"] == "paused"
        assert fetched["enabled"] is False
