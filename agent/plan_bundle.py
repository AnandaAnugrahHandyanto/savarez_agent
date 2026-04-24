from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Dict, Optional

from agent.role_runtime import (
    default_workspace_root,
    list_role_definitions,
    resolve_role,
    slugify_plan_id,
    slugify_role_name,
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_plan_bundle_root(plan_id: str, workspace_root: Optional[str | Path] = None) -> Path:
    root = default_workspace_root(workspace_root)
    return root / "_plans" / slugify_plan_id(plan_id)


def bundle_paths(plan_id: str, workspace_root: Optional[str | Path] = None) -> Dict[str, Path]:
    bundle_root = resolve_plan_bundle_root(plan_id, workspace_root)
    return {
        "bundle_root": bundle_root,
        "plan": bundle_root / "00-plan.md",
        "manifest": bundle_root / "01-manifest.json",
        "role_execution_plan": bundle_root / "02-role-execution-plan.json",
        "findings_ledger": bundle_root / "03-findings-ledger.json",
        "role_utilization_report": bundle_root / "04-role-utilization-report.json",
        "summary": bundle_root / "99-summary.md",
    }


def role_paths(plan_id: str, role_slug: str, workspace_root: Optional[str | Path] = None) -> Dict[str, Path]:
    base = resolve_plan_bundle_root(plan_id, workspace_root) / "roles" / slugify_role_name(role_slug)
    return {
        "role_root": base,
        "packets": base / "packets",
        "outputs": base / "outputs",
        "evidence": base / "evidence",
    }


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _deep_merge_dicts(base: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    merged = json.loads(json.dumps(base))
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def _validate_patch_shape(patch: Dict[str, Any], baseline: Dict[str, Any], scope: str = "manifest") -> None:
    for key, value in patch.items():
        if key not in baseline:
            continue
        expected = baseline[key]
        if isinstance(expected, dict):
            if not isinstance(value, dict):
                raise ValueError(f"Invalid patch type for {scope}.{key}: expected object")
            _validate_patch_shape(value, expected, f"{scope}.{key}")
        elif isinstance(expected, list):
            if not isinstance(value, list):
                raise ValueError(f"Invalid patch type for {scope}.{key}: expected list")
        elif isinstance(value, (dict, list)):
            raise ValueError(f"Invalid patch type for {scope}.{key}: expected scalar value")



def _read_json(path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
    if not path.exists():
        return json.loads(json.dumps(default))
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return json.loads(json.dumps(default))
    return data if isinstance(data, dict) else json.loads(json.dumps(default))


def _findings_ledger_default(plan_id: str) -> Dict[str, Any]:
    return {
        "schema_version": "1.0",
        "plan_id": slugify_plan_id(plan_id),
        "updated_at": utc_now_iso(),
        "summary": {
            "open_count": 0,
            "pending_lead_review_count": 0,
            "pending_revalidation_count": 0,
            "closed_count": 0,
            "send_back_count": 0,
            "rejected_count": 0,
            "deferred_count": 0,
        },
        "findings": [],
    }


def _relative_to_workspace(path: Path, workspace_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(workspace_root.resolve()))
    except ValueError:
        return str(path)


def _safe_role_artifact_target(base_dir: Path, filename: str) -> Path:
    if not filename or not str(filename).strip():
        raise ValueError("filename is required")
    candidate = (base_dir / filename).resolve()
    base_resolved = base_dir.resolve()
    try:
        candidate.relative_to(base_resolved)
    except ValueError as exc:
        raise ValueError(f"Artifact filename escapes role artifact directory: {filename}") from exc
    return candidate


def _ensure_known_role_slug(role_slug: str, registry_path: Optional[str | Path] = None) -> str:
    slug = slugify_role_name(role_slug)
    known_slugs = {role.slug for role in list_role_definitions(path=registry_path)}
    if slug not in known_slugs:
        raise ValueError(f"Unknown role slug: {role_slug}")
    return slug


def _resolve_role_title_and_slug(role_value: str, registry_path: Optional[str | Path] = None) -> tuple[str, str]:
    role = resolve_role(role_value, path=registry_path)
    return role.title, role.slug


def _recompute_findings_summary(ledger: Dict[str, Any]) -> Dict[str, int]:
    findings = ledger.get("findings") if isinstance(ledger.get("findings"), list) else []

    def _status(finding: Dict[str, Any]) -> str:
        return str(finding.get("status") or "").strip().lower()

    def _disposition(finding: Dict[str, Any]) -> str:
        review = finding.get("lead_review") if isinstance(finding.get("lead_review"), dict) else {}
        return str(review.get("disposition") or "").strip().lower()

    summary = {
        "open_count": sum(
            1
            for finding in findings
            if isinstance(finding, dict) and _status(finding) in {"open", "in_fix", "pending_revalidation"}
        ),
        "pending_lead_review_count": sum(
            1
            for finding in findings
            if isinstance(finding, dict)
            and _status(finding) == "open"
            and _disposition(finding) in {"", "pending", "needs_clarification"}
        ),
        "pending_revalidation_count": sum(
            1 for finding in findings if isinstance(finding, dict) and _status(finding) == "pending_revalidation"
        ),
        "closed_count": sum(1 for finding in findings if isinstance(finding, dict) and _status(finding) == "closed"),
        "send_back_count": sum(
            1
            for finding in findings
            if isinstance(finding, dict) and _status(finding) in {"in_fix", "pending_revalidation"}
        ),
        "rejected_count": sum(1 for finding in findings if isinstance(finding, dict) and _status(finding) == "rejected"),
        "deferred_count": sum(1 for finding in findings if isinstance(finding, dict) and _status(finding) == "deferred"),
    }
    ledger["summary"] = summary
    return summary


def _read_findings_ledger(plan_id: str, paths: Dict[str, Path]) -> Dict[str, Any]:
    ledger = _read_json(paths["findings_ledger"], _findings_ledger_default(plan_id))
    if not isinstance(ledger.get("findings"), list):
        ledger["findings"] = []
    _recompute_findings_summary(ledger)
    return ledger


def _write_findings_ledger(
    plan_id: str,
    ledger: Dict[str, Any],
    paths: Dict[str, Path],
    workspace_root: Path,
) -> Dict[str, Any]:
    ledger["plan_id"] = slugify_plan_id(plan_id)
    ledger["updated_at"] = utc_now_iso()
    summary = _recompute_findings_summary(ledger)
    _write_json(paths["findings_ledger"], ledger)

    manifest_default = _default_manifest(
        plan_id=plan_id,
        workspace_root=workspace_root,
        title=None,
        lead_session_id=None,
        paths=paths,
    )
    manifest = _read_json(paths["manifest"], manifest_default)
    recovery = manifest.get("recovery") if isinstance(manifest.get("recovery"), dict) else {}
    recovery["open_findings_count"] = summary["open_count"]
    if summary["pending_lead_review_count"] == 0:
        reviewed_times = [
            finding.get("lead_review", {}).get("reviewed_at")
            for finding in ledger.get("findings", [])
            if isinstance(finding, dict) and isinstance(finding.get("lead_review"), dict)
        ]
        reviewed_times = [item for item in reviewed_times if item]
        if reviewed_times:
            recovery["last_lead_review_at"] = max(reviewed_times)
    manifest["recovery"] = recovery
    manifest["updated_at"] = utc_now_iso()
    _write_json(paths["manifest"], manifest)
    return ledger


def _finding_index(ledger: Dict[str, Any], finding_id: str) -> int:
    for idx, finding in enumerate(ledger.get("findings", [])):
        if isinstance(finding, dict) and str(finding.get("finding_id") or "") == str(finding_id):
            return idx
    raise ValueError(f"Unknown finding_id: {finding_id}")


def _default_manifest(
    *,
    plan_id: str,
    workspace_root: Path,
    title: Optional[str],
    lead_session_id: Optional[str],
    paths: Dict[str, Path],
) -> Dict[str, Any]:
    return {
        "schema_version": "1.0",
        "plan_id": slugify_plan_id(plan_id),
        "title": title or plan_id,
        "bundle_root": _relative_to_workspace(paths["bundle_root"], workspace_root),
        "plan_path": _relative_to_workspace(paths["plan"], workspace_root),
        "status": "planned",
        "current_phase": "planning",
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
        "lead": {
            "role": "Lead / PM",
            "role_slug": "lead-pm",
            "session_id": lead_session_id,
            "execution_mode": "persistent_role_instance",
        },
        "user_approval": {
            "required": True,
            "status": "pending",
            "approved_at": None,
            "approval_artifact": None,
        },
        "artifacts": {
            "role_execution_plan": _relative_to_workspace(paths["role_execution_plan"], workspace_root),
            "findings_ledger": _relative_to_workspace(paths["findings_ledger"], workspace_root),
            "role_utilization_report": _relative_to_workspace(paths["role_utilization_report"], workspace_root),
            "summary": _relative_to_workspace(paths["summary"], workspace_root),
        },
        "role_sessions": [],
        "recovery": {
            "active_role": None,
            "resume_from_artifact": None,
            "open_findings_count": 0,
            "last_lead_review_at": None,
        },
    }


def ensure_plan_bundle(
    plan_id: str,
    *,
    workspace_root: Optional[str | Path] = None,
    title: Optional[str] = None,
    lead_session_id: Optional[str] = None,
    registry_path: Optional[str | Path] = None,
) -> Dict[str, Path]:
    workspace = default_workspace_root(workspace_root)
    paths = bundle_paths(plan_id, workspace)
    bundle_root = paths["bundle_root"]
    bundle_root.mkdir(parents=True, exist_ok=True)

    for role in list_role_definitions(path=registry_path):
        rp = role_paths(plan_id, role.slug, workspace)
        for directory in rp.values():
            directory.mkdir(parents=True, exist_ok=True)

    if not paths["plan"].exists():
        title_text = title or f"Plan bundle for {plan_id}"
        paths["plan"].write_text(
            f"# {title_text}\n\n> Auto-created role-team plan bundle.\n",
            encoding="utf-8",
        )

    manifest_default = _default_manifest(
        plan_id=plan_id,
        workspace_root=workspace,
        title=title,
        lead_session_id=lead_session_id,
        paths=paths,
    )
    if not paths["manifest"].exists():
        _write_json(paths["manifest"], manifest_default)

    role_execution_plan_default = {
        "schema_version": "1.0",
        "plan_id": slugify_plan_id(plan_id),
        "generated_at": utc_now_iso(),
        "generated_by": {
            "role": "Lead / PM",
            "session_id": lead_session_id,
        },
        "workflow_sequence": [],
        "roles": [],
    }
    if not paths["role_execution_plan"].exists():
        _write_json(paths["role_execution_plan"], role_execution_plan_default)

    findings_default = _findings_ledger_default(plan_id)
    if not paths["findings_ledger"].exists():
        _write_json(paths["findings_ledger"], findings_default)

    role_utilization_default = {
        "schema_version": "1.0",
        "plan_id": slugify_plan_id(plan_id),
        "generated_at": utc_now_iso(),
        "generated_by": {
            "role": "Lead / PM",
            "session_id": lead_session_id,
        },
        "roles": [],
    }
    if not paths["role_utilization_report"].exists():
        _write_json(paths["role_utilization_report"], role_utilization_default)

    if not paths["summary"].exists():
        paths["summary"].write_text("# Summary\n\n", encoding="utf-8")

    return paths


def update_manifest(
    plan_id: str,
    patch: Dict[str, Any],
    workspace_root: Optional[str | Path] = None,
    registry_path: Optional[str | Path] = None,
) -> Dict[str, Any]:
    workspace = default_workspace_root(workspace_root)
    paths = ensure_plan_bundle(plan_id, workspace_root=workspace, registry_path=registry_path)
    manifest_default = _default_manifest(
        plan_id=plan_id,
        workspace_root=workspace,
        title=None,
        lead_session_id=None,
        paths=paths,
    )
    _validate_patch_shape(patch, manifest_default)
    current = _read_json(paths["manifest"], manifest_default)
    current = _deep_merge_dicts(current, patch)
    current["updated_at"] = utc_now_iso()
    _write_json(paths["manifest"], current)
    return current


def read_manifest(
    plan_id: str,
    workspace_root: Optional[str | Path] = None,
    registry_path: Optional[str | Path] = None,
) -> Dict[str, Any]:
    workspace = default_workspace_root(workspace_root)
    paths = ensure_plan_bundle(plan_id, workspace_root=workspace, registry_path=registry_path)
    manifest_default = _default_manifest(
        plan_id=plan_id,
        workspace_root=workspace,
        title=None,
        lead_session_id=None,
        paths=paths,
    )
    return _read_json(paths["manifest"], manifest_default)


def write_role_packet(
    plan_id: str,
    role_slug: str,
    filename: str,
    content: str,
    workspace_root: Optional[str | Path] = None,
    registry_path: Optional[str | Path] = None,
) -> Path:
    canonical_role_slug = _ensure_known_role_slug(role_slug, registry_path=registry_path)
    base_dir = role_paths(plan_id, canonical_role_slug, workspace_root)["packets"]
    target = _safe_role_artifact_target(base_dir, filename)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def write_role_output(
    plan_id: str,
    role_slug: str,
    filename: str,
    content: str,
    workspace_root: Optional[str | Path] = None,
    registry_path: Optional[str | Path] = None,
) -> Path:
    canonical_role_slug = _ensure_known_role_slug(role_slug, registry_path=registry_path)
    base_dir = role_paths(plan_id, canonical_role_slug, workspace_root)["outputs"]
    target = _safe_role_artifact_target(base_dir, filename)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def _extract_json_candidates(text: str) -> list[Dict[str, Any]]:
    candidates: list[Dict[str, Any]] = []
    if not isinstance(text, str) or not text.strip():
        return candidates
    for match in re.finditer(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL | re.IGNORECASE):
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            candidates.append(payload)
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            candidates.append(payload)
    return candidates


def _iter_structured_findings(output_text: str) -> list[Dict[str, Any]]:
    findings: list[Dict[str, Any]] = []
    for payload in _extract_json_candidates(output_text):
        raw_findings = payload.get("findings")
        if isinstance(raw_findings, list):
            findings.extend(item for item in raw_findings if isinstance(item, dict))
        elif isinstance(raw_findings, dict):
            findings.append(raw_findings)
    return findings


def ingest_findings_from_role_output(
    plan_id: str,
    *,
    raised_by_role: str,
    output_text: str,
    source_artifact: Optional[str] = None,
    workspace_root: Optional[str | Path] = None,
    registry_path: Optional[str | Path] = None,
) -> Dict[str, Any]:
    """Ingest structured findings emitted by a validator/specialist role output.

    Supported output shape is a JSON object, either raw or in a fenced JSON block,
    containing `findings: [{finding_id, title, description, severity?}, ...]`.
    Findings are recorded as Lead-review-pending; this helper never creates
    Developer remediation packets.
    """
    structured_findings = _iter_structured_findings(output_text)
    ingested: list[str] = []
    skipped: list[Dict[str, str]] = []
    ledger = None
    for index, finding in enumerate(structured_findings, start=1):
        finding_id = str(finding.get("finding_id") or finding.get("id") or "").strip()
        title = str(finding.get("title") or "").strip()
        description = str(finding.get("description") or finding.get("details") or "").strip()
        if not finding_id:
            finding_id = f"{slugify_role_name(raised_by_role).upper()}-{index:03d}"
        if not title or not description:
            skipped.append({"finding_id": finding_id, "reason": "missing title or description"})
            continue
        try:
            ledger = record_finding(
                plan_id,
                finding_id=finding_id,
                raised_by_role=raised_by_role,
                title=title,
                description=description,
                severity=str(finding.get("severity") or "medium"),
                source_artifact=source_artifact,
                workspace_root=workspace_root,
                registry_path=registry_path,
            )
            ingested.append(finding_id)
        except ValueError as exc:
            skipped.append({"finding_id": finding_id, "reason": str(exc)})
    if ledger is None:
        workspace = default_workspace_root(workspace_root)
        paths = ensure_plan_bundle(plan_id, workspace_root=workspace, registry_path=registry_path)
        ledger = _read_findings_ledger(plan_id, paths)
    return {
        "count": len(ingested),
        "finding_ids": ingested,
        "skipped": skipped,
        "ledger": ledger,
    }


def record_finding(
    plan_id: str,
    *,
    finding_id: str,
    raised_by_role: str,
    title: str,
    description: str,
    severity: str = "medium",
    source_artifact: Optional[str] = None,
    workspace_root: Optional[str | Path] = None,
    registry_path: Optional[str | Path] = None,
) -> Dict[str, Any]:
    """Record a validator/specialist finding awaiting Lead review.

    The finding is intentionally not assigned to Developer and no remediation
    packet is created here. Lead review is the only path that may route the
    finding into a remediation packet.
    """
    workspace = default_workspace_root(workspace_root)
    paths = ensure_plan_bundle(plan_id, workspace_root=workspace, registry_path=registry_path)
    ledger = _read_findings_ledger(plan_id, paths)
    if any(str(item.get("finding_id") or "") == str(finding_id) for item in ledger.get("findings", []) if isinstance(item, dict)):
        raise ValueError(f"Duplicate finding_id: {finding_id}")

    role_title, role_slug = _resolve_role_title_and_slug(raised_by_role, registry_path=registry_path)
    now = utc_now_iso()
    ledger["findings"].append(
        {
            "finding_id": str(finding_id),
            "raised_by_role": role_title,
            "raised_by_role_slug": role_slug,
            "title": str(title),
            "description": str(description),
            "severity": str(severity or "medium"),
            "source_artifact": source_artifact,
            "status": "open",
            "lead_review": {
                "disposition": "pending",
                "reviewed_by_session_id": None,
                "reviewed_at": None,
                "notes": None,
            },
            "assigned_to_role": None,
            "assigned_to_role_slug": None,
            "remediation_packet_path": None,
            "revalidation_roles_required": [],
            "remediation_artifacts": [],
            "closure_artifacts": [],
            "created_at": now,
            "updated_at": now,
        }
    )
    return _write_findings_ledger(plan_id, ledger, paths, workspace)


def lead_review_finding(
    plan_id: str,
    *,
    finding_id: str,
    disposition: str,
    lead_session_id: str,
    assigned_to_role: str = "Developer",
    remediation_instructions: Optional[str] = None,
    revalidation_roles_required: Optional[list[str]] = None,
    notes: Optional[str] = None,
    workspace_root: Optional[str | Path] = None,
    registry_path: Optional[str | Path] = None,
) -> Dict[str, Any]:
    """Apply Lead disposition and, for accepted findings, create a remediation packet."""
    workspace = default_workspace_root(workspace_root)
    paths = ensure_plan_bundle(plan_id, workspace_root=workspace, registry_path=registry_path)
    ledger = _read_findings_ledger(plan_id, paths)
    idx = _finding_index(ledger, finding_id)
    finding = ledger["findings"][idx]

    disposition_clean = str(disposition or "").strip().lower()
    if disposition_clean not in {"accepted", "rejected", "deferred", "needs_clarification"}:
        raise ValueError("disposition must be accepted, rejected, deferred, or needs_clarification")

    now = utc_now_iso()
    finding["lead_review"] = {
        "disposition": disposition_clean,
        "reviewed_by_session_id": lead_session_id,
        "reviewed_at": now,
        "notes": notes,
    }
    finding.setdefault("review_history", []).append(finding["lead_review"])

    if disposition_clean == "accepted":
        assigned_title, assigned_slug = _resolve_role_title_and_slug(assigned_to_role, registry_path=registry_path)
        revalidation_titles = []
        for role_value in (revalidation_roles_required or [finding.get("raised_by_role")]):
            role_title, _ = _resolve_role_title_and_slug(str(role_value), registry_path=registry_path)
            revalidation_titles.append(role_title)

        safe_finding_id = str(finding_id).replace("/", "-").replace("\\", "-")
        packet_filename = f"remediation-{safe_finding_id}.md"
        packet_text = (
            f"# Lead-reviewed remediation packet: {finding_id}\n\n"
            f"- Finding: {finding.get('title')}\n"
            f"- Raised by: {finding.get('raised_by_role')}\n"
            f"- Lead session: {lead_session_id}\n"
            f"- Assigned to: {assigned_title}\n"
            f"- Revalidation required from: {', '.join(revalidation_titles)}\n\n"
            "## Finding description\n\n"
            f"{finding.get('description')}\n\n"
            "## Remediation instructions\n\n"
            f"{remediation_instructions or 'Address the accepted finding and provide remediation evidence.'}\n"
        )
        packet_path = write_role_packet(
            plan_id,
            assigned_slug,
            packet_filename,
            packet_text,
            workspace_root=workspace,
            registry_path=registry_path,
        )
        finding["status"] = "in_fix"
        finding["assigned_to_role"] = assigned_title
        finding["assigned_to_role_slug"] = assigned_slug
        finding["remediation_packet_path"] = _relative_to_workspace(packet_path, workspace)
        finding["revalidation_roles_required"] = revalidation_titles
    elif disposition_clean == "rejected":
        finding["status"] = "rejected"
    elif disposition_clean == "deferred":
        finding["status"] = "deferred"
    else:
        finding["status"] = "open"

    finding["updated_at"] = now
    ledger["findings"][idx] = finding
    return _write_findings_ledger(plan_id, ledger, paths, workspace)


def mark_finding_pending_revalidation(
    plan_id: str,
    *,
    finding_id: str,
    developer_session_id: Optional[str] = None,
    remediation_artifacts: Optional[list[str]] = None,
    workspace_root: Optional[str | Path] = None,
    registry_path: Optional[str | Path] = None,
) -> Dict[str, Any]:
    workspace = default_workspace_root(workspace_root)
    paths = ensure_plan_bundle(plan_id, workspace_root=workspace, registry_path=registry_path)
    ledger = _read_findings_ledger(plan_id, paths)
    idx = _finding_index(ledger, finding_id)
    finding = ledger["findings"][idx]
    if finding.get("status") != "in_fix":
        raise ValueError(f"Finding {finding_id} is not currently in_fix")
    finding["status"] = "pending_revalidation"
    finding["developer_session_id"] = developer_session_id
    finding["remediation_artifacts"] = list(remediation_artifacts or [])
    finding["updated_at"] = utc_now_iso()
    ledger["findings"][idx] = finding
    return _write_findings_ledger(plan_id, ledger, paths, workspace)


def close_finding(
    plan_id: str,
    *,
    finding_id: str,
    closed_by_role: str,
    closure_artifacts: Optional[list[str]] = None,
    workspace_root: Optional[str | Path] = None,
    registry_path: Optional[str | Path] = None,
) -> Dict[str, Any]:
    workspace = default_workspace_root(workspace_root)
    paths = ensure_plan_bundle(plan_id, workspace_root=workspace, registry_path=registry_path)
    ledger = _read_findings_ledger(plan_id, paths)
    idx = _finding_index(ledger, finding_id)
    finding = ledger["findings"][idx]
    closed_title, closed_slug = _resolve_role_title_and_slug(closed_by_role, registry_path=registry_path)
    now = utc_now_iso()
    finding["status"] = "closed"
    finding["closed_by_role"] = closed_title
    finding["closed_by_role_slug"] = closed_slug
    finding["closed_at"] = now
    finding["closure_artifacts"] = list(closure_artifacts or [])
    finding["updated_at"] = now
    ledger["findings"][idx] = finding
    return _write_findings_ledger(plan_id, ledger, paths, workspace)


def completion_gate_status(
    plan_id: str,
    *,
    workspace_root: Optional[str | Path] = None,
    registry_path: Optional[str | Path] = None,
) -> Dict[str, Any]:
    """Return whether a role-team plan may be declared complete."""
    workspace = default_workspace_root(workspace_root)
    paths = ensure_plan_bundle(plan_id, workspace_root=workspace, registry_path=registry_path)
    ledger = _read_findings_ledger(plan_id, paths)
    execution_plan = _read_json(paths["role_execution_plan"], {"roles": []})
    utilization_report = _read_json(paths["role_utilization_report"], {"roles": []})

    blockers = []
    for finding in ledger.get("findings", []):
        if not isinstance(finding, dict):
            continue
        finding_id = finding.get("finding_id")
        status = str(finding.get("status") or "").strip().lower()
        review = finding.get("lead_review") if isinstance(finding.get("lead_review"), dict) else {}
        disposition = str(review.get("disposition") or "").strip().lower()
        if status == "open" and disposition in {"", "pending", "needs_clarification"}:
            blockers.append({"type": "pending_lead_review", "finding_id": finding_id})
        elif status in {"open", "in_fix", "pending_revalidation"}:
            blockers.append({"type": "open_finding", "finding_id": finding_id, "status": status})

    utilized_roles = {}
    for item in utilization_report.get("roles", []) if isinstance(utilization_report.get("roles"), list) else []:
        if not isinstance(item, dict):
            continue
        role_slug = slugify_role_name(item.get("role_slug") or item.get("role") or item.get("title") or "")
        if role_slug:
            utilized_roles[role_slug] = item

    waived_required_roles = []
    planned_roles = execution_plan.get("roles") if isinstance(execution_plan.get("roles"), list) else []
    for item in planned_roles:
        if not isinstance(item, dict) or not item.get("required", True):
            continue
        role_slug = slugify_role_name(item.get("role_slug") or item.get("role") or item.get("title") or "")
        if not role_slug:
            continue
        if item.get("waived") and str(item.get("waiver_reason") or "").strip():
            waived_required_roles.append(role_slug)
            continue
        utilized = utilized_roles.get(role_slug)
        utilized_status = str((utilized or {}).get("status") or "").strip().lower()
        if utilized is None:
            blockers.append({"type": "required_role_missing", "role_slug": role_slug})
        elif utilized_status != "completed":
            blockers.append({"type": "required_role_incomplete", "role_slug": role_slug, "status": utilized_status})

    summary = ledger.get("summary") if isinstance(ledger.get("summary"), dict) else {}
    return {
        "can_complete": not blockers,
        "blockers": blockers,
        "open_findings_count": int(summary.get("open_count") or 0),
        "pending_lead_review_count": int(summary.get("pending_lead_review_count") or 0),
        "pending_revalidation_count": int(summary.get("pending_revalidation_count") or 0),
        "closed_count": int(summary.get("closed_count") or 0),
        "waived_required_roles": waived_required_roles,
    }
