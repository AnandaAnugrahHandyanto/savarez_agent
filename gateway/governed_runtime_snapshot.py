"""Unified governed runtime snapshot across Hermes Wave 1-5 governance surfaces."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import yaml

from agent.continuity_queue import build_snapshot as build_continuity_queue_snapshot
from agent.routing_policy_bridge import build_routing_governance_snapshot
from gateway.evidence_ladder import build_release_evidence_bundle, evaluate_release_evidence_ladder
from gateway.operator_surfaces import build_operator_mission_surface, build_operator_triage_surface
from hermes_constants import get_hermes_home


SCHEMA = "hermes.governed_runtime_snapshot.v1"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _snapshot_path() -> Path:
    return get_hermes_home() / "governed_runtime" / "latest_snapshot.json"


def _load_config_routes(config_path: Path) -> tuple[dict[str, str], list[dict[str, str]]]:
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    model = payload.get("model") or {}
    primary = {
        "provider": str(model.get("provider") or "").strip(),
        "model": str(model.get("default") or "").strip(),
    }
    fallbacks: list[dict[str, str]] = []
    for item in payload.get("fallback_providers") or []:
        if not isinstance(item, dict):
            continue
        provider = str(item.get("provider") or "").strip()
        model_name = str(item.get("model") or "").strip()
        if provider and model_name:
            fallbacks.append({"provider": provider, "model": model_name})
    return primary, fallbacks


def _overall_status(*, triage: dict[str, Any], release_decision: dict[str, Any], routing: dict[str, Any], continuity: dict[str, Any]) -> str:
    if str(triage.get("severity") or "") == "critical":
        return "critical"
    if str(release_decision.get("verdict") or "") == "block":
        return "degraded"
    if continuity.get("totals", {}).get("blocked", 0) or routing.get("parity_validation", {}).get("tasks_without_any_policy_candidate"):
        return "degraded"
    if str(triage.get("severity") or "") == "warning":
        return "warning"
    return "healthy"


def _recommended_actions(
    *,
    mission: dict[str, Any],
    triage: dict[str, Any],
    release_decision: dict[str, Any],
    routing: dict[str, Any],
    continuity: dict[str, Any],
) -> list[str]:
    actions: list[str] = list(mission.get("recommended_actions") or [])
    if release_decision.get("verdict") == "block":
        blocked = [row["gate_id"] for row in release_decision.get("gate_results", []) if row.get("status") == "block"]
        actions.append(f"Resolve release evidence ladder blocks: {', '.join(blocked) or 'unknown gate'}")
    missing_policy = routing.get("parity_validation", {}).get("tasks_without_any_policy_candidate") or []
    if missing_policy:
        actions.append(f"Add routing candidates for task classes with no policy match: {', '.join(missing_policy)}")
    blocked_tasks = continuity.get("queue", {}).get("blocked") or []
    if blocked_tasks:
        actions.append(f"Unblock continuity queue tasks: {', '.join(item['task_id'] for item in blocked_tasks[:3])}")
    seen: list[str] = []
    for item in actions:
        if item and item not in seen:
            seen.append(item)
    return seen


def build_governed_runtime_snapshot(
    *,
    repo_root: Path,
    config_path: Path | None = None,
    release_id: str | None = None,
    activation_mode: str = "shadow",
    probe_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config_path = config_path or (get_hermes_home() / "config.yaml")
    primary_route, fallback_routes = _load_config_routes(config_path)

    mission = build_operator_mission_surface()
    triage = build_operator_triage_surface()
    continuity = build_continuity_queue_snapshot()
    routing = build_routing_governance_snapshot(
        primary_route=primary_route,
        fallback_routes=fallback_routes,
        repo_root=repo_root,
        probe_summary=probe_summary,
    )
    effective_release_id = release_id or f"rel_governed_runtime_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    release_bundle = build_release_evidence_bundle(
        release_id=effective_release_id,
        activation_mode=activation_mode,
        repo_root=repo_root,
        lane_id="C2_RELEASE_SUBSTRATE",
        wave="wave_3_to_5",
    )
    release_decision = evaluate_release_evidence_ladder(bundle=release_bundle, repo_root=repo_root)

    snapshot = {
        "schema": SCHEMA,
        "generated_at": _utc_now_iso(),
        "overall_status": _overall_status(
            triage=triage,
            release_decision=release_decision,
            routing=routing,
            continuity=continuity,
        ),
        "operator": {
            "mission": mission,
            "triage": triage,
        },
        "release_governance": {
            "bundle": release_bundle,
            "decision": release_decision,
        },
        "routing_governance": routing,
        "continuity_queue": continuity,
        "summary": {
            "operator_issue_count": int(triage.get("issue_count") or 0),
            "release_block_count": sum(1 for row in release_decision.get("gate_results", []) if row.get("status") == "block"),
            "routing_policy_gap_count": len(routing.get("parity_validation", {}).get("tasks_without_any_policy_candidate") or []),
            "blocked_queue_count": int(continuity.get("totals", {}).get("blocked") or 0),
            "resumable_queue_count": len(continuity.get("queue", {}).get("resumable") or []),
        },
        "recommended_actions": _recommended_actions(
            mission=mission,
            triage=triage,
            release_decision=release_decision,
            routing=routing,
            continuity=continuity,
        ),
    }
    path = _snapshot_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    snapshot["snapshot_path"] = str(path)
    return snapshot
