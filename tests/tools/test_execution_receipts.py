import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from tools.execution_receipts import (
    get_execution_receipts_dir,
    get_execution_receipts_index_path,
    persist_execution_receipt,
    prune_execution_receipts,
    query_execution_receipts,
    reconcile_execution_receipts,
)


def _sample_receipt(**overrides):
    receipt = {
        "receipt_id": "receipt-1",
        "task_index": 0,
        "goal": "Inspect code",
        "child_session_id": "child-1",
        "status": "completed",
        "summary": "Done",
        "api_calls": 2,
        "duration_seconds": 1.5,
        "model": "gpt-5.4",
        "exit_reason": "completed",
        "fallback_reason": None,
        "tool_trace": [{"tool": "read_file", "status": "ok"}],
        "context_package": {"parent_session_id": "parent-1"},
        "execution_envelope": {"task_spec": "Inspect code"},
        "execution_envelope_digest": "abc123",
    }
    receipt.update(overrides)
    return receipt


class TestExecutionReceiptsLedger:
    def test_persist_writes_file_and_index(self, tmp_path):
        with patch("tools.execution_receipts.get_hermes_home", return_value=tmp_path):
            path = persist_execution_receipt(_sample_receipt())
            assert path == str(tmp_path / "artifacts" / "execution-receipts" / "receipt-1.json")
            assert Path(path).exists()
            rows = query_execution_receipts()
            assert len(rows) == 1
            assert rows[0]["receipt_id"] == "receipt-1"
            assert rows[0]["parent_session_id"] == "parent-1"
            assert rows[0]["task_spec"] == "Inspect code"

    def test_query_filters(self, tmp_path):
        with patch("tools.execution_receipts.get_hermes_home", return_value=tmp_path):
            persist_execution_receipt(_sample_receipt(receipt_id="r1", child_session_id="child-a", status="completed", execution_path="subagent", worker_mode="cold", worker_task_id="delegate-cold-1", worker_runtime_kind="DockerTerminalEnvironment", worker_runtime_id="cold-container-1"))
            persist_execution_receipt(_sample_receipt(receipt_id="r2", child_session_id="child-b", status="failed", execution_path="direct_terminal_work_order", fallback_reason="max_iterations", worker_mode="warm", worker_task_id="delegate-lease-abcd", worker_reused=True, worker_reuse_count=2, worker_runtime_kind="DockerTerminalEnvironment", worker_runtime_id="warm-container-1", worker_runtime_reused=True))
            completed = query_execution_receipts(status="completed")
            failed = query_execution_receipts(status="failed")
            child_b = query_execution_receipts(child_session_id="child-b")
            assert [row["receipt_id"] for row in completed] == ["r1"]
            assert [row["receipt_id"] for row in failed] == ["r2"]
            assert [row["receipt_id"] for row in child_b] == ["r2"]
            assert completed[0]["execution_path"] == "subagent"
            assert completed[0]["worker_mode"] == "cold"
            assert completed[0]["worker_runtime_kind"] == "DockerTerminalEnvironment"
            assert completed[0]["worker_runtime_id"] == "cold-container-1"
            assert failed[0]["execution_path"] == "direct_terminal_work_order"
            assert failed[0]["worker_mode"] == "warm"
            assert failed[0]["worker_reused"] == 1
            assert failed[0]["worker_reuse_count"] == 2
            assert failed[0]["worker_runtime_kind"] == "DockerTerminalEnvironment"
            assert failed[0]["worker_runtime_id"] == "warm-container-1"
            assert failed[0]["worker_runtime_reused"] == 1

    def test_prune_keeps_failed_by_default(self, tmp_path):
        with patch("tools.execution_receipts.get_hermes_home", return_value=tmp_path):
            old = time.time() - 10_000
            persist_execution_receipt(_sample_receipt(receipt_id="old-ok", ledger_created_at=old, status="completed"))
            persist_execution_receipt(_sample_receipt(receipt_id="old-failed", ledger_created_at=old, status="failed", fallback_reason="max_iterations"))
            result = prune_execution_receipts(max_age_seconds=60, keep_failed=True)
            assert result["deleted_count"] == 1
            assert result["deleted_receipt_ids"] == ["old-ok"]
            remaining = {row["receipt_id"] for row in query_execution_receipts(limit=10)}
            assert "old-failed" in remaining
            assert "old-ok" not in remaining

    def test_prune_can_remove_failed(self, tmp_path):
        with patch("tools.execution_receipts.get_hermes_home", return_value=tmp_path):
            old = time.time() - 10_000
            persist_execution_receipt(_sample_receipt(receipt_id="old-failed", ledger_created_at=old, status="failed", fallback_reason="max_iterations"))
            result = prune_execution_receipts(max_age_seconds=60, keep_failed=False)
            assert result["deleted_count"] == 1
            assert result["deleted_receipt_ids"] == ["old-failed"]
            assert query_execution_receipts(limit=10) == []

    def test_persist_rolls_back_file_when_indexing_fails(self, tmp_path):
        with patch("tools.execution_receipts.get_hermes_home", return_value=tmp_path):
            with patch("tools.execution_receipts._connect_index", side_effect=RuntimeError("db down")):
                path = persist_execution_receipt(_sample_receipt(receipt_id="rollback-me"))
            assert path is None
            assert not (tmp_path / "artifacts" / "execution-receipts" / "rollback-me.json").exists()

    def test_persist_failed_overwrite_restores_previous_file(self, tmp_path):
        with patch("tools.execution_receipts.get_hermes_home", return_value=tmp_path):
            original_path = persist_execution_receipt(_sample_receipt(receipt_id="same-id", summary="original"))
            assert original_path is not None
            with patch("tools.execution_receipts._connect_index", side_effect=RuntimeError("db down")):
                failed_path = persist_execution_receipt(_sample_receipt(receipt_id="same-id", summary="new"))
            assert failed_path is None
            restored = json.loads(Path(original_path).read_text(encoding="utf-8"))
            assert restored["summary"] == "original"
            rows = query_execution_receipts(limit=10)
            assert [row["receipt_id"] for row in rows] == ["same-id"]

    def test_prune_rejects_non_positive_age(self, tmp_path):
        with patch("tools.execution_receipts.get_hermes_home", return_value=tmp_path):
            persist_execution_receipt(_sample_receipt(receipt_id="fresh"))
            with pytest.raises(ValueError, match="max_age_seconds must be > 0"):
                prune_execution_receipts(max_age_seconds=0)
            with pytest.raises(ValueError, match="max_age_seconds must be > 0"):
                prune_execution_receipts(max_age_seconds=-1)

    def test_reconcile_reindexes_untracked_file(self, tmp_path):
        with patch("tools.execution_receipts.get_hermes_home", return_value=tmp_path):
            receipts_dir = get_execution_receipts_dir()
            receipt_path = receipts_dir / "orphan.json"
            receipt_path.write_text(json.dumps(_sample_receipt(receipt_id="orphan")), encoding="utf-8")
            result = reconcile_execution_receipts()
            assert result["inserted_count"] == 1
            assert result["inserted_receipt_ids"] == ["orphan"]
            rows = query_execution_receipts(limit=10)
            assert [row["receipt_id"] for row in rows] == ["orphan"]

    def test_reconcile_drops_missing_index_rows(self, tmp_path):
        with patch("tools.execution_receipts.get_hermes_home", return_value=tmp_path):
            persist_execution_receipt(_sample_receipt(receipt_id="missing-file"))
            (tmp_path / "artifacts" / "execution-receipts" / "missing-file.json").unlink()
            result = reconcile_execution_receipts(delete_missing_rows=True)
            assert result["removed_missing_count"] == 1
            assert result["removed_missing_receipt_ids"] == ["missing-file"]
            assert query_execution_receipts(limit=10) == []

    def test_index_path_lives_under_receipts_dir(self, tmp_path):
        with patch("tools.execution_receipts.get_hermes_home", return_value=tmp_path):
            receipts_dir = get_execution_receipts_dir()
            index_path = get_execution_receipts_index_path()
            assert receipts_dir == tmp_path / "artifacts" / "execution-receipts"
            assert index_path == receipts_dir / "index.sqlite"
