import json

from cron.jobs import create_job
from tools.execution_receipts import get_execution_receipts_dir, persist_execution_receipt
from tools.execution_receipts_tool import (
    EXECUTION_RECEIPTS_SCHEMA,
    MAINTENANCE_JOB_NAME,
    MAINTENANCE_PROMPT_MARKER,
    execution_receipts_tool,
)


def _seed_receipt(receipt_id: str, *, status: str = "completed"):
    return {
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


class TestExecutionReceiptsTool:
    def test_schema_lists_actions(self):
        action = EXECUTION_RECEIPTS_SCHEMA["parameters"]["properties"]["action"]
        assert action["enum"] == [
            "list",
            "query",
            "prune",
            "reconcile",
            "maintenance_status",
            "install_maintenance",
            "remove_maintenance",
        ]

    def test_list_returns_recent_receipts(self, tmp_path, monkeypatch):
        monkeypatch.setattr("tools.execution_receipts.get_hermes_home", lambda: tmp_path)
        persist_execution_receipt(_seed_receipt("r1"))
        payload = json.loads(execution_receipts_tool(action="list", limit=5))
        assert payload["action"] == "list"
        assert payload["count"] == 1
        assert payload["receipts"][0]["receipt_id"] == "r1"

    def test_query_filters_by_status(self, tmp_path, monkeypatch):
        monkeypatch.setattr("tools.execution_receipts.get_hermes_home", lambda: tmp_path)
        persist_execution_receipt(_seed_receipt("r1", status="completed"))
        persist_execution_receipt(_seed_receipt("r2", status="failed"))
        payload = json.loads(execution_receipts_tool(action="query", status="failed", limit=5))
        assert payload["count"] == 1
        assert payload["receipts"][0]["receipt_id"] == "r2"

    def test_prune_requires_max_age(self):
        payload = json.loads(execution_receipts_tool(action="prune"))
        assert "error" in payload

    def test_prune_rejects_non_positive_age(self):
        payload = json.loads(execution_receipts_tool(action="prune", max_age_seconds=0))
        assert "error" in payload
        assert "must be > 0" in payload["error"]

    def test_prune_removes_old_receipts(self, tmp_path, monkeypatch):
        monkeypatch.setattr("tools.execution_receipts.get_hermes_home", lambda: tmp_path)
        persist_execution_receipt({**_seed_receipt("old"), "ledger_created_at": 1.0})
        payload = json.loads(execution_receipts_tool(action="prune", max_age_seconds=1, limit=5, keep_failed=True))
        assert payload["deleted_count"] == 1
        assert payload["deleted_receipt_ids"] == ["old"]

    def test_reconcile_reindexes_orphan_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("tools.execution_receipts.get_hermes_home", lambda: tmp_path)
        receipts_dir = get_execution_receipts_dir()
        file_path = receipts_dir / "orphan-tool.json"
        file_path.write_text(json.dumps(_seed_receipt("orphan-tool")), encoding="utf-8")
        payload = json.loads(execution_receipts_tool(action="reconcile"))
        assert payload["inserted_count"] == 1
        assert payload["inserted_receipt_ids"] == ["orphan-tool"]

    def test_install_maintenance_creates_cron_job(self, tmp_path, monkeypatch):
        cron_dir = tmp_path / "cron"
        monkeypatch.setattr("cron.jobs.CRON_DIR", cron_dir)
        monkeypatch.setattr("cron.jobs.JOBS_FILE", cron_dir / "jobs.json")
        monkeypatch.setattr("cron.jobs.OUTPUT_DIR", cron_dir / "output")

        payload = json.loads(
            execution_receipts_tool(
                action="install_maintenance",
                schedule="every 2h",
                prune_completed_after_seconds=600,
                prune_failed_after_seconds=7200,
                delete_missing_rows=True,
                limit=77,
                model="gpt-5.4",
                provider="openai-codex",
            )
        )

        assert payload["installed"] is True
        assert payload["created"] is True
        job = payload["job"]
        assert job["name"] == MAINTENANCE_JOB_NAME
        assert job["schedule"] == "every 120m"
        assert job["deliver"] == "local"
        assert job["model"] == "gpt-5.4"
        assert job["provider"] == "openai-codex"
        assert job["config"]["prune_limit"] == 77

        status = json.loads(execution_receipts_tool(action="maintenance_status"))
        assert status["installed"] is True
        assert status["installed_count"] == 1
        assert status["jobs"][0]["job_id"] == job["job_id"]
        assert status["jobs"][0]["config"]["prune_completed_after_seconds"] == 600.0

        jobs_payload = json.loads((cron_dir / "jobs.json").read_text(encoding="utf-8"))
        assert MAINTENANCE_PROMPT_MARKER in jobs_payload["jobs"][0]["prompt"]

    def test_install_maintenance_updates_existing_job(self, tmp_path, monkeypatch):
        cron_dir = tmp_path / "cron"
        monkeypatch.setattr("cron.jobs.CRON_DIR", cron_dir)
        monkeypatch.setattr("cron.jobs.JOBS_FILE", cron_dir / "jobs.json")
        monkeypatch.setattr("cron.jobs.OUTPUT_DIR", cron_dir / "output")

        first = json.loads(execution_receipts_tool(action="install_maintenance", schedule="every 6h"))
        second = json.loads(
            execution_receipts_tool(
                action="install_maintenance",
                schedule="every 4h",
                prune_completed_after_seconds=120,
                prune_failed_after_seconds=240,
                delete_missing_rows=False,
                limit=11,
            )
        )

        assert first["job"]["job_id"] == second["job"]["job_id"]
        assert second["created"] is False
        assert second["updated"] is True
        assert second["job"]["schedule"] == "every 240m"
        assert second["job"]["config"]["delete_missing_rows"] is False
        assert second["job"]["config"]["prune_limit"] == 11

        status = json.loads(execution_receipts_tool(action="maintenance_status"))
        assert status["installed_count"] == 1

    def test_same_name_non_marker_job_is_not_treated_as_maintenance(self, tmp_path, monkeypatch):
        cron_dir = tmp_path / "cron"
        monkeypatch.setattr("cron.jobs.CRON_DIR", cron_dir)
        monkeypatch.setattr("cron.jobs.JOBS_FILE", cron_dir / "jobs.json")
        monkeypatch.setattr("cron.jobs.OUTPUT_DIR", cron_dir / "output")

        unrelated = create_job(
            prompt="unrelated job",
            schedule="every 3h",
            name=MAINTENANCE_JOB_NAME,
            deliver="local",
        )

        status_before = json.loads(execution_receipts_tool(action="maintenance_status"))
        assert status_before["installed"] is False
        assert status_before["installed_count"] == 0

        removed_before = json.loads(execution_receipts_tool(action="remove_maintenance"))
        assert removed_before["deleted_count"] == 0

        install = json.loads(execution_receipts_tool(action="install_maintenance", schedule="every 1h"))
        assert install["job"]["job_id"] != unrelated["id"]

        jobs_payload = json.loads((cron_dir / "jobs.json").read_text(encoding="utf-8"))
        assert len(jobs_payload["jobs"]) == 2

        status_after = json.loads(execution_receipts_tool(action="maintenance_status"))
        assert status_after["installed"] is True
        assert status_after["installed_count"] == 1
        assert status_after["jobs"][0]["job_id"] == install["job"]["job_id"]

    def test_remove_maintenance_removes_matching_jobs(self, tmp_path, monkeypatch):
        cron_dir = tmp_path / "cron"
        monkeypatch.setattr("cron.jobs.CRON_DIR", cron_dir)
        monkeypatch.setattr("cron.jobs.JOBS_FILE", cron_dir / "jobs.json")
        monkeypatch.setattr("cron.jobs.OUTPUT_DIR", cron_dir / "output")

        install = json.loads(execution_receipts_tool(action="install_maintenance", schedule="every 1h"))
        payload = json.loads(execution_receipts_tool(action="remove_maintenance"))

        assert payload["deleted_count"] == 1
        assert payload["deleted_job_ids"] == [install["job"]["job_id"]]

        status = json.loads(execution_receipts_tool(action="maintenance_status"))
        assert status["installed"] is False
        assert status["installed_count"] == 0
