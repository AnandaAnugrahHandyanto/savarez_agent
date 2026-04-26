"""Capability metadata catalog for Hermes.

Phase 1A: normalize tool + skill capability metadata into a single in-memory
catalog. This is intentionally read-only and lightweight so `status` / `doctor`
can gradually migrate off scattered heuristics without a large framework rewrite.
"""

from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from tools.registry import ToolRegistry, registry as global_registry


def _normalize_check(name: str, status: str, detail: str) -> Dict[str, str]:
    return {"name": name, "status": status, "detail": detail}


def _tool_record(tool_name: str, tool_registry: ToolRegistry) -> Dict[str, Any]:
    entry = tool_registry.get_entry(tool_name)
    if entry is None:
        raise KeyError(f"Unknown tool: {tool_name}")

    toolset_ready = tool_registry.is_toolset_available(entry.toolset)
    readiness_status = "ready" if toolset_ready else "setup_needed"
    readiness_reason = (
        "toolset requirements satisfied"
        if toolset_ready
        else "toolset requirements are not currently satisfied"
    )

    return {
        "id": f"tool:{entry.name}",
        "kind": "tool",
        "name": entry.name,
        "canonical_name": entry.name,
        "source": {
            "type": "registry",
            "path": "tools/registry.py",
            "origin": entry.toolset,
        },
        "description": entry.description or entry.schema.get("description", ""),
        "group": entry.toolset,
        "platform_scope": ["all"],
        "runtime_dependencies": list(entry.runtime_dependencies),
        "required_env": list(entry.requires_env),
        "required_commands": [],
        "execution_tags": list(entry.execution_tags),
        "readiness": {
            "status": readiness_status,
            "reason": readiness_reason,
            "checks": [
                _normalize_check(
                    "toolset_available",
                    "pass" if toolset_ready else "fail",
                    f"toolset={entry.toolset}",
                )
            ],
        },
        "relationships": {
            "depends_on": [f"toolset:{entry.toolset}"],
            "provides_to": [],
            "owned_by": [],
        },
        "display": {
            "summary_surface": ["status", "doctor"],
            "priority": 50,
            "emoji": entry.emoji or None,
        },
    }


def _normalize_skill_env_requirements(raw_values: List[Any]) -> List[str]:
    normalized: List[str] = []
    for item in raw_values or []:
        if isinstance(item, dict):
            name = str(item.get("name") or "").strip()
            if name:
                normalized.append(name)
        else:
            text = str(item).strip()
            if text:
                normalized.append(text)
    return normalized


def _iter_skill_metadata(skill_roots: List[Path]) -> Iterable[Dict[str, Any]]:
    from tools.skills_tool import (
        _EXCLUDED_SKILL_DIRS,
        _collect_prerequisite_values,
        _get_category_from_path,
        _get_required_environment_variables,
        _is_env_var_persisted,
        _parse_frontmatter,
        MAX_DESCRIPTION_LENGTH,
    )

    seen_names: set[str] = set()
    for root in skill_roots:
        if not root.exists():
            continue
        for skill_md in root.rglob("SKILL.md"):
            if any(part in _EXCLUDED_SKILL_DIRS for part in skill_md.parts):
                continue
            try:
                content = skill_md.read_text(encoding="utf-8")
                frontmatter, body = _parse_frontmatter(content)
            except Exception:
                continue

            skill_name = str(frontmatter.get("name") or skill_md.parent.name).strip()
            if not skill_name or skill_name in seen_names:
                continue
            seen_names.add(skill_name)

            description = str(frontmatter.get("description") or "").strip()
            if not description:
                for line in body.strip().split("\n"):
                    line = line.strip()
                    if line and not line.startswith("#"):
                        description = line
                        break
            if len(description) > MAX_DESCRIPTION_LENGTH:
                description = description[: MAX_DESCRIPTION_LENGTH - 3] + "..."

            legacy_env_vars, legacy_commands = _collect_prerequisite_values(frontmatter)
            required_env_entries = _get_required_environment_variables(frontmatter, legacy_env_vars)
            missing_env = [
                entry["name"]
                for entry in required_env_entries
                if not entry.get("optional") and not _is_env_var_persisted(entry["name"])
            ]
            required_cred_files_raw = frontmatter.get("required_credential_files", [])
            if not isinstance(required_cred_files_raw, list):
                required_cred_files_raw = []
            missing_cred_files = [
                str(path)
                for path in required_cred_files_raw
                if not Path(os.path.expanduser(str(path))).exists()
            ]

            platforms = frontmatter.get("platforms")
            if isinstance(platforms, str):
                platforms = [platforms]
            if not isinstance(platforms, list) or not platforms:
                platform_scope = ["all"]
                supported = True
            else:
                platform_scope = [str(p).strip() for p in platforms if str(p).strip()]
                current_platform = __import__("sys").platform
                supported = any(
                    (p == "macos" and current_platform == "darwin")
                    or (p == "linux" and current_platform.startswith("linux"))
                    or (p == "windows" and current_platform == "win32")
                    for p in platform_scope
                )

            if not supported:
                readiness_status = "unsupported"
                readiness_reason = "skill is unsupported on this platform"
            elif missing_env or missing_cred_files:
                readiness_status = "setup_needed"
                missing = missing_env or missing_cred_files
                readiness_reason = f"missing prerequisites: {', '.join(missing)}"
            else:
                readiness_status = "ready"
                readiness_reason = "skill is available"

            checks: List[Dict[str, str]] = []
            required_env = _normalize_skill_env_requirements(required_env_entries)
            if required_env:
                checks.append(
                    _normalize_check(
                        "required_environment_variables",
                        "pass" if not missing_env else "fail",
                        ", ".join(required_env),
                    )
                )
            if legacy_commands:
                checks.append(
                    _normalize_check(
                        "required_commands",
                        "pass",
                        ", ".join(legacy_commands),
                    )
                )
            if missing_cred_files:
                checks.append(
                    _normalize_check(
                        "required_credential_files",
                        "fail",
                        ", ".join(missing_cred_files),
                    )
                )
            if not checks:
                checks.append(_normalize_check("skill_metadata", "pass", "skill metadata loaded"))

            yield {
                "id": f"skill:{skill_name}",
                "kind": "skill",
                "name": skill_name,
                "canonical_name": skill_name,
                "source": {
                    "type": "skill_frontmatter",
                    "path": str(skill_md),
                    "origin": str(skill_md.parent),
                },
                "description": description,
                "group": "skill",
                "platform_scope": platform_scope,
                "runtime_dependencies": [],
                "required_env": required_env,
                "required_commands": list(legacy_commands),
                "execution_tags": [],
                "readiness": {
                    "status": readiness_status,
                    "reason": readiness_reason,
                    "checks": checks,
                },
                "relationships": {
                    "depends_on": [],
                    "provides_to": [],
                    "owned_by": [f"category:{_get_category_from_path(skill_md) or 'none'}"],
                },
                "display": {
                    "summary_surface": ["status", "doctor", "skills_hub"],
                    "priority": 40,
                    "emoji": None,
                },
            }


def _skill_record(skill: Dict[str, Any], task_id: str | None = None) -> Dict[str, Any]:
    raise NotImplementedError("Use _iter_skill_metadata() for read-only skill catalog ingestion")


def build_capability_catalog(
    *,
    tool_registry: ToolRegistry | None = None,
    skills_dir: Path | None = None,
    task_id: str | None = None,
) -> Dict[str, Any]:
    """Build an in-memory capability catalog.

    Phase 1A intentionally limits scope to tools and skills, but the returned
    object shape leaves room for MCP/auth/automation surfaces later.
    """
    tool_registry = tool_registry or global_registry

    records: List[Dict[str, Any]] = []
    for tool_name in tool_registry.get_all_tool_names():
        records.append(_tool_record(tool_name, tool_registry))

    skill_roots = [Path(skills_dir)] if skills_dir is not None else []
    if not skill_roots:
        from tools.skills_tool import SKILLS_DIR
        from agent.skill_utils import get_external_skills_dirs

        skill_roots = [SKILLS_DIR, *get_external_skills_dirs()]

    records.extend(_iter_skill_metadata(skill_roots))

    by_kind = dict(sorted(Counter(record["kind"] for record in records).items()))

    return {
        "records": sorted(records, key=lambda item: (item["kind"], item["canonical_name"])),
        "counts": by_kind,
    }


def list_capabilities(*, kind: str | None = None, catalog: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    catalog = catalog or build_capability_catalog()
    records = catalog.get("records", [])
    if kind is None:
        return records
    return [record for record in records if record.get("kind") == kind]


def get_capability(capability_id: str, *, catalog: Dict[str, Any] | None = None) -> Optional[Dict[str, Any]]:
    catalog = catalog or build_capability_catalog()
    for record in catalog.get("records", []):
        if record.get("id") == capability_id:
            return record
    return None


def summarize_capability_health(catalog: Dict[str, Any] | None = None) -> Dict[str, Any]:
    catalog = catalog or build_capability_catalog()
    records = catalog.get("records", [])
    return {
        "total": len(records),
        "by_kind": dict(sorted(Counter(record["kind"] for record in records).items())),
        "by_status": dict(sorted(Counter(record["readiness"]["status"] for record in records).items())),
    }


def summarize_repo_context_capabilities(catalog: Dict[str, Any] | None = None) -> List[Dict[str, str]]:
    """Return repo-context/indexing capability summaries for status/doctor surfaces."""
    catalog = catalog or build_capability_catalog()
    records = catalog.get("records", [])
    summaries: List[Dict[str, str]] = []
    seen_keys: set[tuple[str, str]] = set()

    for record in records:
        if record.get("kind") != "tool":
            continue
        execution_tags = set(record.get("execution_tags") or [])
        if "indexing_workflow" not in execution_tags:
            continue

        name = str(record.get("canonical_name") or record.get("name") or "")
        summary = {
            "name": name,
            "group": str(record.get("group") or ""),
            "readiness_status": str((record.get("readiness") or {}).get("status") or "unknown"),
            "identity_scope": "absolute_path" if name.startswith("mcp_claude_context_") else "tool_defined",
            "workflow": "index/status/search/clear",
            "result_mode": "partial_or_complete",
        }
        summaries.append(summary)
        seen_keys.add((summary["group"], summary["name"]))

    try:
        from tools.mcp_tool import _KNOWN_MCP_RUNTIME_PROFILES, _load_mcp_config

        configured_servers = _load_mcp_config()
        for server_name in configured_servers:
            server_profile = _KNOWN_MCP_RUNTIME_PROFILES.get(server_name, {})
            if not any("indexing_workflow" in (meta.get("execution_tags") or []) for meta in server_profile.values()):
                continue
            for tool_name, meta in server_profile.items():
                if "indexing_workflow" not in (meta.get("execution_tags") or []):
                    continue
                group = f"mcp-{server_name}"
                canonical_name = f"mcp_{server_name.replace('-', '_')}_{tool_name}"
                key = (group, canonical_name)
                if key in seen_keys:
                    continue
                summaries.append(
                    {
                        "name": canonical_name,
                        "group": group,
                        "readiness_status": "configured",
                        "identity_scope": "absolute_path" if server_name == "claude-context" else "tool_defined",
                        "workflow": "index/status/search/clear",
                        "result_mode": "partial_or_complete",
                    }
                )
                seen_keys.add(key)
    except Exception:
        pass

    return sorted(summaries, key=lambda item: (item["group"], item["name"]))
