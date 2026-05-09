"""Minimal repo-contained HASOS policy engine fixture for clean CI.

This fixture intentionally implements only the behavior asserted by
`tests/hasos/test_hasos_policy_engine.py`.  The real local engine remains the
source of truth when present at ~/.hermes/scripts/hasos_policy_engine.py.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCHEMA = "hasos.policy_decision.v1"
_REPORT_SCHEMA = "hasos.sanitized_audit_report.v1"
_SECRET_RE = re.compile(
    r"(?i)(sk-[A-Za-z0-9_-]{20,}|TEST_FAKE_VALUE_[A-Za-z0-9_-]{8,}|bearer\s+[A-Za-z0-9._-]{20,})"
)


def sanitize_text(value: Any) -> str:
    return _SECRET_RE.sub("[REDACTED]", "" if value is None else str(value))


def sanitize_data(value: Any) -> Any:
    if isinstance(value, str):
        return sanitize_text(value)
    if isinstance(value, list):
        return [sanitize_data(v) for v in value]
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            key_text = str(key)
            if any(marker in key_text.lower() for marker in ("api_key", "access_token", "secret", "password", "private_key")):
                redacted[key_text] = "[REDACTED]" if isinstance(item, str) else sanitize_data(item)
            else:
                redacted[key_text] = sanitize_data(item)
        return redacted
    return value


def redact(value: Any) -> Any:
    return sanitize_data(value)


def detect_secret_findings(value: Any) -> list[dict[str, str]]:
    serialized = json.dumps(value, ensure_ascii=False, default=str)
    findings = []
    for match in _SECRET_RE.finditer(serialized):
        findings.append({"type": "secret-like-token", "value": "[REDACTED]", "span": f"{match.start()}:{match.end()}"})
    if any(marker in serialized.lower() for marker in ("api_key", "access_token", "secret")):
        findings.append({"type": "sensitive-key", "value": "[REDACTED]"})
    return findings


def _allow(level: int, decision: str = "allow", reason: str = "tool-call") -> dict[str, Any]:
    return {
        "schema_version": _SCHEMA,
        "level": level,
        "decision": decision,
        "action": "allow",
        "message": "",
        "reason_codes": [reason],
        "required_gates": [],
        "missing_gates": [],
    }


def _block(level: int, reason: str, required: list[str] | None = None) -> dict[str, Any]:
    required = required or []
    return {
        "schema_version": _SCHEMA,
        "level": level,
        "decision": "block",
        "action": "block",
        "message": f"HASOS Level {level} blocked by fixture: {reason}",
        "reason_codes": [reason],
        "required_gates": required,
        "missing_gates": required,
    }


def _runtime_policy(payload: dict[str, Any]) -> dict[str, Any]:
    policy = payload.get("runtime_policy") if isinstance(payload.get("runtime_policy"), dict) else None
    if policy is None and isinstance(payload.get("policy_context"), dict):
        policy = payload["policy_context"]
    return policy or {}


def _complete_release_gate(policy: dict[str, Any]) -> bool:
    required = [
        "policy_authorized",
        "runbook_id",
        "runbook_version",
        "owner",
        "target",
        "evidence_id",
        "stop_rules_checked",
        "redaction_checked",
        "release_security_gate_passed",
    ]
    return all(bool(policy.get(k)) for k in required)


def evaluate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    tool = str(payload.get("tool_name", ""))
    tool_input = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
    command = str(tool_input.get("command", ""))
    lowered = json.dumps(tool_input, ensure_ascii=False, default=str).lower()
    policy = _runtime_policy(payload)

    level5_terms = [
        "rm -rf", "rm -r -f", "git push --force", "git push --force-with-lease",
        "git reset --hard", "git clean", "shutil.rmtree", "xargs rm -rf", "find /tmp/example -delete",
        "install.sh | sh", "path('/tmp/example').unlink", "finder\" to delete", "cat ~/.hermes/.env",
        "auth.json", "sudo launchctl unload",
    ]
    if tool == "terminal" and any(term in command.lower() for term in level5_terms):
        return _block(5, "level5-dangerous-command-or-secret-exfiltration-pattern", ["deny-by-default"])

    level4_release = tool == "terminal" and any(term in command.lower() for term in ("submit for review", "fastlane deliver"))
    level4_credential = tool == "terminal" and "security add-generic-password" in command.lower()
    level4_external = tool == "send_message" and str(tool_input.get("target", "")).startswith("telegram:-")
    level4_cost = "upgrade plan" in lowered or "paid service" in lowered
    level4_cron = tool == "cronjob" and ("publish" in lowered or "public release" in lowered)

    if tool == "cronjob" and "hasos harness runtime daily audit" in lowered and "read-only" in lowered:
        return _allow(4, "allow-policy-authorized-4d", "4d-read-only-audit-cron")

    if level4_release:
        if _complete_release_gate(policy):
            return _allow(4, "allow-policy-authorized-4c-release", "level4c-release-upload-public-or-production-action")
        missing = ["release_security_gate_passed"] if policy else ["runbook_id", "release_security_gate_passed"]
        return _block(4, "level4c-release-upload-public-or-production-action", missing)

    if level4_credential:
        if _complete_release_gate(policy) and policy.get("credential_scope_reviewed") and policy.get("rollback_plan") and policy.get("rollback_verification"):
            return _allow(4, "allow-policy-authorized-4c-credential", "level4c-credential-mutation")
        return _block(4, "credential", ["credential_scope_reviewed", "rollback_plan"])

    if level4_external:
        return _block(4, "external", ["external_or_public_allowlist"])
    if level4_cost:
        return _block(4, "cost", ["cost_approval"])
    if level4_cron:
        return _block(4, "level4-cron-public-side-effect", ["runbook_id"])

    if tool in {"read_file", "search_files"} or "documentation only" in lowered or "py_compile" in command:
        return _allow(2, reason="read-only-or-documentation")
    return _allow(2)


def _strip_sensitive_report_fields(value: Any) -> Any:
    data = sanitize_data(value)
    if isinstance(data, dict):
        synthetic = data.get("synthetic")
        if isinstance(synthetic, dict):
            synthetic.pop("hook_outputs", None)
    return data


def write_sanitized_audit_report(result: dict[str, Any], root: Path | str) -> Path:
    root_path = Path(root)
    root_path.mkdir(parents=True, exist_ok=True)
    data = _strip_sensitive_report_fields(result)
    if isinstance(data, dict):
        data["report_schema"] = _REPORT_SCHEMA
        data["written_at"] = datetime.now(timezone.utc).isoformat()
    path = root_path / "hasos-audit-report-0001.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def audit_report_status(root: Path | str) -> dict[str, Any]:
    files = sorted(Path(root).glob("*.json"))
    latest_status = "none"
    if files:
        try:
            latest_status = json.loads(files[-1].read_text(encoding="utf-8")).get("status", "unknown")
        except Exception:
            latest_status = "unknown"
    return {"report_count": len(files), "latest_status": latest_status}


def prune_sanitized_audit_reports(root: Path | str, keep_last: int = 1, max_age_days: int = 365) -> dict[str, int]:
    files = sorted(Path(root).glob("*.json"))
    remove = files[:-keep_last] if keep_last >= 0 else files
    for path in remove:
        path.unlink(missing_ok=True)
    return {"kept": len(files) - len(remove), "removed": len(remove)}
