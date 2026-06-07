from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
import os
import subprocess

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/context-control", tags=["context-control"])

PROJECT_NAMES = ["Menu Finance", "Chief OS", "Salim", "Hermes Dashboard", "Skills", "Models", "Logs", "Crons"]
SAFETY_BLOCK_KEYS = [
    "safety.finance-execution-disabled",
    "safety.menu-ca-research-only",
    "safety.no-live-switch-without-approval",
    "safety.no-secret-emission",
    "safety.practice-mode-off-on-load",
]


def _root() -> Path:
    return Path(os.getenv("HERMES_CONTEXT_CONTROL_ROOT") or "/Users/jordan/projects/context-ci-pilot-001")


def _phase_dir(root: Path) -> Path:
    return root / "reports/pilot-001/phase-c"


def _control_root(root: Path) -> Path:
    return root / ".hermes/context-control-plane/pilot-001"


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def _read_text(path: Path) -> str:
    return path.read_text() if path.exists() else ""


def _latest_child(parent: Path) -> Path | None:
    if not parent.exists():
        return None
    children = [p for p in parent.iterdir() if p.is_dir()]
    return max(children, key=lambda p: p.name) if children else None


def _jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            rows.append({"event": "unparseable", "raw": line})
    return rows


def _hours_left(live: dict[str, Any]) -> str:
    target = live.get("target_end_utc")
    if not target:
        return "unknown"
    try:
        end = datetime.fromisoformat(str(target).replace("Z", "+00:00"))
        delta = end - datetime.now(timezone.utc)
        hours = max(0, delta.total_seconds() / 3600)
        return f"{hours:.0f}h left"
    except Exception:
        return "unknown"


def _override_rate(rows: list[dict[str, Any]]) -> tuple[str, float]:
    real = [r for r in rows if not str(r.get("event", "")).startswith("test_") and r.get("event") != "live_window_started"]
    if not real:
        return "0/0", 0.0
    overrides = [r for r in real if r.get("override") or r.get("event") in {"user_correction", "safety_regression"}]
    return f"{len(overrides)}/{len(real)}", len(overrides) / len(real)


def _finding_count(findings: dict[str, Any], *keys: str) -> int:
    total = 0
    for key in keys:
        value = findings.get(key, [])
        if isinstance(value, list):
            total += len(value)
        elif value:
            total += 1
    return total


def _latest_baseline_token_count(control: Path) -> int | None:
    latest = _latest_child(control / "baseline")
    if not latest:
        return None
    counts = _read_json(latest / "token-counts.json", {})
    return counts.get("active_context_tokens_estimate") or counts.get("tokens")


def build_context_control_state() -> dict[str, Any]:
    root = _root()
    phase = _phase_dir(root)
    control = _control_root(root)
    eval_report = _read_json(phase / "eval-report.json", {})
    diff_packet = _read_json(phase / "diff-packet.json", {})
    live = _read_json(control / "live-window/live-window.json", {})
    override_rows = _jsonl(control / "live-window/override-log.jsonl")
    rejection_rows = _jsonl(control / "live-window/rejections.jsonl")
    latest_switch = _latest_child(control / "switch")
    switch_log = _read_json(latest_switch / "switch-log.json", {}) if latest_switch else {}
    findings = diff_packet.get("findings") or diff_packet.get("stale_duplicate_conflict") or {}
    findings = {
        **findings,
        "scope_leakage": (diff_packet.get("scope_leakage") or {}).get("findings", []),
        "precedence_conflicts": (diff_packet.get("precedence_conflict") or {}).get("findings", []),
    }
    managed = diff_packet.get("managed_scope") or {}
    provenance_count = len(diff_packet.get("provenance") or [])
    diff_value = diff_packet.get("diff") or []
    diff_count = len(diff_value) if isinstance(diff_value, list) else len(diff_value.get("added", []) or [])
    blocks = managed.get("blocks") or provenance_count or diff_count or 8
    sources = managed.get("sources") or provenance_count or blocks
    eval0_passed = bool((eval_report.get("eval_0") or eval_report.get("eval0") or {}).get("passed"))
    rollback_hot = bool((switch_log.get("rollback_command") or live.get("rollback_command")))
    override_text, override_float = _override_rate(override_rows)
    token_delta = ((eval_report.get("candidate_vs_baseline") or {}).get("token_delta"))
    if token_delta is None:
        token_delta = eval_report.get("token_delta")
    tokens_saved = abs(int(token_delta)) if isinstance(token_delta, int | float) and token_delta < 0 else 0
    stale_count = _finding_count(findings, "stale", "duplicates", "conflicts")
    scope_count = _finding_count(findings, "scope_leakage", "precedence_conflicts")
    raw_proposals = diff_packet.get("proposals") or [{
        "id": "chief-os-pilot-001",
        "project": "Chief OS",
        "summary": "Chief OS: remove stale tokens, keep all safety rules, pass-rate held",
        "safety_critical_blocks": SAFETY_BLOCK_KEYS,
        "token_delta": token_delta or -tokens_saved,
        "pass_rate_impact": "held" if eval_report.get("task_pass_rate") else "unknown",
        "confidence": 0.92 if eval0_passed else 0.0,
    }]
    proposals = []
    for p in raw_proposals:
        safety_blocks = p.get("safety_critical_blocks") or []
        proposals.append({
            **p,
            "approve_enabled": eval0_passed,
            "requires_per_block_approval": bool(safety_blocks),
            "safety_impact": "safety-critical approval required" if safety_blocks else "no safety-critical block changes",
            "status": "awaiting approval",
        })
    projects = []
    for name in PROJECT_NAMES:
        managed_project = name in {"Chief OS"}
        projects.append({
            "name": name,
            "managed": managed_project,
            "current_size": f"{_latest_baseline_token_count(control) or 'unknown'} tokens" if managed_project else "unmanaged",
            "last_compiled": switch_log.get("switch_id") if managed_project else "—",
            "pending_proposals": len([p for p in proposals if p.get("project") == name]),
            "findings_count": stale_count + scope_count if managed_project else 0,
            "eval_0": "pass" if eval0_passed and managed_project else ("unmanaged" if not managed_project else "fail"),
            "last_switch": switch_log.get("switch_id") if managed_project else "—",
            "rollback": "hot" if rollback_hot and managed_project else "—",
        })
    safety_events = [r for r in override_rows if r.get("safety_relevant")]
    return {
        "eyebrow": "CONTEXT CONTROL · RECOMMEND ONLY · NO LIVE CHANGES WITHOUT APPROVAL",
        "title": "Context control plane",
        "subtitle": "The immutable baseline and one-click rollback win ties. This is a review and approval surface for agent context — never something that changes context on its own. Proposals are draft-only; nothing goes live without Jordan's approval.",
        "pill": "Auto-apply disabled",
        "status": {
            "date": datetime.now(timezone.utc).date().isoformat(),
            "pending_approvals": len(proposals),
            "eval_0": "pass" if eval0_passed else "fail",
            "override_rate": override_text,
            "live_overlay": "active" if switch_log else "none",
            "rollback": "hot" if rollback_hot else "missing",
            "managed_scope": f"{blocks} blocks / {sources} sources",
            "live_window": _hours_left(live),
        },
        "metrics": {
            "pending_approvals": {"value": len(proposals), "tone": "red" if proposals else "green"},
            "safety": {"value": "Eval 0 pass" if eval0_passed else "Eval 0 fail", "tone": "green" if eval0_passed else "red"},
            "override_rate": {"value": override_text, "float": override_float, "tone": "amber" if override_float else "green"},
            "tokens_saved": {"value": tokens_saved, "tone": "green" if tokens_saved else "amber"},
            "stale_findings": {"value": stale_count, "tone": "amber" if stale_count else "green"},
            "scope_leakage_findings": {"value": scope_count, "tone": "red" if scope_count else "green"},
        },
        "proposals": proposals,
        "recommended_fixes": findings,
        "projects": projects,
        "evals": eval_report,
        "diff": diff_packet.get("diff") if isinstance(diff_packet.get("diff"), list) else [{"block_id": "candidate", "reason": "compiled diff", "removed": (diff_packet.get("diff") or {}).get("removed", []), "added": (diff_packet.get("diff") or {}).get("added", [])}],
        "summary_md": _read_text(phase / "summary.md"),
        "evidence_summary_md": _read_text(phase / "evidence-summary.md"),
        "live_window": live,
        "override_log": override_rows,
        "rejections": rejection_rows,
        "history": {"latest_switch": switch_log, "switch_dir": str(latest_switch) if latest_switch else None},
        "governance": {"auto_apply": False, "approval_mode": "Jordan explicit approval", "rollback_command": switch_log.get("rollback_command") or live.get("rollback_command")},
    }


def record_rejection(proposal_id: str, reason: str, rejected_by: str = "Jordan") -> dict[str, Any]:
    if not proposal_id or not reason.strip():
        raise ValueError("proposal_id and reason are required")
    root = _root()
    log = _control_root(root) / "live-window/rejections.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "event": "proposal_rejected",
        "at_utc": datetime.now(timezone.utc).isoformat(),
        "proposal_id": proposal_id,
        "reason": reason.strip(),
        "rejected_by": rejected_by,
        "training_data": True,
        "deleted": False,
    }
    with log.open("a") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"status": "recorded", "record": row}


class RejectRequest(BaseModel):
    reason: str
    rejected_by: str = "Jordan"


class ApproveRequest(BaseModel):
    safety_block_approvals: list[str] = []


class OpenFileRequest(BaseModel):
    path: str


def resolve_open_file_target(path: str) -> Path:
    root = _root().resolve()
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    if root != resolved and root not in resolved.parents:
        raise ValueError("open-file target is outside the context-control pilot root")
    if not resolved.exists():
        raise ValueError("open-file target does not exist")
    return resolved


@router.get("/state")
def context_control_state() -> dict[str, Any]:
    return build_context_control_state()


@router.post("/proposals/{proposal_id}/reject")
def reject_context_control_proposal(proposal_id: str, payload: RejectRequest) -> dict[str, Any]:
    try:
        return record_rejection(proposal_id, payload.reason, payload.rejected_by)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/proposals/{proposal_id}/approve")
def approve_context_control_proposal(proposal_id: str, payload: ApproveRequest) -> dict[str, Any]:
    state = build_context_control_state()
    if state["status"]["eval_0"] != "pass":
        raise HTTPException(status_code=409, detail="Eval 0 must be green before approval")
    proposal = next((p for p in state["proposals"] if p.get("id") == proposal_id), None)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    required = set(proposal.get("safety_critical_blocks") or [])
    supplied = set(payload.safety_block_approvals or [])
    if required and required != supplied:
        raise HTTPException(status_code=409, detail="Every safety-critical block needs explicit per-block approval")
    script = _root() / "scripts/switch_managed_context.py"
    if not script.exists():
        raise HTTPException(status_code=404, detail="switch_managed_context.py not found")
    result = subprocess.run(["python", str(script)], cwd=str(_root()), text=True, capture_output=True, timeout=120)
    return {"status": "switched" if result.returncode == 0 else "failed", "returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}


@router.post("/rollback")
def rollback_context_control() -> dict[str, Any]:
    state = build_context_control_state()
    cmd = state.get("governance", {}).get("rollback_command")
    if not cmd:
        raise HTTPException(status_code=404, detail="Rollback command not found")
    result = subprocess.run(["bash", cmd], cwd=str(_root()), text=True, capture_output=True, timeout=120)
    return {"status": "rolled_back" if result.returncode == 0 else "failed", "returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}


@router.post("/open-file")
def open_context_control_file(payload: OpenFileRequest) -> dict[str, Any]:
    try:
        target = resolve_open_file_target(payload.path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    opener = "open" if os.name == "posix" else "xdg-open"
    try:
        subprocess.Popen([opener, str(target)])
    except Exception as exc:  # pragma: no cover - depends on desktop environment
        raise HTTPException(status_code=500, detail=f"Failed to open file: {exc}") from exc
    return {"status": "opened", "path": str(target)}
