from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from gateway.image2_candidate_gate import evaluate_candidate_gate, sha256_file
from gateway.image2_store import Image2JobStore
from gateway.image2_worker import run_worker


def _enqueue(runtime: Path, payload: dict[str, object]) -> dict[str, object]:
    return Image2JobStore(db_path=runtime / "image2_jobs.sqlite", runtime_root=runtime).enqueue_feishu(payload)


def _write_bytes(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def test_candidate_gate_rejects_exact_source_echo_by_sha(tmp_path):
    runtime = tmp_path / "runtime"
    source = _write_bytes(tmp_path / "source.jpg", b"same-bytes-as-user-source")
    source_sha = sha256_file(source)
    job = _enqueue(
        runtime,
        {
            "feishu_message_id": "msg-source",
            "chat_id": "chat",
            "root_id": "root",
            "thread_id": "root",
            "text": "按这张图重做海报",
            "source_files": [
                {
                    "source": "feishu_thread_root_image",
                    "path": str(source),
                    "sha256": source_sha,
                }
            ],
        },
    )
    job_dir = Path(str(job["job_dir"]))
    candidate = _write_bytes(job_dir / "candidates" / "candidate-source-echo.png", source.read_bytes())

    result = evaluate_candidate_gate(job_dir=job_dir, candidate_paths=[candidate])

    assert result["status"] == "rejected"
    assert result["accepted"] is None
    assert result["source_sha256"] == [source_sha]
    assert result["decisions"][0]["decision"] == "reject"
    assert result["decisions"][0]["reasons"] == ["source_sha_match"]
    assert json.loads((job_dir / "candidate_gate_result.json").read_text(encoding="utf-8"))["status"] == "rejected"


def test_candidate_gate_rejects_plain_string_source_manifest_paths(tmp_path):
    runtime = tmp_path / "runtime"
    source = _write_bytes(tmp_path / "direct-source.png", b"plain-string-source")
    source_sha = sha256_file(source)
    job = _enqueue(
        runtime,
        {
            "feishu_message_id": "msg-source-string",
            "chat_id": "chat",
            "root_id": "root",
            "thread_id": "root",
            "text": "按这张图重做海报",
            "source_files": [str(source)],
        },
    )
    job_dir = Path(str(job["job_dir"]))
    candidate = _write_bytes(job_dir / "candidates" / "candidate-source-echo.png", source.read_bytes())

    result = evaluate_candidate_gate(job_dir=job_dir, candidate_paths=[candidate])

    assert result["status"] == "rejected"
    assert result["source_sha256"] == [source_sha]
    assert result["decisions"][0]["reasons"] == ["source_sha_match"]


def test_candidate_gate_rejects_historical_sha_even_when_file_path_is_new(tmp_path):
    runtime = tmp_path / "runtime"
    job = _enqueue(
        runtime,
        {
            "feishu_message_id": "msg-history",
            "chat_id": "chat",
            "root_id": "root",
            "thread_id": "root",
            "text": "重新生成一张，不要发旧图",
        },
    )
    job_dir = Path(str(job["job_dir"]))
    historical = _write_bytes(tmp_path / "old-gallery.png", b"old-gallery-image")
    historical_sha = sha256_file(historical)
    (job_dir / "history_sha256.json").write_text(json.dumps([historical_sha]), encoding="utf-8")
    candidate = _write_bytes(job_dir / "candidates" / "new-name-same-old-image.png", historical.read_bytes())

    result = evaluate_candidate_gate(job_dir=job_dir, candidate_paths=[candidate])

    assert result["status"] == "rejected"
    assert result["accepted"] is None
    assert result["historical_sha256"] == [historical_sha]
    assert result["decisions"][0]["reasons"] == ["historical_sha_match"]


def test_candidate_gate_rejects_stale_mtime_and_accepts_fresh_non_matching_candidate(tmp_path):
    runtime = tmp_path / "runtime"
    job = _enqueue(
        runtime,
        {
            "feishu_message_id": "msg-fresh",
            "chat_id": "chat",
            "root_id": "root",
            "thread_id": "root",
            "text": "生成一张全新的臭豆腐海报",
        },
    )
    job_dir = Path(str(job["job_dir"]))
    stale = _write_bytes(job_dir / "candidates" / "stale.png", b"stale-candidate")
    fresh = _write_bytes(job_dir / "candidates" / "fresh.png", b"fresh-candidate")
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=30)
    os.utime(stale, (cutoff.timestamp() - 60, cutoff.timestamp() - 60))
    os.utime(fresh, (cutoff.timestamp() + 60, cutoff.timestamp() + 60))

    result = evaluate_candidate_gate(job_dir=job_dir, candidate_paths=[stale, fresh], generated_after=cutoff)

    assert result["status"] == "pass"
    assert result["accepted"]["path"] == str(fresh)
    decisions = {Path(item["path"]).name: item for item in result["decisions"]}
    assert decisions["stale.png"]["decision"] == "reject"
    assert decisions["stale.png"]["reasons"] == ["stale_mtime_before_generation_start"]
    assert decisions["fresh.png"]["decision"] == "pass"
    assert decisions["fresh.png"]["reasons"] == []


def test_worker_runs_candidate_gate_before_delivery_and_fails_closed_without_feishu_credentials(tmp_path):
    runtime = tmp_path / "runtime"
    db_path = runtime / "image2_jobs.sqlite"
    job = _enqueue(
        runtime,
        {
            "feishu_message_id": "msg-worker-gate",
            "chat_id": "chat",
            "root_id": "root",
            "thread_id": "root",
            "text": "生成一张新的臭豆腐海报",
        },
    )
    job_dir = Path(str(job["job_dir"]))
    candidate = _write_bytes(job_dir / "candidates" / "fresh.png", b"fresh-worker-candidate")
    future = datetime.now(timezone.utc).timestamp() + 30
    os.utime(candidate, (future, future))
    (job_dir / "browser_state.json").write_text(
        json.dumps({"cdp_reachable": True, "active_url": "https://chatgpt.com/images", "title": "ChatGPT Images"}),
        encoding="utf-8",
    )
    (job_dir / "review_result.json").write_text(json.dumps({"decision": "PASS", "issues": []}), encoding="utf-8")

    result = run_worker(
        db_path=db_path,
        runtime_root=runtime,
        task_id=str(job["task_id"]),
        worker_id="worker-candidate-gate-test",
        environ={
            "IMAGE2_WORKER_LIVE_ENABLED": "1",
            "OPENCLI_CDP_URL": "ws://example.invalid/devtools/browser/test",
            "IMAGE2_REVIEWER_PROVIDER": "stub-present",
        },
    )

    assert result["status"] == "failed_final"
    assert result["reason"] == "delivery_preflight_missing"
    assert result["browser_preflight"]["status"] == "pass"
    assert result["candidate_gate"]["status"] == "pass"
    assert result["candidate_gate"]["accepted"]["path"] == str(candidate)
    assert result["review_gate"]["status"] == "pass"
    assert result["delivery_contract"]["status"] == "ready_to_send"
    assert result["delivery_contract"]["sent"] is False
    gate_result = json.loads((job_dir / "candidate_gate_result.json").read_text(encoding="utf-8"))
    assert gate_result["accepted"]["sha256"] == sha256_file(candidate)
    worker_result = json.loads((job_dir / "worker_result.json").read_text(encoding="utf-8"))
    assert worker_result["reason"] == "delivery_preflight_missing"
    assert worker_result["candidate_gate"]["status"] == "pass"


def test_worker_candidate_freshness_uses_claimed_at_not_original_enqueue_time(tmp_path):
    runtime = tmp_path / "runtime"
    db_path = runtime / "image2_jobs.sqlite"
    job = _enqueue(
        runtime,
        {
            "feishu_message_id": "msg-worker-claimed-at",
            "chat_id": "chat",
            "root_id": "root",
            "thread_id": "root",
            "text": "生成一张新的臭豆腐海报",
        },
    )
    job_dir = Path(str(job["job_dir"]))
    candidate = _write_bytes(job_dir / "candidates" / "preclaim.png", b"candidate-before-worker-claim")
    preclaim_time = datetime.now(timezone.utc) - timedelta(seconds=60)
    os.utime(candidate, (preclaim_time.timestamp(), preclaim_time.timestamp()))
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            "UPDATE image2_jobs SET created_at = '2000-01-01T00:00:00+00:00', updated_at = '2000-01-01T00:00:00+00:00' WHERE task_id = ?",
            (job["task_id"],),
        )
    (job_dir / "browser_state.json").write_text(
        json.dumps({"cdp_reachable": True, "active_url": "https://chatgpt.com/images", "title": "ChatGPT Images"}),
        encoding="utf-8",
    )

    result = run_worker(
        db_path=db_path,
        runtime_root=runtime,
        task_id=str(job["task_id"]),
        worker_id="worker-claimed-at-test",
        environ={
            "IMAGE2_WORKER_LIVE_ENABLED": "1",
            "OPENCLI_CDP_URL": "ws://example.invalid/devtools/browser/test",
            "IMAGE2_REVIEWER_PROVIDER": "stub-present",
        },
    )

    assert result["reason"] == "candidate_gate_rejected"
    assert result["candidate_gate"]["status"] == "rejected"
    assert result["candidate_gate"]["decisions"][0]["reasons"] == ["stale_mtime_before_generation_start"]
