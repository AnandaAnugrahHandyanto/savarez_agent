#!/usr/bin/env python3
"""Validate Hermes ↔ OpenClaw A2A v2.6.0 mock fixtures.

This validator is intentionally offline-only: it must not call OpenClaw,
Hermes gateway, cron, webhooks, or platform senders. It checks the local
controller/worker contract fixtures before any live two-worker sample.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

FORBIDDEN_SECRET_PATTERNS = [
    re.compile(r"Authorization\s*:", re.IGNORECASE),
    re.compile(r"Bearer\s+\S+", re.IGNORECASE),
    re.compile(r"api[_-]?key\s*[:=]", re.IGNORECASE),
    re.compile(r"password\s*[:=]", re.IGNORECASE),
    re.compile(r"secret\s*[:=]", re.IGNORECASE),
]

DISPATCH_REQUIRED = {
    "schema_version": str,
    "task_id": str,
    "source_agent": str,
    "target_agent": str,
    "goal": str,
    "context": str,
    "allowed_actions": list,
    "forbidden_actions": list,
    "expected_outputs": list,
    "acceptance_criteria": list,
    "stop_conditions": list,
}

RECEIPT_REQUIRED = {
    "schema_version": str,
    "ok": bool,
    "task_id": str,
    "source_agent": str,
    "target_agent": str,
    "protocol": str,
    "http_status": int,
    "remote_task_id": str,
    "remote_context_id": str,
    "state": str,
    "marker": str,
    "artifact_text_preview": str,
    "evidence_path": str,
    "auth": dict,
}

ACCEPTANCE_REQUIRED = {
    "schema_version": str,
    "run_id": str,
    "overall": str,
    "items": list,
    "secret_scan": dict,
    "external_side_effects": dict,
    "next_step": str,
}

ALLOWED_ACCEPTANCE = {"accepted", "accepted_with_boundary", "rejected", "blocked", "unsafe"}


def fail(errors: list[str], msg: str) -> None:
    errors.append(msg)


def load_json(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - validation script reports exact parse failure
        fail(errors, f"{path}: JSON parse failed: {exc}")
        return {}
    if not isinstance(data, dict):
        fail(errors, f"{path}: root must be object")
        return {}
    return data


def validate_required(name: str, data: dict[str, Any], required: dict[str, type], errors: list[str]) -> None:
    for key, typ in required.items():
        if key not in data:
            fail(errors, f"{name}: missing required field {key}")
            continue
        if not isinstance(data[key], typ):
            fail(errors, f"{name}: field {key} must be {typ.__name__}")


def scan_text(path: Path, text: str, errors: list[str]) -> None:
    for pattern in FORBIDDEN_SECRET_PATTERNS:
        match = pattern.search(text)
        if match:
            fail(errors, f"{path}: forbidden secret-like literal matched {pattern.pattern!r}")


def scan_tree(base: Path, errors: list[str]) -> None:
    for path in sorted(base.glob("*")):
        if path.is_file():
            scan_text(path, path.read_text(encoding="utf-8", errors="replace"), errors)


def validate_dispatch(path: Path, errors: list[str]) -> dict[str, Any]:
    data = load_json(path, errors)
    validate_required(path.name, data, DISPATCH_REQUIRED, errors)
    if data.get("schema_version") != "a2a-dispatch-envelope-v1":
        fail(errors, f"{path.name}: schema_version must be a2a-dispatch-envelope-v1")
    if data.get("source_agent") != "hermes":
        fail(errors, f"{path.name}: source_agent must be hermes")
    forbidden = "\n".join(data.get("forbidden_actions", []))
    for marker in ["restart", "cron", "webhook", "secrets", "platform messages"]:
        if marker not in forbidden.lower():
            fail(errors, f"{path.name}: forbidden_actions should explicitly include boundary marker {marker!r}")
    if not data.get("task_id", "").startswith("a2a-v260-"):
        fail(errors, f"{path.name}: task_id must start with a2a-v260-")
    return data


def validate_receipt(path: Path, dispatches: dict[str, dict[str, Any]], errors: list[str]) -> dict[str, Any]:
    data = load_json(path, errors)
    validate_required(path.name, data, RECEIPT_REQUIRED, errors)
    if data.get("schema_version") != "a2a-worker-receipt-v1":
        fail(errors, f"{path.name}: schema_version must be a2a-worker-receipt-v1")
    task_id = data.get("task_id")
    if task_id not in dispatches:
        fail(errors, f"{path.name}: task_id {task_id!r} has no matching dispatch")
    if data.get("ok") is not True:
        fail(errors, f"{path.name}: ok must be true for positive mock fixture")
    if data.get("state") != "completed":
        fail(errors, f"{path.name}: state must be completed")
    if data.get("http_status") != 200:
        fail(errors, f"{path.name}: http_status must be 200")
    auth = data.get("auth") if isinstance(data.get("auth"), dict) else {}
    if auth.get("token_recorded") is not False:
        fail(errors, f"{path.name}: auth.token_recorded must be false")
    marker = data.get("marker", "")
    evidence_path = Path(data.get("evidence_path", ""))
    if not evidence_path.exists():
        fail(errors, f"{path.name}: evidence_path missing: {evidence_path}")
    else:
        evidence = evidence_path.read_text(encoding="utf-8", errors="replace")
        if marker not in evidence:
            fail(errors, f"{path.name}: marker {marker!r} not found in evidence_path")
    return data


def validate_acceptance(path: Path, receipts: dict[str, dict[str, Any]], errors: list[str]) -> dict[str, Any]:
    data = load_json(path, errors)
    validate_required(path.name, data, ACCEPTANCE_REQUIRED, errors)
    if data.get("schema_version") != "a2a-acceptance-report-v1":
        fail(errors, f"{path.name}: schema_version must be a2a-acceptance-report-v1")
    if data.get("overall") not in ALLOWED_ACCEPTANCE:
        fail(errors, f"{path.name}: invalid overall classification")
    for item in data.get("items", []):
        if not isinstance(item, dict):
            fail(errors, f"{path.name}: each item must be object")
            continue
        if item.get("task_id") not in receipts:
            fail(errors, f"{path.name}: item task_id {item.get('task_id')!r} has no matching receipt")
        if item.get("classification") not in ALLOWED_ACCEPTANCE:
            fail(errors, f"{path.name}: item {item.get('task_id')} invalid classification")
    secret_scan = data.get("secret_scan", {})
    if secret_scan.get("ok") is not True or secret_scan.get("token_recorded") is not False:
        fail(errors, f"{path.name}: secret_scan must assert ok=true and token_recorded=false")
    effects = data.get("external_side_effects", {})
    for key in ["gateway_restart", "openclaw_restart", "cron_enabled", "platform_send", "live_a2a_call"]:
        if effects.get(key) is not False:
            fail(errors, f"{path.name}: external_side_effects.{key} must be false")
    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture-dir", default="examples/v2.6.0/mock-fixtures")
    parser.add_argument("--write-summary", default="")
    args = parser.parse_args()

    base = Path(args.fixture_dir)
    errors: list[str] = []
    if not base.is_dir():
        fail(errors, f"fixture dir missing: {base}")
    else:
        scan_tree(base, errors)

    dispatch_paths = [base / "dispatch-worker-readiness.json", base / "dispatch-worker-review.json"]
    receipt_paths = [base / "receipt-worker-readiness.json", base / "receipt-worker-review.json"]
    acceptance_path = base / "acceptance-report.json"

    dispatches = {d.get("task_id", f"missing:{path.name}"): d for path in dispatch_paths for d in [validate_dispatch(path, errors)] if d}
    receipts = {r.get("task_id", f"missing:{path.name}"): r for path in receipt_paths for r in [validate_receipt(path, dispatches, errors)] if r}
    acceptance = validate_acceptance(acceptance_path, receipts, errors)

    summary = {
        "ok": not errors,
        "fixture_dir": str(base),
        "dispatch_count": len(dispatches),
        "receipt_count": len(receipts),
        "acceptance_overall": acceptance.get("overall"),
        "errors": errors,
        "side_effects": {
            "live_a2a_call": False,
            "gateway_restart": False,
            "openclaw_restart": False,
            "cron_enabled": False,
            "platform_send": False,
        },
    }
    if args.write_summary:
        Path(args.write_summary).write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
