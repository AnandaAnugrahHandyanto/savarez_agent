"""Tests for the /cron-list gateway slash command."""

import pytest

from cron.jobs import create_job, pause_job
from gateway.config import Platform
from gateway.platforms.base import MessageEvent
from gateway.session import SessionSource


@pytest.fixture()
def tmp_cron_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("cron.jobs.CRON_DIR", tmp_path / "cron")
    monkeypatch.setattr("cron.jobs.JOBS_FILE", tmp_path / "cron" / "jobs.json")
    monkeypatch.setattr("cron.jobs.OUTPUT_DIR", tmp_path / "cron" / "output")
    return tmp_path


def _make_event(text: str) -> MessageEvent:
    return MessageEvent(
        text=text,
        source=SessionSource(
            platform=Platform.TELEGRAM,
            chat_id="chat-1",
            user_id="user-1",
            user_name="tester",
            chat_type="dm",
        ),
    )


def _make_runner():
    from gateway.run import GatewayRunner

    return object.__new__(GatewayRunner)


@pytest.mark.asyncio
async def test_cron_list_command_reads_job_store_without_shell(tmp_cron_dir, monkeypatch):
    active = create_job(prompt="Audit active jobs", schedule="every 1h", name="Active audit")
    paused = create_job(prompt="Audit paused jobs", schedule="30m", name="Paused audit")
    pause_job(paused["id"])

    def fail_shell(*_args, **_kwargs):
        raise AssertionError("/cron-list must not invoke subprocesses")

    monkeypatch.setattr("subprocess.run", fail_shell)
    monkeypatch.setattr("subprocess.Popen", fail_shell)

    out = await _make_runner()._handle_cron_list_command(_make_event("/cron-list"))

    assert f"job_id: {active['id']}" in out
    assert f"job_id: {paused['id']}" in out
    assert "name: Active audit" in out
    assert "name: Paused audit" in out
    assert "status: scheduled" in out
    assert "status: paused" in out
    assert "last_run: -" in out
    assert "next_run:" in out


@pytest.mark.asyncio
async def test_cron_list_command_rejects_unknown_args(tmp_cron_dir):
    out = await _make_runner()._handle_cron_list_command(_make_event("/cron-list now"))

    assert out == "Usage: /cron-list [--all]"
