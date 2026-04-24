from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import re
from typing import Any, Dict, Iterable, List, Optional

import yaml

DEFAULT_EXECUTION_MODE = "persistent_role_instance"
EXECUTION_MODES = (
    "persistent_role_instance",
    "delegated_subagent",
    "scheduled_role_run",
    "inline_lead_exception",
)
ROLE_SESSION_STATUSES = (
    "planned",
    "active",
    "completed",
    "blocked",
    "paused",
    "cancelled",
)
FINDING_STATUSES = (
    "open",
    "in_fix",
    "pending_revalidation",
    "closed",
    "rejected",
    "deferred",
)
PLAN_PHASES = (
    "routing",
    "planning",
    "lead_review",
    "awaiting_user_approval",
    "implementation",
    "validation",
    "specialist_review",
    "remediation",
    "complete",
)

_DEFAULT_ALLOWED_EXECUTION_MODES = [
    "persistent_role_instance",
    "delegated_subagent",
    "scheduled_role_run",
]

DEFAULT_RUNTIME_POLICY: Dict[str, Any] = {
    "default_execution_mode": DEFAULT_EXECUTION_MODE,
    "allowed_execution_modes": list(_DEFAULT_ALLOWED_EXECUTION_MODES),
    "requires_independent_session": True,
    "requires_artifact_handoff": True,
    "lead_coordinates_feedback": True,
    "lead_review_required_before_next_handoff": True,
    "requires_revalidation_after_fix": False,
    "worktree_strategy": "shared",
}

DEFAULT_ORG_CHART_REGISTRY_PATH = (
    Path(__file__).resolve().parent.parent / "web" / "src" / "data" / "hermesOrgChart.registry.yaml"
)


@dataclass(frozen=True)
class RolePolicy:
    default_execution_mode: str = DEFAULT_EXECUTION_MODE
    allowed_execution_modes: tuple[str, ...] = tuple(_DEFAULT_ALLOWED_EXECUTION_MODES)
    requires_independent_session: bool = True
    requires_artifact_handoff: bool = True
    lead_coordinates_feedback: bool = True
    lead_review_required_before_next_handoff: bool = True
    requires_revalidation_after_fix: bool = False
    worktree_strategy: str = "shared"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "default_execution_mode": self.default_execution_mode,
            "allowed_execution_modes": list(self.allowed_execution_modes),
            "requires_independent_session": self.requires_independent_session,
            "requires_artifact_handoff": self.requires_artifact_handoff,
            "lead_coordinates_feedback": self.lead_coordinates_feedback,
            "lead_review_required_before_next_handoff": self.lead_review_required_before_next_handoff,
            "requires_revalidation_after_fix": self.requires_revalidation_after_fix,
            "worktree_strategy": self.worktree_strategy,
        }


@dataclass(frozen=True)
class RoleDefinition:
    title: str
    slug: str
    payload: Dict[str, Any]
    policy: RolePolicy
    aliases: tuple[str, ...] = ()
    is_lead: bool = False


@dataclass(frozen=True)
class RoleSession:
    session_id: str
    plan_id: str
    role: str
    role_slug: str
    parent_session_id: Optional[str]
    execution_mode: str
    policy_default_execution_mode: str
    metadata: Dict[str, Any]
    created: bool = False


def _org_chart_registry_path(path: Optional[str | Path] = None) -> Path:
    return Path(path).expanduser().resolve() if path is not None else DEFAULT_ORG_CHART_REGISTRY_PATH


def load_org_chart_registry(path: Optional[str | Path] = None) -> Dict[str, Any]:
    registry_path = _org_chart_registry_path(path)
    data = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Org chart registry at {registry_path} did not parse to a mapping")
    return data


def slugify_role_name(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower())
    return text.strip("-") or "role"


def slugify_plan_id(value: str) -> str:
    return slugify_role_name(value)


def _coerce_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _normalize_allowed_modes(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        return tuple(_DEFAULT_ALLOWED_EXECUTION_MODES)
    cleaned = []
    for item in value:
        item_text = str(item or "").strip()
        if item_text in EXECUTION_MODES and item_text not in cleaned:
            cleaned.append(item_text)
    return tuple(cleaned or _DEFAULT_ALLOWED_EXECUTION_MODES)


def policy_from_payload(payload: Dict[str, Any]) -> RolePolicy:
    raw = payload.get("runtimePolicy")
    if not isinstance(raw, dict):
        raw = {}
    default_mode = str(raw.get("default_execution_mode") or DEFAULT_EXECUTION_MODE).strip()
    if default_mode not in EXECUTION_MODES:
        default_mode = DEFAULT_EXECUTION_MODE
    allowed_modes = _normalize_allowed_modes(raw.get("allowed_execution_modes"))
    if default_mode not in allowed_modes:
        allowed_modes = tuple([default_mode, *[m for m in allowed_modes if m != default_mode]])
    worktree_strategy = str(raw.get("worktree_strategy") or "shared").strip() or "shared"
    if worktree_strategy not in {"shared", "isolated_if_coding", "isolated_required"}:
        worktree_strategy = "shared"
    return RolePolicy(
        default_execution_mode=default_mode,
        allowed_execution_modes=allowed_modes,
        requires_independent_session=_coerce_bool(raw.get("requires_independent_session"), True),
        requires_artifact_handoff=_coerce_bool(raw.get("requires_artifact_handoff"), True),
        lead_coordinates_feedback=_coerce_bool(raw.get("lead_coordinates_feedback"), True),
        lead_review_required_before_next_handoff=_coerce_bool(
            raw.get("lead_review_required_before_next_handoff"), True
        ),
        requires_revalidation_after_fix=_coerce_bool(raw.get("requires_revalidation_after_fix"), False),
        worktree_strategy=worktree_strategy,
    )


def _iter_registry_roles(registry: Dict[str, Any]) -> Iterable[tuple[Dict[str, Any], bool]]:
    lead = registry.get("lead_role")
    if isinstance(lead, dict):
        yield lead, True
    for section in registry.get("org_sections") or []:
        if not isinstance(section, dict):
            continue
        for role in section.get("roles") or []:
            if isinstance(role, dict):
                yield role, False


def get_role_alias_map(registry: Optional[Dict[str, Any]] = None, path: Optional[str | Path] = None) -> Dict[str, List[str]]:
    data = registry if registry is not None else load_org_chart_registry(path)
    aliases = data.get("role_aliases") or {}
    if not isinstance(aliases, dict):
        return {}
    normalized: Dict[str, List[str]] = {}
    for role_title, items in aliases.items():
        if not isinstance(items, list):
            continue
        normalized[str(role_title)] = [str(item) for item in items if str(item or "").strip()]
    return normalized


def list_role_definitions(path: Optional[str | Path] = None, registry: Optional[Dict[str, Any]] = None) -> List[RoleDefinition]:
    data = registry if registry is not None else load_org_chart_registry(path)
    alias_map = get_role_alias_map(data)
    results: List[RoleDefinition] = []
    for payload, is_lead in _iter_registry_roles(data):
        title = str(payload.get("title") or "").strip()
        if not title:
            continue
        results.append(
            RoleDefinition(
                title=title,
                slug=slugify_role_name(title),
                payload=payload,
                policy=policy_from_payload(payload),
                aliases=tuple(alias_map.get(title, [])),
                is_lead=is_lead,
            )
        )
    return results


def role_titles(path: Optional[str | Path] = None, registry: Optional[Dict[str, Any]] = None) -> List[str]:
    return [role.title for role in list_role_definitions(path=path, registry=registry)]


def _normalize_lookup_key(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def resolve_role(value: str, path: Optional[str | Path] = None, registry: Optional[Dict[str, Any]] = None) -> RoleDefinition:
    if not str(value or "").strip():
        raise ValueError("Role value is required")
    key = _normalize_lookup_key(value)
    slug_key = slugify_role_name(value)
    for role in list_role_definitions(path=path, registry=registry):
        if _normalize_lookup_key(role.title) == key or role.slug == slug_key:
            return role
        if any(_normalize_lookup_key(alias) == key or slugify_role_name(alias) == slug_key for alias in role.aliases):
            return role
    valid = ", ".join(role_titles(path=path, registry=registry))
    raise ValueError(f"Unknown canonical role or alias '{value}'. Valid roles: {valid}")


def role_session_id(plan_id: str, role_slug: str) -> str:
    plan_slug = slugify_plan_id(plan_id)
    role_slug_clean = slugify_role_name(role_slug)
    digest = hashlib.sha1(f"{plan_slug}:{role_slug_clean}".encode("utf-8")).hexdigest()[:10]
    return f"role-{plan_slug}-{role_slug_clean}-{digest}"


def role_system_prompt(role: RoleDefinition) -> str:
    responsibilities = "\n".join(f"- {item}" for item in role.payload.get("responsibilities") or [])
    tool_focus = ", ".join(str(item) for item in role.payload.get("toolFocus") or [])
    invoke_for = "\n".join(f"- {item}" for item in role.payload.get("invokeFor") or [])
    return (
        f"You are the {role.title} role in the Hermes role-team runtime.\n"
        f"Position: {role.payload.get('position', '')}\n"
        f"Mission: {role.payload.get('mission', '')}\n"
        f"Reports to: {role.payload.get('reportsTo', 'Lead / PM')}\n\n"
        f"Responsibilities:\n{responsibilities or '- Produce the requested role handoff.'}\n\n"
        f"Activation: {role.payload.get('activation', '')}\n"
        f"Tool focus: {tool_focus}\n\n"
        f"Invoke for:\n{invoke_for or '- Role-specific work packets.'}\n\n"
        "Operating rules:\n"
        "- Work only within the role packet scope.\n"
        "- Produce an artifact-first handoff for Lead / PM.\n"
        "- Do not communicate directly with the user.\n"
        "- Send findings to Lead / PM for disposition; do not route side-channel work directly to another role.\n"
        f"Runtime policy: {json.dumps(role.policy.to_dict(), sort_keys=True)}\n"
    )


def _merge_model_config(existing_raw: Any, role_metadata: Dict[str, Any], extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if isinstance(existing_raw, str) and existing_raw.strip():
        try:
            base = json.loads(existing_raw)
        except json.JSONDecodeError:
            base = {}
    elif isinstance(existing_raw, dict):
        base = dict(existing_raw)
    else:
        base = {}
    if extra:
        base.update(extra)
    base["role_metadata"] = role_metadata
    return base


def get_or_create_role_session(
    *,
    session_db: Any,
    plan_id: str,
    role: RoleDefinition,
    parent_session_id: Optional[str],
    execution_mode: str,
    policy_default_execution_mode: str,
    task_packet_path: Optional[str] = None,
    artifact_paths: Optional[Dict[str, Any]] = None,
    model: Optional[str] = None,
    source: str = "role_runtime",
    model_config: Optional[Dict[str, Any]] = None,
) -> RoleSession:
    if session_db is None:
        raise ValueError("session_db is required to create or resume a persistent role session")
    plan_slug = slugify_plan_id(plan_id)
    role_sid = role_session_id(plan_slug, role.slug)
    role_metadata = {
        "plan_id": plan_slug,
        "role": role.title,
        "role_slug": role.slug,
        "canonical_role": role.title,
        "execution_mode": execution_mode,
        "policy_default_execution_mode": policy_default_execution_mode,
        "parent_session_id": parent_session_id,
        "persistent_session_id": role_sid,
        "status": "active",
        "task_packet_path": task_packet_path,
        "artifact_paths": artifact_paths or {},
    }
    existing = session_db.get_session(role_sid)
    created = existing is None
    if created:
        session_db.create_session(
            session_id=role_sid,
            source=source,
            model=model,
            model_config=_merge_model_config(None, role_metadata, model_config),
            parent_session_id=parent_session_id,
        )
    else:
        merged = _merge_model_config(existing.get("model_config"), role_metadata, model_config)
        def _do(conn):
            conn.execute(
                "UPDATE sessions SET model_config = ?, parent_session_id = COALESCE(parent_session_id, ?), model = COALESCE(model, ?) WHERE id = ?",
                (json.dumps(merged), parent_session_id, model, role_sid),
            )
        session_db._execute_write(_do)
        try:
            session_db.reopen_session(role_sid)
        except Exception:
            pass
    return RoleSession(
        session_id=role_sid,
        plan_id=plan_slug,
        role=role.title,
        role_slug=role.slug,
        parent_session_id=parent_session_id,
        execution_mode=execution_mode,
        policy_default_execution_mode=policy_default_execution_mode,
        metadata=role_metadata,
        created=created,
    )


def retire_role_session(
    *,
    session_db: Any,
    plan_id: str,
    role: RoleDefinition,
    status: str = "paused",
    reason: str = "role_retired",
) -> RoleSession:
    if session_db is None:
        raise ValueError("session_db is required to retire a persistent role session")
    if status not in ROLE_SESSION_STATUSES:
        raise ValueError(f"Invalid role session status '{status}'")
    plan_slug = slugify_plan_id(plan_id)
    role_sid = role_session_id(plan_slug, role.slug)
    existing = session_db.get_session(role_sid)
    if existing is None:
        raise ValueError(f"Role session '{role_sid}' does not exist")
    retired_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    existing_config = _merge_model_config(existing.get("model_config"), {})
    role_metadata = dict(existing_config.get("role_metadata") or {})
    role_metadata.update(
        {
            "plan_id": plan_slug,
            "role": role.title,
            "role_slug": role.slug,
            "canonical_role": role.title,
            "persistent_session_id": role_sid,
            "status": status,
            "retired_at": retired_at,
            "retire_reason": reason,
        }
    )
    updated_config = dict(existing_config)
    updated_config["role_metadata"] = role_metadata

    def _do(conn):
        conn.execute(
            "UPDATE sessions SET model_config = ? WHERE id = ?",
            (json.dumps(updated_config), role_sid),
        )
    session_db._execute_write(_do)
    session_db.end_session(role_sid, reason)
    return RoleSession(
        session_id=role_sid,
        plan_id=plan_slug,
        role=role.title,
        role_slug=role.slug,
        parent_session_id=existing.get("parent_session_id"),
        execution_mode=str(role_metadata.get("execution_mode") or DEFAULT_EXECUTION_MODE),
        policy_default_execution_mode=str(
            role_metadata.get("policy_default_execution_mode") or role.policy.default_execution_mode
        ),
        metadata=role_metadata,
        created=False,
    )


def default_workspace_root(workspace_root: Optional[str | Path] = None) -> Path:
    if workspace_root is not None:
        return Path(workspace_root).expanduser().resolve()
    env_cwd = os.getenv("TERMINAL_CWD")
    if env_cwd:
        return Path(env_cwd).expanduser().resolve()
    return Path.cwd().resolve()
