"""Tests for CLI heartbeat management."""

from argparse import Namespace

from hermes_cli.heartbeat import heartbeat_command
from cron.heartbeat import get_heartbeat_job


def _redirect_cron_storage(tmp_path, monkeypatch):
    monkeypatch.setattr("cron.jobs.CRON_DIR", tmp_path / "cron")
    monkeypatch.setattr("cron.jobs.JOBS_FILE", tmp_path / "cron" / "jobs.json")
    monkeypatch.setattr("cron.jobs.OUTPUT_DIR", tmp_path / "cron" / "output")


class TestHeartbeatCommand:
    def test_enable_status_disable(self, tmp_path, monkeypatch, capsys):
        _redirect_cron_storage(tmp_path, monkeypatch)

        heartbeat_command(Namespace(heartbeat_command="enable", schedule="every 2h", mission="Stay useful", deliver=None))
        job = get_heartbeat_job()
        assert job is not None

        heartbeat_command(Namespace(heartbeat_command="status"))
        heartbeat_command(Namespace(heartbeat_command="disable"))

        out = capsys.readouterr().out
        assert "Heartbeat enabled" in out
        assert "Heartbeat status" in out
        assert "Heartbeat disabled" in out
