from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

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
SKILL_POLICY_SOURCE = "hermesOrgChart.registry.yaml"
MAX_LOADED_SKILL_BYTES = 100_000
_SAFE_SKILL_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


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


def _skill_policy(role_payload: Dict[str, Any]) -> Dict[str, Any]:
    raw = role_payload.get("skills") if isinstance(role_payload, dict) else None
    raw = raw if isinstance(raw, dict) else {}
    triggered = raw.get("triggered") if isinstance(raw.get("triggered"), list) else []
    normalized_triggered = [item for item in triggered if isinstance(item, dict)]
    return {
        "required": list(raw.get("required") or []),
        "recommended": list(raw.get("recommended") or []),
        "triggered": normalized_triggered,
    }


def _skill_policy_markdown(policy: Dict[str, Any], skill_compliance: str) -> str:
    lines = [
        "## Skill policy",
        "",
        f"Skill compliance: `{skill_compliance}` (required skill content was resolved before packet handoff).",
        "",
    ]
    for label, key in (("Required", "required"), ("Recommended", "recommended")):
        values = [str(item) for item in policy.get(key) or []]
        lines.append(f"### {label}")
        lines.extend(f"- `{item}`" for item in values)
        if not values:
            lines.append("- _None declared._")
        lines.append("")
    lines.append("### Triggered")
    triggered = policy.get("triggered") or []
    if triggered:
        for item in triggered:
            skill = item.get("skill")
            when = item.get("when")
            lines.append(f"- `{skill}` — {when}")
    else:
        lines.append("- _None declared._")
    return "\n".join(lines).rstrip() + "\n"


def _packet_with_skill_policy(packet_body: str, policy: Dict[str, Any], skill_compliance: str) -> str:
    if "## Skill policy" in packet_body:
        return packet_body
    return packet_body.rstrip() + "\n\n" + _skill_policy_markdown(policy, skill_compliance)


def _candidate_workspace_skill_paths(skill_name: str, workspace_root: Path) -> List[Path]:
    if not _SAFE_SKILL_NAME_RE.fullmatch(skill_name):
        return []
    root = workspace_root.resolve()
    candidates: List[Path] = []
    for base in (
        root / "_docs" / "codex-skills",
        root / ".agents" / "skills",
    ):
        try:
            base_resolved = base.resolve()
            base_resolved.relative_to(root)
            skill_md = (base / skill_name / "SKILL.md").resolve()
            skill_md.relative_to(base_resolved)
        except (OSError, ValueError):
            continue
        candidates.append(skill_md)
    return candidates


def _load_installed_skill(skill_name: str, role_session_id: Optional[str]) -> Optional[Dict[str, Any]]:
    try:
        from tools.skills_tool import skill_view
        loaded = json.loads(skill_view(skill_name, task_id=role_session_id))
    except Exception:
        return None
    if not isinstance(loaded, dict) or not loaded.get("success"):
        return None
    content = str(loaded.get("content") or loaded.get("raw_content") or "").strip()
    if not content or len(content.encode("utf-8")) > MAX_LOADED_SKILL_BYTES:
        return None
    return {
        "name": str(loaded.get("name") or skill_name),
        "source": "installed",
        "path": str(loaded.get("path") or ""),
        "skill_dir": str(loaded.get("skill_dir") or ""),
        "content": content,
    }


def _load_workspace_skill(skill_name: str, workspace_root: Path) -> Optional[Dict[str, Any]]:
    for skill_md in _candidate_workspace_skill_paths(skill_name, workspace_root):
        if not skill_md.is_file():
            continue
        try:
            if skill_md.stat().st_size > MAX_LOADED_SKILL_BYTES:
                continue
            content = skill_md.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if not content or len(content.encode("utf-8")) > MAX_LOADED_SKILL_BYTES:
            continue
        name = skill_name
        try:
            from agent.skill_utils import parse_frontmatter
            frontmatter, _ = parse_frontmatter(content)
            if isinstance(frontmatter, dict) and frontmatter.get("name"):
                name = str(frontmatter["name"])
        except Exception:
            pass
        return {
            "name": name,
            "source": "workspace",
            "path": str(skill_md),
            "skill_dir": str(skill_md.parent),
            "content": content,
        }
    return None


def _load_required_skill_documents(
    policy: Dict[str, Any],
    workspace_root: Path,
    role_session_id: Optional[str],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    loaded: List[Dict[str, Any]] = []
    missing: List[str] = []
    seen: set[str] = set()
    loaded_bytes = 0
    for raw_name in policy.get("required") or []:
        skill_name = str(raw_name or "").strip()
        if not skill_name or skill_name in seen:
            continue
        seen.add(skill_name)
        if not _SAFE_SKILL_NAME_RE.fullmatch(skill_name):
            missing.append(skill_name)
            continue
        doc = _load_installed_skill(skill_name, role_session_id) or _load_workspace_skill(skill_name, workspace_root)
        if doc:
            content_bytes = len(str(doc.get("content") or "").encode("utf-8"))
            if loaded_bytes + content_bytes > MAX_LOADED_SKILL_BYTES:
                missing.append(skill_name)
                continue
            loaded.append(doc)
            loaded_bytes += content_bytes
        else:
            missing.append(skill_name)
    return loaded, missing


def _loaded_required_skills_markdown(loaded_skills: List[Dict[str, Any]], missing_skills: List[str]) -> str:
    lines = ["## Loaded required skill content", ""]
    if loaded_skills:
        for item in loaded_skills:
            name = str(item.get("name") or "").strip()
            source = str(item.get("source") or "unknown")
            path = str(item.get("path") or "").strip()
            lines.append(f"### {name}")
            lines.append(f"- source: `{source}`")
            if path:
                lines.append(f"- path: `{path}`")
            lines.append("")
            lines.append(str(item.get("content") or "").strip())
            lines.append("")
    else:
        lines.append("_No required skill content was loaded._")
        lines.append("")
    if missing_skills:
        lines.append("### Missing required skills")
        lines.extend(f"- `{name}`" for name in missing_skills)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _packet_with_loaded_required_skills(
    packet_body: str,
    loaded_skills: List[Dict[str, Any]],
    missing_skills: List[str],
) -> str:
    return packet_body.rstrip() + "\n\n" + _loaded_required_skills_markdown(loaded_skills, missing_skills)


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

    skill_policy = _skill_policy(role_def.payload)
    loaded_required_skills, missing_required_skills = _load_required_skill_documents(
        skill_policy,
        workspace,
        role_sid,
    )
    skill_compliance = "verified" if not missing_required_skills else "partial"
    packet_body = _packet_with_skill_policy(
        packet_content or _default_packet(role_def.title, plan_id, summary, chosen_mode, status),
        skill_policy,
        skill_compliance,
    )
    packet_body = _packet_with_loaded_required_skills(
        packet_body,
        loaded_required_skills,
        missing_required_skills,
    )
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
        "skill_policy_source": "hermesOrgChart.registry.yaml",
        "skill_compliance": skill_compliance,
        "required_skills": list(skill_policy.get("required") or []),
        "recommended_skills": list(skill_policy.get("recommended") or []),
        "triggered_skills": list(skill_policy.get("triggered") or []),
        "loaded_required_skills": [str(item.get("name") or "") for item in loaded_required_skills],
        "missing_required_skills": list(missing_required_skills),
        "loaded_skill_sources": [
            {
                "name": str(item.get("name") or ""),
                "source": str(item.get("source") or ""),
                "path": str(item.get("path") or ""),
            }
            for item in loaded_required_skills
        ],
        "skill_policy": skill_policy,
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
        "skill_policy_source": "hermesOrgChart.registry.yaml",
        "skill_compliance": skill_compliance,
        "required_skills": list(skill_policy.get("required") or []),
        "recommended_skills": list(skill_policy.get("recommended") or []),
        "triggered_skills": list(skill_policy.get("triggered") or []),
        "loaded_required_skills": [str(item.get("name") or "") for item in loaded_required_skills],
        "missing_required_skills": list(missing_required_skills),
        "loaded_skill_sources": [
            {
                "name": str(item.get("name") or ""),
                "source": str(item.get("source") or ""),
                "path": str(item.get("path") or ""),
            }
            for item in loaded_required_skills
        ],
        "skill_policy": skill_policy,
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
            "skill_policy_source": "hermesOrgChart.registry.yaml",
            "skill_compliance": skill_compliance,
            "required_skills": list(skill_policy.get("required") or []),
            "recommended_skills": list(skill_policy.get("recommended") or []),
            "triggered_skills": list(skill_policy.get("triggered") or []),
            "loaded_required_skills": [str(item.get("name") or "") for item in loaded_required_skills],
            "missing_required_skills": list(missing_required_skills),
            "loaded_skill_sources": [
                {
                    "name": str(item.get("name") or ""),
                    "source": str(item.get("source") or ""),
                    "path": str(item.get("path") or ""),
                }
                for item in loaded_required_skills
            ],
            "skill_policy": skill_policy,
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
