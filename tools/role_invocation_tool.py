from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from agent.plan_bundle import (
    bundle_paths,
    ensure_plan_bundle,
    ingest_findings_from_role_output,
    read_manifest,
    role_paths,
    update_manifest,
)
from agent.role_runtime import (
    EXECUTION_MODES,
    FINDING_STATUSES,
    DEFAULT_EXECUTION_MODE,
    DEFAULT_RUNTIME_POLICY,
    PLAN_PHASES,
    ROLE_SESSION_STATUSES,
    default_workspace_root,
    get_or_create_role_session,
    resolve_role,
    role_session_id,
    role_system_prompt,
    slugify_plan_id,
)
from tools.registry import registry, tool_error, tool_result

DECLARED_ONLY_MODES = {"scheduled_role_run", "inline_lead_exception"}
SUPPORTED_EXECUTION_MODES = {"persistent_role_instance", "delegated_subagent"}
ROLE_INVOCATION_TOOLSET = "delegation"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _relativize(path: Path, workspace_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(workspace_root.resolve()))
    except Exception:
        return str(path)


def _write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _read_json(path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
    if not path.exists():
        return json.loads(json.dumps(default))
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return json.loads(json.dumps(default))
    return data if isinstance(data, dict) else json.loads(json.dumps(default))


def _upsert_by_key(items: Iterable[Dict[str, Any]], key: str, item: Dict[str, Any]) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    replaced = False
    for existing in items:
        if isinstance(existing, dict) and existing.get(key) == item.get(key):
            merged.append(item)
            replaced = True
        else:
            merged.append(existing)
    if not replaced:
        merged.append(item)
    return merged


def _merge_counts(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    counts: Dict[str, Any] = {
        "total": len(records),
        "by_status": {},
        "by_execution_mode": {},
    }
    for record in records:
        status = str(record.get("status") or "unknown")
        mode = str(record.get("execution_mode") or "unknown")
        counts["by_status"][status] = counts["by_status"].get(status, 0) + 1
        counts["by_execution_mode"][mode] = counts["by_execution_mode"].get(mode, 0) + 1
    return counts


INVOKE_ROLE_SCHEMA = {
    "name": "invoke_role",
    "description": (
        "Record and materialize a canonical role invocation inside a role-team plan bundle. "
        "Use this to validate a role against the org chart, select a supported execution mode, "
        "write packet/output/evidence artifacts, and update the bundle's execution plan and "
        "utilization report. Scheduled and inline-lead-override modes are declared by the "
        "runtime schema but are not yet implemented by this tool."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "role": {
                "type": "string",
                "description": "Canonical org-chart role title or alias to invoke."
            },
            "plan_id": {
                "type": "string",
                "description": "Stable identifier for the plan bundle under _plans/.",
            },
            "summary": {
                "type": "string",
                "description": "Short summary of what this role invocation should record.",
            },
            "execution_mode": {
                "type": "string",
                "enum": list(EXECUTION_MODES),
                "description": (
                    "Choose the role's execution mode. Defaults to the role policy's "
                    "default_execution_mode when omitted."
                ),
            },
            "status": {
                "type": "string",
                "enum": list(ROLE_SESSION_STATUSES),
                "default": "completed",
                "description": "Status to record for the role session artifact.",
            },
            "packet_content": {
                "type": "string",
                "description": "Optional explicit role packet body. A default packet is generated when omitted.",
            },
            "output_content": {
                "type": "string",
                "description": "Optional explicit role output body. Defaults to the summary when omitted.",
            },
            "evidence_content": {
                "type": "string",
                "description": "Optional explicit evidence body for the role artifact trail.",
            },
            "workspace_root": {
                "type": "string",
                "description": "Workspace root used to resolve the _plans directory.",
            },
            "registry_path": {
                "type": "string",
                "description": "Optional override for the org-chart registry YAML path.",
            },
            "lead_session_id": {
                "type": "string",
                "description": "Optional explicit lead session id to record in the manifest.",
            },
        },
        "required": ["role", "plan_id", "summary"],
        "additionalProperties": False,
    },
}


def check_invoke_role_requirements() -> bool:
    return True


def _default_packet(role_title: str, plan_id: str, summary: str, execution_mode: str, status: str) -> str:
    return (
        f"# Role packet: {role_title}\n\n"
        f"- plan_id: `{plan_id}`\n"
        f"- execution_mode: `{execution_mode}`\n"
        f"- status: `{status}`\n\n"
        f"## Summary\n\n{summary.strip()}\n"
    )


def _default_output(role_title: str, summary: str) -> str:
    return f"# Role output: {role_title}\n\n{summary.strip()}\n"


def _default_evidence(role_title: str, summary: str, execution_mode: str) -> str:
    return (
        f"# Role evidence: {role_title}\n\n"
        f"- execution_mode: `{execution_mode}`\n\n"
        f"{summary.strip()}\n"
    )


def _extract_role_response(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("final_response", "response", "output", "summary"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        return json.dumps(value, indent=2, ensure_ascii=False)
    return str(value or "").strip()


def _load_role_conversation_history(session_db: Any, role_session_id: str) -> list[Dict[str, Any]]:
    if session_db is None or not hasattr(session_db, "get_messages_as_conversation"):
        return []
    try:
        history = session_db.get_messages_as_conversation(role_session_id)
    except Exception:
        return []
    return history if isinstance(history, list) else []


def _run_persistent_role_agent(
    *,
    packet_content: str,
    role_session_id: str,
    role_system_prompt: str,
    session_db: Any,
    parent_session_id: Optional[str],
    role_agent_config: Optional[Dict[str, Any]] = None,
) -> str:
    from run_agent import AIAgent

    cfg = dict(role_agent_config or {})
    allowed_keys = {
        "base_url",
        "api_key",
        "provider",
        "api_mode",
        "model",
        "max_iterations",
        "enabled_toolsets",
        "disabled_toolsets",
        "quiet_mode",
        "reasoning_config",
        "max_tokens",
        "service_tier",
        "request_overrides",
    }
    agent_kwargs = {key: value for key, value in cfg.items() if key in allowed_keys and value is not None}
    agent_kwargs.setdefault("quiet_mode", True)
    agent_kwargs.setdefault("platform", "role_runtime")
    agent_kwargs["session_id"] = role_session_id
    agent_kwargs["parent_session_id"] = parent_session_id
    agent_kwargs["session_db"] = session_db
    agent_kwargs["ephemeral_system_prompt"] = role_system_prompt
    conversation_history = _load_role_conversation_history(session_db, role_session_id)
    result = AIAgent(**agent_kwargs).run_conversation(
        packet_content,
        conversation_history=conversation_history,
    )
    return _extract_role_response(result)


def invoke_role(
    role: Optional[str] = None,
    plan_id: Optional[str] = None,
    summary: Optional[str] = None,
    execution_mode: Optional[str] = None,
    status: str = "completed",
    packet_content: Optional[str] = None,
    output_content: Optional[str] = None,
    evidence_content: Optional[str] = None,
    workspace_root: Optional[str | Path] = None,
    registry_path: Optional[str | Path] = None,
    lead_session_id: Optional[str] = None,
    session_id: Optional[str] = None,
    task_id: Optional[str] = None,
    user_task: Optional[str] = None,
    session_db: Any = None,
    role_runner: Any = None,
    role_agent_config: Optional[Dict[str, Any]] = None,
) -> str:
    if not role or not str(role).strip():
        return tool_error("role is required")
    if not plan_id or not str(plan_id).strip():
        return tool_error("plan_id is required")
    if not summary or not str(summary).strip():
        return tool_error("summary is required")
    if status not in ROLE_SESSION_STATUSES:
        return tool_error(
            f"Status '{status}' is not supported. Supported statuses: {', '.join(sorted(ROLE_SESSION_STATUSES))}."
        )

    try:
        role_def = resolve_role(role, path=registry_path)
    except Exception as exc:
        return tool_error(str(exc))

    chosen_mode = str(execution_mode or role_def.policy.default_execution_mode or DEFAULT_EXECUTION_MODE).strip()
    if chosen_mode not in SUPPORTED_EXECUTION_MODES:
        if chosen_mode in DECLARED_ONLY_MODES:
            return tool_error(
                f"Execution mode '{chosen_mode}' is declared by the role-runtime schema but is not yet implemented in invoke_role."
            )
        return tool_error(
            f"Execution mode '{chosen_mode}' is not supported. Supported modes: {', '.join(sorted(SUPPORTED_EXECUTION_MODES))}."
        )

    if chosen_mode not in role_def.policy.allowed_execution_modes:
        return tool_error(
            f"Execution mode '{chosen_mode}' is not allowed for role '{role_def.title}'. "
            f"Allowed modes: {', '.join(role_def.policy.allowed_execution_modes)}."
        )

    workspace = default_workspace_root(workspace_root)
    parent_session = lead_session_id or session_id or task_id
    plan_slug = slugify_plan_id(plan_id)
    paths = ensure_plan_bundle(
        plan_id,
        workspace_root=workspace,
        title=f"{role_def.title} role invocation",
        lead_session_id=parent_session,
        registry_path=registry_path,
    )
    bundle_root = paths["bundle_root"]
    role_dirs = role_paths(plan_id, role_def.slug, workspace)

    timestamp = _utc_stamp()
    role_sid = role_session_id(plan_id, role_def.slug)
    packet_name = f"{timestamp}-{role_def.slug}-packet.md"
    output_name = f"{timestamp}-{role_def.slug}-output.md"
    evidence_name = f"{timestamp}-{role_def.slug}-evidence.md"

    packet_body = packet_content or _default_packet(role_def.title, plan_id, summary, chosen_mode, status)
    output_path = role_dirs["outputs"] / output_name
    evidence_path = role_dirs["evidence"] / evidence_name
    packet_path = _write_text(role_dirs["packets"] / packet_name, packet_body)

    rel_packet = _relativize(packet_path, workspace)
    rel_output = _relativize(output_path, workspace)
    rel_evidence = _relativize(evidence_path, workspace)

    role_prompt = role_system_prompt(role_def)
    role_execution_output: Optional[str] = None
    if chosen_mode == "persistent_role_instance":
        if session_db is None:
            return tool_error("persistent_role_instance execution requires a SessionDB-backed session_db")
        get_or_create_role_session(
            session_db=session_db,
            plan_id=plan_id,
            role=role_def,
            parent_session_id=parent_session,
            execution_mode=chosen_mode,
            policy_default_execution_mode=role_def.policy.default_execution_mode,
            task_packet_path=rel_packet,
            artifact_paths={
                "packet": rel_packet,
                "output": rel_output,
                "evidence": rel_evidence,
            },
            model=(role_agent_config or {}).get("model") if isinstance(role_agent_config, dict) else None,
            model_config={"role_system_prompt": role_prompt},
        )
        runner = role_runner or _run_persistent_role_agent
        try:
            role_execution_output = _extract_role_response(
                runner(
                    packet_content=packet_body,
                    role_session_id=role_sid,
                    role_system_prompt=role_prompt,
                    session_db=session_db,
                    parent_session_id=parent_session,
                    role_agent_config=role_agent_config,
                )
            )
        except Exception as exc:
            return tool_error(f"Persistent role session '{role_sid}' failed: {type(exc).__name__}: {exc}")

    output_body = role_execution_output or output_content or _default_output(role_def.title, summary)
    evidence_body = evidence_content or _default_evidence(role_def.title, role_execution_output or summary, chosen_mode)
    _write_text(output_path, output_body)
    _write_text(evidence_path, evidence_body)
    findings_ingested = ingest_findings_from_role_output(
        plan_id,
        raised_by_role=role_def.title,
        output_text=output_body,
        source_artifact=rel_output,
        workspace_root=workspace,
        registry_path=registry_path,
    )

    role_record = {
        "role_session_id": role_sid,
        "role": role_def.title,
        "role_slug": role_def.slug,
        "canonical_role": role_def.title,
        "summary": summary.strip(),
        "status": status,
        "policy_default_execution_mode": role_def.policy.default_execution_mode,
        "execution_mode": chosen_mode,
        "invocation_source": {
            "session_id": session_id,
            "task_id": task_id,
            "user_task": user_task,
        },
        "started_at": timestamp,
        "ended_at": timestamp,
        "parent_session_id": parent_session,
        "child_session_id": role_sid if chosen_mode == "delegated_subagent" else None,
        "persistent_session_id": role_sid if chosen_mode == "persistent_role_instance" else None,
        "task_packet_path": rel_packet,
        "artifact_paths": {
            "packet": rel_packet,
            "output": rel_output,
            "evidence": rel_evidence,
        },
    }

    # Update the bundle manifest with the new role session record.
    manifest = read_manifest(plan_id, workspace_root=workspace, registry_path=registry_path)
    manifest_role_sessions = manifest.get("role_sessions") or []
    manifest_role_sessions = _upsert_by_key(manifest_role_sessions, "role_session_id", role_record)
    updated_manifest = update_manifest(
        plan_id,
        {
            "lead": {"session_id": parent_session},
            "role_sessions": manifest_role_sessions,
        },
        workspace_root=workspace,
        registry_path=registry_path,
    )

    execution_plan_path = bundle_root / "02-role-execution-plan.json"
    execution_plan_default = {
        "schema_version": "1.0",
        "plan_id": plan_slug,
        "generated_at": timestamp,
        "generated_by": {"role": "Lead / PM", "session_id": parent_session},
        "workflow_sequence": list(PLAN_PHASES),
        "roles": [],
    }
    execution_plan = _read_json(execution_plan_path, execution_plan_default)
    execution_plan.setdefault("schema_version", "1.0")
    execution_plan["plan_id"] = plan_slug
    execution_plan["generated_at"] = timestamp
    execution_plan.setdefault("generated_by", {})
    execution_plan["generated_by"]["role"] = "Lead / PM"
    execution_plan["generated_by"]["session_id"] = parent_session
    execution_plan["workflow_sequence"] = execution_plan.get("workflow_sequence") or list(PLAN_PHASES)
    execution_plan_roles = execution_plan.get("roles") or []
    execution_plan_role = {
        "role_session_id": role_sid,
        "role": role_def.title,
        "role_slug": role_def.slug,
        "canonical_role": role_def.title,
        "planned_execution_mode": chosen_mode,
        "execution_mode": chosen_mode,
        "status": status,
        "summary": summary.strip(),
        "task_packet_path": rel_packet,
        "artifact_paths": {
            "packet": rel_packet,
            "output": rel_output,
            "evidence": rel_evidence,
        },
    }
    execution_plan["roles"] = _upsert_by_key(execution_plan_roles, "role_session_id", execution_plan_role)
    _write_text(execution_plan_path, json.dumps(execution_plan, indent=2, ensure_ascii=False) + "\n")

    utilization_path = bundle_root / "04-role-utilization-report.json"
    utilization_default = {
        "schema_version": "1.0",
        "plan_id": plan_slug,
        "generated_at": timestamp,
        "generated_by": {"role": "Lead / PM", "session_id": parent_session},
        "summary": {},
        "roles": [],
    }
    utilization = _read_json(utilization_path, utilization_default)
    utilization.setdefault("schema_version", "1.0")
    utilization["plan_id"] = plan_slug
    utilization["generated_at"] = timestamp
    utilization.setdefault("generated_by", {})
    utilization["generated_by"]["role"] = "Lead / PM"
    utilization["generated_by"]["session_id"] = parent_session
    utilization_roles = utilization.get("roles") or []
    utilization_roles = _upsert_by_key(utilization_roles, "role_session_id", role_record)
    utilization["roles"] = utilization_roles
    utilization["summary"] = _merge_counts(utilization_roles)
    _write_text(utilization_path, json.dumps(utilization, indent=2, ensure_ascii=False) + "\n")

    summary_path = bundle_root / "99-summary.md"
    summary_text = summary_path.read_text(encoding="utf-8") if summary_path.exists() else "# Summary\n\n"
    summary_text += (
        f"## Latest role invocation\n\n"
        f"- role: {role_def.title}\n"
        f"- execution_mode: {chosen_mode}\n"
        f"- status: {status}\n"
        f"- role_session_id: {role_sid}\n"
        f"- packet: {rel_packet}\n"
        f"- output: {rel_output}\n"
        f"- evidence: {rel_evidence}\n\n"
        f"{summary.strip()}\n\n"
    )
    _write_text(summary_path, summary_text)

    return tool_result(
        {
            "success": True,
            "canonical_role": role_def.title,
            "role_slug": role_def.slug,
            "role_session_id": role_sid,
            "persistent_session_id": role_sid if chosen_mode == "persistent_role_instance" else None,
            "child_session_id": role_sid if chosen_mode == "delegated_subagent" else None,
            "plan_id": plan_slug,
            "summary": summary.strip(),
            "status": status,
            "execution_mode": chosen_mode,
            "policy_default_execution_mode": role_def.policy.default_execution_mode,
            "allowed_execution_modes": list(role_def.policy.allowed_execution_modes),
            "worktree_strategy": role_def.policy.worktree_strategy,
            "bundle": {
                "bundle_root": str(bundle_root),
                "manifest_path": str(paths["manifest"]),
                "execution_plan_path": str(execution_plan_path),
                "utilization_report_path": str(utilization_path),
                "summary_path": str(summary_path),
            },
            "artifact_paths": {
                "packet": str(packet_path),
                "output": str(output_path),
                "evidence": str(evidence_path),
                "packet_relative": rel_packet,
                "output_relative": rel_output,
                "evidence_relative": rel_evidence,
            },
            "findings_ingested": {
                "count": findings_ingested.get("count", 0),
                "finding_ids": findings_ingested.get("finding_ids", []),
                "skipped": findings_ingested.get("skipped", []),
            },
            "manifest": updated_manifest,
        }
    )


registry.register(
    name="invoke_role",
    toolset=ROLE_INVOCATION_TOOLSET,
    schema=INVOKE_ROLE_SCHEMA,
    handler=lambda args, **kw: invoke_role(
        role=args.get("role"),
        plan_id=args.get("plan_id"),
        summary=args.get("summary"),
        execution_mode=args.get("execution_mode"),
        status=args.get("status", "completed"),
        packet_content=args.get("packet_content"),
        output_content=args.get("output_content"),
        evidence_content=args.get("evidence_content"),
        workspace_root=args.get("workspace_root"),
        registry_path=args.get("registry_path"),
        lead_session_id=args.get("lead_session_id"),
        task_id=kw.get("task_id"),
        session_id=kw.get("session_id"),
        user_task=kw.get("user_task"),
        session_db=kw.get("session_db"),
        role_agent_config=kw.get("role_agent_config"),
    ),
    check_fn=check_invoke_role_requirements,
    description=INVOKE_ROLE_SCHEMA["description"],
    emoji="🎭",
)
