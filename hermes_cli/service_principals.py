from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hermes_constants import get_hermes_home

_DEFAULT_POLICY_FILENAME = "service_principals.json"


def default_policy_path() -> Path:
    return get_hermes_home() / _DEFAULT_POLICY_FILENAME


def load_service_principals_policy(path: str | Path | None = None) -> dict[str, Any]:
    policy_path = Path(path) if path else default_policy_path()
    if not policy_path.exists():
        return {"version": 1, "default_deny": True, "principals": {}}
    raw = policy_path.read_text(encoding="utf-8")
    data = json.loads(raw) if raw.strip() else {}
    if not isinstance(data, dict):
        raise ValueError("service principals policy must be a JSON object")
    principals = data.get("principals")
    if principals is None:
        data["principals"] = {}
    elif not isinstance(principals, dict):
        raise ValueError("service principals policy 'principals' must be an object")
    data.setdefault("version", 1)
    data.setdefault("default_deny", True)
    return data


def resolve_canonical_principal(
    principal: str,
    *,
    aliases: list[str] | tuple[str, ...] | set[str] | None = None,
    policy: dict[str, Any] | None = None,
) -> str | None:
    value = str(principal or "").strip()
    alias_values = {
        str(item).strip()
        for item in (aliases or [])
        if isinstance(item, str) and str(item).strip()
    }
    if value:
        alias_values.add(value)
    if not alias_values:
        return None

    active_policy = policy or {"principals": {}}
    principals = active_policy.get("principals", {})
    if not isinstance(principals, dict):
        return None

    for canonical, cfg in principals.items():
        canonical_value = str(canonical or "").strip()
        if not canonical_value:
            continue
        cfg_dict = cfg if isinstance(cfg, dict) else {}
        known_aliases = {
            str(item).strip()
            for item in cfg_dict.get("aliases", [])
            if isinstance(item, str) and str(item).strip()
        }
        known_aliases.add(canonical_value)
        if alias_values & known_aliases:
            return canonical_value
    return value if value else None


def allowed_services_for_principal(
    principal: str,
    *,
    aliases: list[str] | tuple[str, ...] | set[str] | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    active_policy = policy or load_service_principals_policy()
    canonical = resolve_canonical_principal(principal, aliases=aliases, policy=active_policy)
    if not canonical:
        return {}
    principals = active_policy.get("principals", {})
    cfg = principals.get(canonical, {}) if isinstance(principals, dict) else {}
    services = cfg.get("services", {}) if isinstance(cfg, dict) else {}
    if not isinstance(services, dict):
        return {}
    return {
        str(name): service_cfg
        for name, service_cfg in services.items()
        if isinstance(name, str) and isinstance(service_cfg, dict) and bool(service_cfg.get("allow"))
    }


def is_service_allowed(
    service: str,
    principal: str,
    *,
    aliases: list[str] | tuple[str, ...] | set[str] | None = None,
    policy: dict[str, Any] | None = None,
) -> bool:
    service_name = str(service or "").strip().lower()
    if not service_name:
        return False
    allowed = allowed_services_for_principal(principal, aliases=aliases, policy=policy)
    return service_name in {
        name.strip().lower()
        for name in allowed
        if isinstance(name, str) and name.strip()
    }

