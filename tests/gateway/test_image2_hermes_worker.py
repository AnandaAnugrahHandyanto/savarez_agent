from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from gateway.image2_store import Image2JobStore
from gateway.image2_worker import run_worker


def _row(db_path: Path, task_id: str) -> dict[str, str]:
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM image2_jobs WHERE task_id = ?", (task_id,)).fetchone()
    assert row is not None
    return dict(row)


def _enqueue(runtime: Path, payload: dict[str, object]) -> dict[str, object]:
    return Image2JobStore(db_path=runtime / "image2_jobs.sqlite", runtime_root=runtime).enqueue_feishu(payload)


def test_worker_claims_only_requested_task_and_never_falls_back_to_old_retryable(tmp_path):
    runtime = tmp_path / "runtime"
    db_path = runtime / "image2_jobs.sqlite"
    old = _enqueue(
        runtime,
        {
            "feishu_message_id": "old-msg",
            "chat_id": "chat",
            "root_id": "old-root",
            "thread_id": "old-root",
            "text": "旧任务，应该继续隔离",
        },
    )
    target = _enqueue(
        runtime,
        {
            "feishu_message_id": "target-msg",
            "chat_id": "chat",
            "root_id": "target-root",
            "thread_id": "target-root",
            "text": "我是说臭豆腐，你生成的是什么菜",
            "chatgpt_continuation_mode": True,
        },
    )
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            "UPDATE image2_jobs SET status = 'failed_retryable', updated_at = '2000-01-01T00:00:00+00:00' WHERE task_id = ?",
            (old["task_id"],),
        )

    result = run_worker(
        db_path=db_path,
        runtime_root=runtime,
        task_id=str(target["task_id"]),
        worker_id="worker-test",
        environ={},
    )

    assert result["task_id"] == target["task_id"]
    assert result["status"] == "failed_final"
    assert result["reason"] == "fail_closed_missing_generation_preflight"
    assert _row(db_path, str(target["task_id"]))["status"] == "failed_final"
    assert _row(db_path, str(old["task_id"]))["status"] == "failed_retryable"


def test_worker_reads_compiled_prompt_artifacts_before_fail_closed_preflight(tmp_path):
    runtime = tmp_path / "runtime"
    db_path = runtime / "image2_jobs.sqlite"
    job = _enqueue(
        runtime,
        {
            "feishu_message_id": "msg-1",
            "chat_id": "chat",
            "root_id": "root",
            "thread_id": "root",
            "text": "我是说臭豆腐，你生成的是什么菜",
            "chatgpt_continuation_mode": True,
        },
    )
    job_dir = Path(str(job["job_dir"]))
    assert "臭豆腐" in (job_dir / "prompt.txt").read_text(encoding="utf-8")

    result = run_worker(
        db_path=db_path,
        runtime_root=runtime,
        task_id=str(job["task_id"]),
        worker_id="worker-test",
        environ={},
    )

    result_path = job_dir / "worker_result.json"
    assert result_path.is_file()
    persisted = json.loads(result_path.read_text(encoding="utf-8"))
    assert persisted["task_id"] == job["task_id"]
    assert persisted["prompt_sha256"] == result["prompt_sha256"]
    assert persisted["prompt_artifacts"]["prompt_txt"] == str(job_dir / "prompt.txt")
    assert "臭豆腐" in persisted["prompt_excerpt"]
    assert "IMAGE2_WORKER_LIVE_ENABLED=1" in persisted["missing_preflight"]
    assert "OPENCLI_CDP_URL or CHATGPT_BROWSER_CDP_URL" in persisted["missing_preflight"]
    assert _row(db_path, str(job["task_id"]))["last_error"].startswith("fail_closed_missing_generation_preflight")


def test_worker_missing_compiled_prompt_is_terminal_and_does_not_invoke_generation(tmp_path):
    runtime = tmp_path / "runtime"
    db_path = runtime / "image2_jobs.sqlite"
    job = _enqueue(
        runtime,
        {
            "feishu_message_id": "msg-2",
            "chat_id": "chat",
            "root_id": "root",
            "thread_id": "root",
            "text": "做一张臭豆腐海报",
        },
    )
    job_dir = Path(str(job["job_dir"]))
    (job_dir / "prompt.txt").unlink()

    result = run_worker(
        db_path=db_path,
        runtime_root=runtime,
        task_id=str(job["task_id"]),
        worker_id="worker-test",
        environ={"IMAGE2_WORKER_LIVE_ENABLED": "1", "OPENCLI_CDP_URL": "ws://example", "GEMINI_API_KEY": "present"},
    )

    assert result["status"] == "failed_final"
    assert result["reason"] == "missing_prompt_artifact"
    assert _row(db_path, str(job["task_id"]))["status"] == "failed_final"
    assert "prompt.txt" in _row(db_path, str(job["task_id"]))["last_error"]
