"""Tests for `hermes cron list` rendering (hermes_cli.cron.cron_list)."""

import cron.jobs
import hermes_cli.cron as c


def test_list_renders_job_with_null_deliver(monkeypatch, capsys):
    """A job whose `deliver` field is present but null must render (falling back
    to 'local'), not crash with TypeError on ", ".join(None) (#32896)."""
    job = {"id": "job-1", "name": "nightly", "deliver": None}
    monkeypatch.setattr(cron.jobs, "list_jobs", lambda include_disabled=False: [job])

    c.cron_list()
    out = capsys.readouterr().out
    assert "local" in out  # null deliver falls back to the default channel
