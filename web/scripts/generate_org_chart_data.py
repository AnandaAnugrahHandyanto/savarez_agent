from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Any
import json

from agent.role_runtime import load_org_chart_registry

ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = ROOT / "src" / "data" / "hermesOrgChart.registry.yaml"
OUTPUT_PATH = ROOT / "src" / "data" / "hermesOrgChart.generated.ts"


class TSExpr(str):
    """Raw TypeScript expression that should not be JSON-quoted."""


def _to_ts(value: Any, indent: int = 0) -> str:
    pad = "  " * indent
    next_pad = "  " * (indent + 1)
    if isinstance(value, TSExpr):
        return str(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return json.dumps(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        if not value:
            return "[]"
        rendered = [f"{next_pad}{_to_ts(item, indent + 1)}" for item in value]
        return "[\n" + ",\n".join(rendered) + f"\n{pad}]"
    if isinstance(value, dict):
        if not value:
            return "{}"
        rendered = []
        for key, item in value.items():
            rendered.append(f"{next_pad}{_ts_key(key)}: {_to_ts(item, indent + 1)}")
        return "{\n" + ",\n".join(rendered) + f"\n{pad}}}"
    raise TypeError(f"Unsupported value for TS rendering: {type(value)!r}")


def _ts_key(key: str) -> str:
    key_text = str(key)
    if key_text.isidentifier():
        return key_text
    return json.dumps(key_text, ensure_ascii=False)


def _normalize_role_payload(role: dict[str, Any]) -> dict[str, Any]:
    payload = OrderedDict()
    for key, value in role.items():
        if key == "icon":
            payload[key] = TSExpr(str(value))
        elif key == "runtimePolicy" and isinstance(value, dict):
            policy = OrderedDict()
            for policy_key, policy_value in value.items():
                policy[policy_key] = policy_value
            payload[key] = policy
        else:
            payload[key] = value
    return payload


def _icon_names(registry: dict[str, Any]) -> list[str]:
    seen: OrderedDict[str, None] = OrderedDict()
    lead = registry.get("lead_role") or {}
    if isinstance(lead, dict):
        icon = lead.get("icon")
        if icon:
            seen[str(icon)] = None
    for section in registry.get("org_sections") or []:
        if not isinstance(section, dict):
            continue
        for role in section.get("roles") or []:
            if not isinstance(role, dict):
                continue
            icon = role.get("icon")
            if icon:
                seen[str(icon)] = None
    return list(seen.keys())


def generate_typescript_module(registry_path: str | Path = REGISTRY_PATH) -> str:
    registry = load_org_chart_registry(registry_path)

    lead_role = _normalize_role_payload(dict(registry.get("lead_role") or {}))
    role_aliases = OrderedDict((str(k), list(v)) for k, v in (registry.get("role_aliases") or {}).items())

    sections = []
    for section in registry.get("org_sections") or []:
        if not isinstance(section, dict):
            continue
        normalized = OrderedDict()
        for key, value in section.items():
            if key == "roles":
                normalized[key] = [_normalize_role_payload(dict(role)) for role in value or []]
            else:
                normalized[key] = value
        sections.append(normalized)

    workflow_steps = list(registry.get("workflow_steps") or [])
    verification_levels = list(registry.get("verification_levels") or [])
    invoke_matrix = list(registry.get("invoke_matrix") or [])
    icons = _icon_names(registry)
    icons_import = ",\n  ".join(icons)

    return f'''/* AUTO-GENERATED FILE. DO NOT EDIT DIRECTLY. */
/* Source: hermesOrgChart.registry.yaml */
import type {{ LucideIcon }} from "lucide-react";
import {{
  {icons_import}
}} from "lucide-react";

export type ExecutionMode = "persistent_role_instance" | "delegated_subagent" | "scheduled_role_run" | "inline_lead_exception";
export type WorktreeStrategy = "shared" | "isolated_if_coding" | "isolated_required";

export interface RuntimePolicy {{
  default_execution_mode: ExecutionMode;
  allowed_execution_modes: ExecutionMode[];
  requires_independent_session: boolean;
  requires_artifact_handoff: boolean;
  lead_coordinates_feedback: boolean;
  lead_review_required_before_next_handoff: boolean;
  requires_revalidation_after_fix: boolean;
  worktree_strategy: WorktreeStrategy;
}}

export interface OrgRole {{
  title: string;
  position: string;
  mission: string;
  responsibilities: string[];
  activation: string;
  reportsTo: string;
  model: string;
  toolFocus: string[];
  invokeFor: string[];
  icon: LucideIcon;
  tone?: "default" | "success" | "warning";
  runtimePolicy: RuntimePolicy;
}}

export interface OrgSection {{
  id: string;
  title: string;
  description: string;
  lane: string;
  roles: OrgRole[];
}}

export interface InvokeRow {{
  trigger: string;
  primary: string;
  supporting: string[];
  verification: string;
}}

export interface VerificationLevel {{
  id: string;
  label: string;
  detail: string;
}}

export const LEAD_ROLE: OrgRole = {_to_ts(lead_role)};

export const ROLE_ALIASES: Record<string, string[]> = {_to_ts(role_aliases)};

export const ORG_SECTIONS: OrgSection[] = {_to_ts(sections)};

export const WORKFLOW_STEPS = {_to_ts(workflow_steps)};

export const VERIFICATION_LEVELS: VerificationLevel[] = {_to_ts(verification_levels)};

export const INVOKE_MATRIX: InvokeRow[] = {_to_ts(invoke_matrix)};

export const DEFAULT_OPEN_SECTIONS: Record<string, boolean> = Object.fromEntries(
  ORG_SECTIONS.map((section) => [section.id, true]),
);
'''


def write_generated_module(
    registry_path: str | Path = REGISTRY_PATH,
    output_path: str | Path = OUTPUT_PATH,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(generate_typescript_module(registry_path), encoding="utf-8")
    return output


def main() -> int:
    write_generated_module()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
