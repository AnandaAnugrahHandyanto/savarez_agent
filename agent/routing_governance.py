"""Routing governance helpers for provider/smart-routing policy and rollout state."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hermes_constants import get_hermes_home

_SCHEMA_VERSION = 1
_ROLLOUT_FILE = "model_routing_rollout.json"
_ALLOWED_PROVIDER_SORT = {"price", "throughput", "latency"}
_ALLOWED_DATA_COLLECTION = {"allow", "deny", None}
_ALLOWED_ROLLOUT_MODES = {"manual", "canary", "disabled"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rollout_state_path() -> Path:
    return get_hermes_home() / _ROLLOUT_FILE


def _base_rollout_state() -> dict[str, Any]:
    return {
        "schema_version": _SCHEMA_VERSION,
        "updated_at": _utc_now_iso(),
        "current_route": None,
        "previous_route": None,
        "qualified_routes": [],
        "rollout": {
            "mode": "manual",
            "max_percent": 100,
        },
        "rollback": {
            "available": False,
            "reason": None,
            "at": None,
            "from_route": None,
        },
    }


def validate_provider_routing_config(config: Any) -> list[str]:
    errors: list[str] = []
    if config in (None, {}):
        return errors
    if not isinstance(config, dict):
        return ["provider_routing must be an object"]

    sort = config.get("sort")
    if sort is not None and sort not in _ALLOWED_PROVIDER_SORT:
        errors.append(f"provider_routing.sort must be one of {sorted(_ALLOWED_PROVIDER_SORT)}")

    for key in ("only", "ignore", "order"):
        value = config.get(key)
        if value is None:
            continue
        if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
            errors.append(f"provider_routing.{key} must be a list of non-empty strings")

    require_parameters = config.get("require_parameters")
    if require_parameters is not None and not isinstance(require_parameters, bool):
        errors.append("provider_routing.require_parameters must be a boolean")

    data_collection = config.get("data_collection")
    if data_collection not in _ALLOWED_DATA_COLLECTION:
        errors.append("provider_routing.data_collection must be 'allow', 'deny', or null")

    return errors


def validate_smart_model_routing_config(config: Any) -> list[str]:
    errors: list[str] = []
    if config in (None, {}):
        return errors
    if not isinstance(config, dict):
        return ["smart_model_routing must be an object"]

    enabled = config.get("enabled")
    if enabled is not None and not isinstance(enabled, bool):
        errors.append("smart_model_routing.enabled must be a boolean")

    for key in ("max_simple_chars", "max_simple_words"):
        value = config.get(key)
        if value is None:
            continue
        if not isinstance(value, int) or value <= 0:
            errors.append(f"smart_model_routing.{key} must be a positive integer")

    require_qualified = config.get("require_qualified")
    if require_qualified is not None and not isinstance(require_qualified, bool):
        errors.append("smart_model_routing.require_qualified must be a boolean")

    cheap_model = config.get("cheap_model")
    if cheap_model not in (None, {}):
        if not isinstance(cheap_model, dict):
            errors.append("smart_model_routing.cheap_model must be an object")
        else:
            provider = cheap_model.get("provider")
            model = cheap_model.get("model")
            if provider is not None and (not isinstance(provider, str) or not provider.strip()):
                errors.append("smart_model_routing.cheap_model.provider must be a non-empty string")
            if model is not None and (not isinstance(model, str) or not model.strip()):
                errors.append("smart_model_routing.cheap_model.model must be a non-empty string")

    rollout = config.get("rollout")
    if rollout not in (None, {}):
        if not isinstance(rollout, dict):
            errors.append("smart_model_routing.rollout must be an object")
        else:
            mode = rollout.get("mode")
            if mode is not None and mode not in _ALLOWED_ROLLOUT_MODES:
                errors.append(f"smart_model_routing.rollout.mode must be one of {sorted(_ALLOWED_ROLLOUT_MODES)}")
            max_percent = rollout.get("max_percent")
            if max_percent is not None and (
                not isinstance(max_percent, int) or max_percent < 0 or max_percent > 100
            ):
                errors.append("smart_model_routing.rollout.max_percent must be an integer between 0 and 100")

    return errors


def read_rollout_state() -> dict[str, Any]:
    path = _rollout_state_path()
    if not path.exists():
        return _base_rollout_state()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _base_rollout_state()
    if not isinstance(payload, dict):
        return _base_rollout_state()
    merged = _base_rollout_state()
    merged.update(payload)
    return merged


def write_rollout_state(payload: dict[str, Any]) -> dict[str, Any]:
    state = _base_rollout_state()
    state.update(payload)
    state["schema_version"] = _SCHEMA_VERSION
    state["updated_at"] = _utc_now_iso()
    path = _rollout_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    return state


def route_matches_qualified(provider: str, model: str) -> bool:
    state = read_rollout_state()
    for route in state.get("qualified_routes", []):
        if route.get("provider") == provider and route.get("model") == model:
            return True
    return False


def promote_route(*, provider: str, model: str, reason: str, rollout: dict[str, Any] | None = None) -> dict[str, Any]:
    state = read_rollout_state()
    current = state.get("current_route")
    route = {
        "provider": provider,
        "model": model,
        "promoted_at": _utc_now_iso(),
        "qualification_reason": reason,
    }
    qualified = [
        item for item in state.get("qualified_routes", [])
        if not (item.get("provider") == provider and item.get("model") == model)
    ]
    qualified.append(route)
    state["previous_route"] = current
    state["current_route"] = route
    state["qualified_routes"] = qualified
    state["rollback"] = {
        "available": current is not None,
        "reason": None,
        "at": None,
        "from_route": current,
    }
    if rollout:
        state["rollout"] = {
            "mode": rollout.get("mode", state.get("rollout", {}).get("mode", "manual")),
            "max_percent": rollout.get("max_percent", state.get("rollout", {}).get("max_percent", 100)),
        }
    return write_rollout_state(state)


def rollback_route(*, reason: str) -> dict[str, Any]:
    state = read_rollout_state()
    current = state.get("current_route")
    state["previous_route"] = current
    state["current_route"] = None
    state["rollback"] = {
        "available": current is not None,
        "reason": reason,
        "at": _utc_now_iso(),
        "from_route": current,
    }
    return write_rollout_state(state)
