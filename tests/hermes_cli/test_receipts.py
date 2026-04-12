"""Tests for hermes_cli.receipts surfaces."""

import json
from argparse import Namespace

from cron.jobs import create_job, get_job
from hermes_cli.receipts import capture_receipts_slash_output, receipts_command
from tools.execution_receipts import persist_execution_receipt
from tools.execution_receipts_tool import MAINTENANCE_JOB_NAME


def _receipt(receipt_id: str, *, status: str = "completed", ledger_created_at: float | None = None):
    payload = {
        "receipt_id": receipt_id,
        "task_index": 0,
        "goal": f"goal-{receipt_id}",
        "child_session_id": f"child-{receipt_id}",
        "status": status,
        "summary": "done",
        "api_calls": 1,
        "duration_seconds": 1.0,
        "model": "gpt-5.4",
        "fallback_reason": None if status == "completed" else "max_iterations",
        "tool_trace": [],
        "context_package": {"parent_session_id": "parent-1"},
        "execution_envelope": {"task_spec": "inspect"},
        "execution_envelope_digest": f"digest-{receipt_id}",
    }
    if ledger_created_at is not None:
        payload["ledger_created_at"] = ledger_created_at
    return payload


def _setup_cron(monkeypatch, tmp_path):
    cron_dir = tmp_path / "cron"
    monkeypatch.setattr("cron.jobs.CRON_DIR", cron_dir)
    monkeypatch.setattr("cron.jobs.JOBS_FILE", cron_dir / "jobs.json")
    monkeypatch.setattr("cron.jobs.OUTPUT_DIR", cron_dir / "output")
    return cron_dir


class TestReceiptsCliCommand:
    def test_list_and_prune(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr("tools.execution_receipts.get_hermes_home", lambda: tmp_path)
        persist_execution_receipt({**_receipt("fresh"), "execution_path": "direct_terminal_work_order", "worker_mode": "warm", "worker_task_id": "delegate-lease-abcd", "worker_reused": True, "worker_reuse_count": 3, "worker_runtime_kind": "DockerTerminalEnvironment", "worker_runtime_id": "container-xyz", "worker_runtime_reused": True})
        persist_execution_receipt(_receipt("old", ledger_created_at=1.0))

        rc = receipts_command(Namespace(receipts_command="list", limit=10, status=None, parent_session_id=None, child_session_id=None))
        assert rc == 0
        out = capsys.readouterr().out
        assert "Execution Receipts" in out
        assert "fresh" in out
        assert "old" in out
        assert "Exec path:" in out
        assert "direct_terminal_work_order" in out
        assert "Worker:" in out
        assert "delegate-lease-abcd" in out
        assert "runtime-reused" in out
        assert "Runtime:" in out
        assert "container-xyz" in out

        rc = receipts_command(Namespace(receipts_command="prune", max_age_seconds=60.0, include_failed=False, limit=100))
        assert rc == 0
        out = capsys.readouterr().out
        assert "Pruned execution receipts" in out
        assert "old" in out

    def test_install_status_remove(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr("tools.execution_receipts.get_hermes_home", lambda: tmp_path)
        _setup_cron(monkeypatch, tmp_path)

        rc = receipts_command(
            Namespace(
                receipts_command="install",
                schedule="every 2h",
                prune_completed_after_seconds=600.0,
                prune_failed_after_seconds=7200.0,
                keep_missing_rows=False,
                limit=22,
                model="gpt-5.4",
                provider="openai-codex",
                base_url=None,
            )
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "Created execution receipt maintenance job" in out

        status_rc = receipts_command(Namespace(receipts_command="status"))
        assert status_rc == 0
        out = capsys.readouterr().out
        assert "Installed jobs: 1" in out
        assert "Retain completed for: 600.0s" in out

        remove_rc = receipts_command(Namespace(receipts_command="remove"))
        assert remove_rc == 0
        out = capsys.readouterr().out
        assert "Removed execution receipt maintenance job" in out

    def test_slash_status_install_remove(self, tmp_path, monkeypatch):
        monkeypatch.setattr("tools.execution_receipts.get_hermes_home", lambda: tmp_path)
        _setup_cron(monkeypatch, tmp_path)

        before = capture_receipts_slash_output("/receipts status")
        assert "Installed jobs: 0" in before

        install_out = capture_receipts_slash_output("/receipts install --schedule 'every 1h' --prune-completed-after-seconds 120 --prune-failed-after-seconds 240 --limit 11")
        assert "Created execution receipt maintenance job" in install_out

        after = capture_receipts_slash_output("/receipts status")
        assert "Installed jobs: 1" in after
        assert "Prune limit:          11" in after

        remove_out = capture_receipts_slash_output("/receipts remove")
        assert "Removed execution receipt maintenance job" in remove_out

    def test_slash_install_uses_default_maintenance_limit(self, tmp_path, monkeypatch):
        monkeypatch.setattr("tools.execution_receipts.get_hermes_home", lambda: tmp_path)
        _setup_cron(monkeypatch, tmp_path)

        install_out = capture_receipts_slash_output("/receipts install --schedule 'every 1h'")
        assert "Created execution receipt maintenance job" in install_out

        status_out = capture_receipts_slash_output("/receipts status")
        assert "Prune limit:          200" in status_out

    def test_slash_prune_uses_default_limit_100(self, tmp_path, monkeypatch):
        monkeypatch.setattr("tools.execution_receipts.get_hermes_home", lambda: tmp_path)
        for idx in range(12):
            persist_execution_receipt(_receipt(f"old-{idx}", ledger_created_at=1.0))

        prune_out = capture_receipts_slash_output("/receipts prune 60")
        assert "Deleted: 12" in prune_out

    def test_same_name_unrelated_job_survives_receipts_surface(self, tmp_path, monkeypatch):
        monkeypatch.setattr("tools.execution_receipts.get_hermes_home", lambda: tmp_path)
        _setup_cron(monkeypatch, tmp_path)

        unrelated = create_job(
            prompt="plain unrelated cron job",
            schedule="every 4h",
            name=MAINTENANCE_JOB_NAME,
            deliver="local",
        )

        status_out = capture_receipts_slash_output("/receipts status")
        assert "Installed jobs: 0" in status_out

        remove_out = capture_receipts_slash_output("/receipts remove")
        assert "No execution receipt maintenance job was installed" in remove_out
        assert get_job(unrelated["id"]) is not None

    def test_rm_alias_removes_maintenance(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr("tools.execution_receipts.get_hermes_home", lambda: tmp_path)
        _setup_cron(monkeypatch, tmp_path)

        receipts_command(
            Namespace(
                receipts_command="install",
                schedule="every 2h",
                prune_completed_after_seconds=600.0,
                prune_failed_after_seconds=7200.0,
                keep_missing_rows=False,
                limit=22,
                model=None,
                provider=None,
                base_url=None,
            )
        )
        capsys.readouterr()

        rc = receipts_command(Namespace(receipts_command="rm"))
        assert rc == 0
        out = capsys.readouterr().out
        assert "Removed execution receipt maintenance job" in out
