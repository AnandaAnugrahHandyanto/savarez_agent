from __future__ import annotations

import json
import os
import time
from pathlib import Path

from gateway.image2_browser_preflight import evaluate_browser_preflight
from gateway.image2_candidate_gate import sha256_file
from gateway.image2_delivery_contract import evaluate_delivery_contract
from gateway.image2_review_gate import evaluate_review_gate
from gateway.image2_store import Image2JobStore
from gateway.image2_worker import run_worker


def _enqueue(runtime: Path, payload: dict[str, object]) -> dict[str, object]:
    return Image2JobStore(db_path=runtime / "image2_jobs.sqlite", runtime_root=runtime).enqueue_feishu(payload)


def _write_bytes(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return path


def test_browser_preflight_rejects_blank_chatgpt_tab_without_generation(tmp_path):
    job_dir = tmp_path / "job"

    result = evaluate_browser_preflight(
        job_dir=job_dir,
        environ={"OPENCLI_CDP_URL": "ws://127.0.0.1:9222/devtools/browser/test"},
        browser_state={"cdp_reachable": True, "active_url": "about:blank", "title": ""},
    )

    assert result["status"] == "failed"
    assert result["reasons"] == ["blank_or_new_tab"]
    assert result["cdp_url_present"] is True
    assert result["active_url"] == "about:blank"
    persisted = json.loads((job_dir / "browser_preflight_result.json").read_text(encoding="utf-8"))
    assert persisted["status"] == "failed"
    assert persisted["reasons"] == ["blank_or_new_tab"]


def test_browser_preflight_rejects_unreachable_cdp_before_generation(tmp_path):
    result = evaluate_browser_preflight(
        job_dir=tmp_path / "job",
        environ={"CHATGPT_BROWSER_CDP_URL": "ws://127.0.0.1:19222/devtools/browser/test"},
        browser_state={"cdp_reachable": False, "active_url": "https://chatgpt.com/images", "title": "ChatGPT Images"},
    )

    assert result["status"] == "failed"
    assert result["reasons"] == ["cdp_unreachable"]
    assert result["cdp_url_present"] is True


def test_review_gate_fails_closed_without_visual_review_result(tmp_path):
    candidate = _write_bytes(tmp_path / "candidate.png", b"candidate-image")

    result = evaluate_review_gate(
        job_dir=tmp_path / "job",
        candidate={"path": str(candidate), "sha256": sha256_file(candidate)},
        review_result=None,
    )

    assert result["status"] == "rejected"
    assert result["reasons"] == ["review_result_missing"]
    assert json.loads((tmp_path / "job" / "review_gate_result.json").read_text(encoding="utf-8"))["status"] == "rejected"


def test_review_gate_allows_pass_with_p2_but_blocks_p1_logo_or_brand_issue(tmp_path):
    candidate = _write_bytes(tmp_path / "candidate.png", b"candidate-image")
    candidate_record = {"path": str(candidate), "sha256": sha256_file(candidate)}

    pass_result = evaluate_review_gate(
        job_dir=tmp_path / "pass-job",
        candidate=candidate_record,
        review_result={"decision": "PASS_WITH_P2", "issues": [{"severity": "P2", "code": "minor_copy_tight"}]},
    )
    reject_result = evaluate_review_gate(
        job_dir=tmp_path / "reject-job",
        candidate=candidate_record,
        review_result={"decision": "PASS_WITH_P2", "issues": [{"severity": "P1", "code": "rendered_brand_text"}]},
    )

    assert pass_result["status"] == "pass"
    assert pass_result["decision"] == "PASS_WITH_P2"
    assert reject_result["status"] == "rejected"
    assert "p1_or_p0_review_issue" in reject_result["reasons"]


def test_delivery_contract_requires_review_pass_and_exact_thread_target(tmp_path):
    candidate = _write_bytes(tmp_path / "candidate.png", b"candidate-image")
    candidate_gate = {"status": "pass", "accepted": {"path": str(candidate), "sha256": sha256_file(candidate)}}

    missing_thread = evaluate_delivery_contract(
        job_dir=tmp_path / "missing-thread-job",
        message={"chat_id": "chat-id", "root_id": "", "thread_id": ""},
        candidate_gate=candidate_gate,
        review_gate={"status": "pass", "decision": "PASS"},
    )
    review_rejected = evaluate_delivery_contract(
        job_dir=tmp_path / "review-rejected-job",
        message={"chat_id": "chat-id", "root_id": "root-id", "thread_id": "root-id"},
        candidate_gate=candidate_gate,
        review_gate={"status": "rejected", "decision": "REJECT"},
    )

    assert missing_thread["status"] == "rejected"
    assert "missing_thread_or_root_id" in missing_thread["reasons"]
    assert review_rejected["status"] == "rejected"
    assert "review_gate_not_pass" in review_rejected["reasons"]


def test_worker_reaches_delivery_contract_after_browser_and_review_gate_and_still_does_not_send(tmp_path):
    runtime = tmp_path / "runtime"
    db_path = runtime / "image2_jobs.sqlite"
    job = _enqueue(
        runtime,
        {
            "feishu_message_id": "msg-worker-delivery-contract",
            "chat_id": "chat",
            "root_id": "root-message",
            "thread_id": "root-message",
            "text": "生成一张新的臭豆腐海报",
        },
    )
    job_dir = Path(str(job["job_dir"]))
    candidate = _write_bytes(job_dir / "candidates" / "fresh.png", b"fresh-worker-candidate")
    future = time.time() + 30
    os.utime(candidate, (future, future))
    browser_state_path = _write_json(
        job_dir / "browser_state.json",
        {"cdp_reachable": True, "active_url": "https://chatgpt.com/images", "title": "ChatGPT Images"},
    )
    _write_json(job_dir / "review_result.json", {"decision": "PASS", "issues": []})

    result = run_worker(
        db_path=db_path,
        runtime_root=runtime,
        task_id=str(job["task_id"]),
        worker_id="worker-delivery-contract-test",
        environ={
            "IMAGE2_WORKER_LIVE_ENABLED": "1",
            "OPENCLI_CDP_URL": "ws://127.0.0.1:9222/devtools/browser/test",
            "IMAGE2_BROWSER_STATE_JSON": str(browser_state_path),
            "IMAGE2_REVIEWER_PROVIDER": "stub-present",
        },
    )

    assert result["status"] == "failed_final"
    assert result["reason"] == "delivery_contract_ready_send_not_implemented"
    assert result["browser_preflight"]["status"] == "pass"
    assert result["candidate_gate"]["status"] == "pass"
    assert result["review_gate"]["status"] == "pass"
    assert result["delivery_contract"]["status"] == "ready_to_send"
    assert result["delivery_contract"]["sent"] is False
    assert not (job_dir / "delivery_result.json").exists()
    assert json.loads((job_dir / "delivery_plan.json").read_text(encoding="utf-8"))["sent"] is False
