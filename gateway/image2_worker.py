"""Hermes-owned Feishu Image2 worker entrypoint.

The legacy live worker was ``marketing-hub/scripts/image2_browser_worker.py``.
This module deliberately stays inside Hermes: it claims the exact task launched
by ingress, reads the Hermes-owned prompt artifacts, and fails closed before any
browser/OpenCLI/ChatGPT/Gemini work unless the later live-generation gate is
explicitly implemented and enabled.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping

from gateway.image2_browser_preflight import evaluate_browser_preflight
from gateway.image2_candidate_gate import evaluate_candidate_gate
from gateway.image2_delivery_contract import evaluate_delivery_contract
from gateway.image2_review_gate import evaluate_review_gate
from gateway.image2_store import Image2JobStore


LIVE_ENABLE_ENV = "IMAGE2_WORKER_LIVE_ENABLED"
BROWSER_ENV_OPTIONS = ("OPENCLI_CDP_URL", "CHATGPT_BROWSER_CDP_URL")
REVIEWER_ENV_OPTIONS = ("GEMINI_API_KEY", "GOOGLE_API_KEY", "IMAGE2_REVIEWER_PROVIDER")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Hermes-owned Image2 worker")
    parser.add_argument("--db", required=True)
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--worker-id", required=True)
    parser.add_argument("--task-id", required=True)
    return parser


def _enabled(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _has_any(environ: Mapping[str, str], keys: tuple[str, ...]) -> bool:
    return any(str(environ.get(key) or "").strip() for key in keys)


def missing_live_preflight(environ: Mapping[str, str]) -> list[str]:
    """Return missing non-secret live-generation gates without exposing values."""
    missing: list[str] = []
    if not _enabled(environ.get(LIVE_ENABLE_ENV)):
        missing.append(f"{LIVE_ENABLE_ENV}=1")
    if not _has_any(environ, BROWSER_ENV_OPTIONS):
        missing.append("OPENCLI_CDP_URL or CHATGPT_BROWSER_CDP_URL")
    if not _has_any(environ, REVIEWER_ENV_OPTIONS):
        missing.append("GEMINI_API_KEY or GOOGLE_API_KEY or IMAGE2_REVIEWER_PROVIDER")
    return missing


def _safe_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return dict(value) if isinstance(value, Mapping) else {}


def _prompt_artifacts(job: Mapping[str, Any], runtime_root: Path) -> dict[str, Any]:
    task_id = str(job.get("task_id") or "")
    job_dir = Path(str(job.get("job_dir") or runtime_root / task_id)).expanduser()
    prompt_path = job_dir / "prompt.txt"
    compiled_path = job_dir / "compiled_prompt.json"
    brief_path = job_dir / "brief.json"
    message_path = job_dir / "message.json"
    return {
        "job_dir": job_dir,
        "prompt_txt": prompt_path,
        "compiled_prompt_json": compiled_path,
        "brief_json": brief_path,
        "message_json": message_path,
    }


def _read_artifacts(job: Mapping[str, Any], runtime_root: Path) -> dict[str, Any]:
    artifacts = _prompt_artifacts(job, runtime_root)
    prompt_path: Path = artifacts["prompt_txt"]
    if not prompt_path.is_file():
        raise FileNotFoundError(str(prompt_path))
    prompt_text = prompt_path.read_text(encoding="utf-8")
    if not prompt_text.strip():
        raise ValueError(f"empty prompt artifact: {prompt_path}")
    compiled_path: Path = artifacts["compiled_prompt_json"]
    compiled = _load_json(compiled_path)
    return {
        "job_dir": str(artifacts["job_dir"]),
        "prompt_text": prompt_text,
        "prompt_sha256": hashlib.sha256(prompt_text.encode("utf-8")).hexdigest(),
        "compiled_prompt": compiled,
        "prompt_artifacts": {key: str(value) for key, value in artifacts.items() if key != "job_dir"},
    }


def _write_worker_result(job_dir: Path, payload: Mapping[str, Any]) -> None:
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "worker_result.json").write_text(_safe_json(dict(payload)), encoding="utf-8")


def _terminal_failure(
    *,
    store: Image2JobStore,
    task_id: str,
    worker_id: str,
    job_dir: Path,
    reason: str,
    last_error: str,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    row = store.mark_failed_final(task_id=task_id, worker_id=worker_id, last_error=last_error) or {}
    result = {
        "task_id": task_id,
        "worker_id": worker_id,
        "status": "failed_final",
        "reason": reason,
        "last_error": last_error,
        "exit_code": 3,
        "db_status": row.get("status"),
    }
    if extra:
        result.update(dict(extra))
    _write_worker_result(job_dir, result)
    return result


def run_worker(
    *,
    db_path: Path,
    runtime_root: Path,
    task_id: str,
    worker_id: str,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Claim and preflight exactly one Image2 task.

    This first worker slice intentionally performs no browser, OpenCLI, ChatGPT,
    Gemini, candidate-review, or Feishu delivery side effects.  It makes the
    durable queue safer by proving that a launched worker only touches the task
    ingress launched it for, reads compiled Hermes prompt artifacts, and records
    a terminal fail-closed result when live-generation prerequisites are missing.
    """
    env = dict(environ if environ is not None else os.environ)
    runtime = Path(runtime_root)
    store = Image2JobStore(db_path=Path(db_path), runtime_root=runtime)
    claimed = store.claim_task(task_id=str(task_id), worker_id=str(worker_id))
    if not claimed:
        return {
            "task_id": str(task_id),
            "worker_id": str(worker_id),
            "status": "not_claimed",
            "reason": "task_not_claimable",
            "exit_code": 1,
        }

    fallback_job_dir = runtime / str(task_id)
    try:
        artifact_info = _read_artifacts(claimed, runtime)
    except Exception as exc:
        return _terminal_failure(
            store=store,
            task_id=str(task_id),
            worker_id=str(worker_id),
            job_dir=Path(str(claimed.get("job_dir") or fallback_job_dir)),
            reason="missing_prompt_artifact",
            last_error=f"missing_prompt_artifact: {exc}",
            extra={"exit_code": 2},
        )

    job_dir = Path(str(artifact_info["job_dir"]))
    missing = missing_live_preflight(env)
    if missing:
        return _terminal_failure(
            store=store,
            task_id=str(task_id),
            worker_id=str(worker_id),
            job_dir=job_dir,
            reason="fail_closed_missing_generation_preflight",
            last_error="fail_closed_missing_generation_preflight: " + ", ".join(missing),
            extra={
                "missing_preflight": missing,
                "prompt_sha256": artifact_info["prompt_sha256"],
                "prompt_excerpt": str(artifact_info["prompt_text"])[0:240],
                "prompt_artifacts": artifact_info["prompt_artifacts"],
                "exit_code": 3,
            },
        )

    browser_preflight = evaluate_browser_preflight(job_dir=job_dir, environ=env)
    if browser_preflight.get("status") != "pass":
        reasons = ", ".join(str(reason) for reason in browser_preflight.get("reasons", []))
        return _terminal_failure(
            store=store,
            task_id=str(task_id),
            worker_id=str(worker_id),
            job_dir=job_dir,
            reason="browser_preflight_failed",
            last_error="browser_preflight_failed: " + reasons,
            extra={
                "browser_preflight": browser_preflight,
                "prompt_sha256": artifact_info["prompt_sha256"],
                "prompt_excerpt": str(artifact_info["prompt_text"])[0:240],
                "prompt_artifacts": artifact_info["prompt_artifacts"],
                "exit_code": 4,
            },
        )

    try:
        candidate_gate = evaluate_candidate_gate(
            job_dir=job_dir,
            generated_after=claimed.get("claimed_at") or claimed.get("created_at"),
        )
    except Exception as exc:
        return _terminal_failure(
            store=store,
            task_id=str(task_id),
            worker_id=str(worker_id),
            job_dir=job_dir,
            reason="candidate_gate_error",
            last_error=f"candidate_gate_error: {exc}",
            extra={
                "prompt_sha256": artifact_info["prompt_sha256"],
                "prompt_excerpt": str(artifact_info["prompt_text"])[0:240],
                "prompt_artifacts": artifact_info["prompt_artifacts"],
                "exit_code": 5,
            },
        )
    if candidate_gate.get("status") == "rejected":
        rejected_reasons = sorted({
            reason
            for decision in candidate_gate.get("decisions", [])
            for reason in decision.get("reasons", [])
        })
        return _terminal_failure(
            store=store,
            task_id=str(task_id),
            worker_id=str(worker_id),
            job_dir=job_dir,
            reason="candidate_gate_rejected",
            last_error="candidate_gate_rejected: " + ", ".join(rejected_reasons),
            extra={
                "candidate_gate": candidate_gate,
                "prompt_sha256": artifact_info["prompt_sha256"],
                "prompt_excerpt": str(artifact_info["prompt_text"])[0:240],
                "prompt_artifacts": artifact_info["prompt_artifacts"],
                "exit_code": 5,
            },
        )
    if candidate_gate.get("status") == "pass":
        review_gate = evaluate_review_gate(job_dir=job_dir, candidate=candidate_gate.get("accepted"))
        if review_gate.get("status") != "pass":
            reasons = ", ".join(str(reason) for reason in review_gate.get("reasons", []))
            return _terminal_failure(
                store=store,
                task_id=str(task_id),
                worker_id=str(worker_id),
                job_dir=job_dir,
                reason="review_gate_rejected",
                last_error="review_gate_rejected: " + reasons,
                extra={
                    "browser_preflight": browser_preflight,
                    "candidate_gate": candidate_gate,
                    "review_gate": review_gate,
                    "prompt_sha256": artifact_info["prompt_sha256"],
                    "prompt_excerpt": str(artifact_info["prompt_text"])[0:240],
                    "prompt_artifacts": artifact_info["prompt_artifacts"],
                    "exit_code": 5,
                },
            )

        message = _load_json(job_dir / "message.json")
        delivery_contract = evaluate_delivery_contract(
            job_dir=job_dir,
            message=message,
            candidate_gate=candidate_gate,
            review_gate=review_gate,
        )
        if delivery_contract.get("status") != "ready_to_send":
            reasons = ", ".join(str(reason) for reason in delivery_contract.get("reasons", []))
            return _terminal_failure(
                store=store,
                task_id=str(task_id),
                worker_id=str(worker_id),
                job_dir=job_dir,
                reason="delivery_contract_rejected",
                last_error="delivery_contract_rejected: " + reasons,
                extra={
                    "browser_preflight": browser_preflight,
                    "candidate_gate": candidate_gate,
                    "review_gate": review_gate,
                    "delivery_contract": delivery_contract,
                    "prompt_sha256": artifact_info["prompt_sha256"],
                    "prompt_excerpt": str(artifact_info["prompt_text"])[0:240],
                    "prompt_artifacts": artifact_info["prompt_artifacts"],
                    "exit_code": 5,
                },
            )

        return _terminal_failure(
            store=store,
            task_id=str(task_id),
            worker_id=str(worker_id),
            job_dir=job_dir,
            reason="delivery_contract_ready_send_not_implemented",
            last_error="delivery_contract_ready_send_not_implemented: native Feishu send/read-back implementation is pending",
            extra={
                "browser_preflight": browser_preflight,
                "candidate_gate": candidate_gate,
                "review_gate": review_gate,
                "delivery_contract": delivery_contract,
                "prompt_sha256": artifact_info["prompt_sha256"],
                "prompt_excerpt": str(artifact_info["prompt_text"])[0:240],
                "prompt_artifacts": artifact_info["prompt_artifacts"],
                "exit_code": 5,
            },
        )

    return _terminal_failure(
        store=store,
        task_id=str(task_id),
        worker_id=str(worker_id),
        job_dir=job_dir,
        reason="live_generation_not_implemented",
        last_error="live_generation_not_implemented: browser/candidate gate/native delivery slices are pending",
        extra={
            "prompt_sha256": artifact_info["prompt_sha256"],
            "prompt_excerpt": str(artifact_info["prompt_text"])[0:240],
            "prompt_artifacts": artifact_info["prompt_artifacts"],
            "exit_code": 4,
        },
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_worker(
        db_path=Path(args.db),
        runtime_root=Path(args.runtime_root),
        worker_id=str(args.worker_id),
        task_id=str(args.task_id),
        environ=os.environ,
    )
    print(_safe_json(result), file=sys.stderr)
    return int(result.get("exit_code") or 0)


if __name__ == "__main__":  # pragma: no cover - CLI guard
    raise SystemExit(main())
