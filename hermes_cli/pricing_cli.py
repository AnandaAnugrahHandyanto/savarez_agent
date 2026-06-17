from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import yaml

from hermes_cli.config import ensure_hermes_home, get_config_path


_ALLOWED_BILLING_MODES = {"user_override", "custom_contract"}


def _read_user_config() -> dict[str, Any]:
    config_path = get_config_path()
    if not config_path.exists():
        return {}
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        raise SystemExit(f"Could not parse existing config.yaml at {config_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"Existing config.yaml at {config_path} does not contain a mapping")
    return data


def _write_user_config(config: dict[str, Any]) -> Path:
    ensure_hermes_home()
    config_path = get_config_path()
    from utils import atomic_yaml_write

    atomic_yaml_write(config_path, config, sort_keys=False)
    return config_path


def _custom_overrides(config: dict[str, Any], *, create: bool = False) -> Optional[dict[str, Any]]:
    pricing = config.get("pricing")
    if not isinstance(pricing, dict):
        if not create:
            return None
        pricing = {}
        config["pricing"] = pricing
    overrides = pricing.get("custom_overrides")
    if not isinstance(overrides, dict):
        if not create:
            return None
        overrides = {}
        pricing["custom_overrides"] = overrides
    if create:
        overrides.setdefault("enabled", True)
        overrides.setdefault("currency", "USD")
        overrides.setdefault("active_plans", {})
        overrides.setdefault("providers", [])
        if not isinstance(overrides.get("active_plans"), dict):
            overrides["active_plans"] = {}
        if not isinstance(overrides.get("providers"), list):
            overrides["providers"] = []
    return overrides


def _normalize_provider(value: Any) -> str:
    return str(value or "").strip().lower()


def _normalize_plan(value: Any) -> str:
    return str(value or "").strip()


def _find_bucket(providers: list[Any], provider: str, plan: str) -> Optional[dict[str, Any]]:
    for item in providers:
        if not isinstance(item, dict):
            continue
        if _normalize_provider(item.get("provider")) != provider:
            continue
        if _normalize_plan(item.get("plan")) != plan:
            continue
        return item
    return None


def _get_or_create_bucket(overrides: dict[str, Any], provider: str, plan: str) -> dict[str, Any]:
    providers = overrides.setdefault("providers", [])
    if not isinstance(providers, list):
        providers = []
        overrides["providers"] = providers
    bucket = _find_bucket(providers, provider, plan)
    if bucket is not None:
        bucket.setdefault("provider", provider)
        if plan:
            bucket.setdefault("plan", plan)
        bucket.setdefault("models", [])
        return bucket
    bucket = {"provider": provider, "models": []}
    if plan:
        bucket["plan"] = plan
    providers.append(bucket)
    return bucket


def _find_model_entry(bucket: dict[str, Any], model: str) -> Optional[dict[str, Any]]:
    models = bucket.get("models")
    if not isinstance(models, list):
        return None
    target = str(model or "").strip().lower()
    for item in models:
        if not isinstance(item, dict):
            continue
        if str(item.get("model", "")).strip().lower() == target:
            return item
    return None


def _get_or_create_model_entry(bucket: dict[str, Any], model: str) -> dict[str, Any]:
    models = bucket.get("models")
    if not isinstance(models, list):
        models = []
        bucket["models"] = models
    entry = _find_model_entry(bucket, model)
    if entry is not None:
        return entry
    entry = {"model": model}
    models.append(entry)
    return entry


def _set_if_present(target: dict[str, Any], key: str, value: Any) -> None:
    if value is not None:
        target[key] = value


def _pricing_payload_from_args(args) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    _set_if_present(payload, "input_cost_per_million", getattr(args, "input_cost_per_million", None))
    _set_if_present(payload, "output_cost_per_million", getattr(args, "output_cost_per_million", None))
    _set_if_present(payload, "cache_read_cost_per_million", getattr(args, "cache_read_cost_per_million", None))
    _set_if_present(payload, "cache_write_cost_per_million", getattr(args, "cache_write_cost_per_million", None))
    _set_if_present(payload, "request_cost", getattr(args, "request_cost", None))
    reason = getattr(args, "reason", None)
    if reason:
        payload["reason"] = reason
    effective_from = getattr(args, "effective_from", None)
    if effective_from:
        payload["effective_from"] = effective_from
    effective_until = getattr(args, "effective_until", None)
    if effective_until:
        payload["effective_until"] = effective_until
    return payload


def _print_bucket(bucket: dict[str, Any], *, active_plan: str = "") -> None:
    provider = bucket.get("provider", "")
    plan = bucket.get("plan", "")
    label = provider
    if plan:
        label += f" [plan={plan}]"
        if plan == active_plan:
            label += " (active)"
    billing_mode = bucket.get("billing_mode", "user_override")
    print(f"- provider: {label}")
    print(f"  billing_mode: {billing_mode}")
    default_payload = bucket.get("default")
    if isinstance(default_payload, dict) and default_payload:
        print("  default:")
        for key, value in default_payload.items():
            print(f"    {key}: {value}")
    models = bucket.get("models") or []
    if models:
        print("  models:")
        for item in models:
            if not isinstance(item, dict):
                continue
            model = item.get("model", "")
            print(f"    - model: {model}")
            for key, value in item.items():
                if key == "model":
                    continue
                print(f"      {key}: {value}")


def list_pricing() -> int:
    config = _read_user_config()
    overrides = _custom_overrides(config, create=False)
    if not overrides or not overrides.get("providers"):
        print("No custom pricing overrides configured.")
        return 0
    enabled = bool(overrides.get("enabled", False))
    currency = overrides.get("currency", "USD")
    print(f"Custom pricing overrides: {'enabled' if enabled else 'disabled'}")
    print(f"Currency: {currency}")
    active_plans_raw = overrides.get("active_plans")
    active_plans: dict[str, Any] = active_plans_raw if isinstance(active_plans_raw, dict) else {}
    if active_plans:
        print("Active plans:")
        for provider, plan in sorted(active_plans.items()):
            print(f"  {provider}: {plan}")
    print("Providers:")
    for bucket in overrides.get("providers", []):
        if not isinstance(bucket, dict):
            continue
        provider = _normalize_provider(bucket.get("provider"))
        _print_bucket(bucket, active_plan=str(active_plans.get(provider, "")))
    return 0


def set_pricing(args) -> int:
    provider = _normalize_provider(getattr(args, "provider", ""))
    if not provider:
        raise SystemExit("--provider is required")
    plan = _normalize_plan(getattr(args, "plan", ""))
    billing_mode = getattr(args, "billing_mode", None)
    if billing_mode and billing_mode not in _ALLOWED_BILLING_MODES:
        raise SystemExit("--billing-mode must be one of: user_override, custom_contract")

    config = _read_user_config()
    overrides = _custom_overrides(config, create=True)
    assert overrides is not None
    bucket = _get_or_create_bucket(overrides, provider, plan)
    if billing_mode:
        bucket["billing_mode"] = billing_mode

    payload = _pricing_payload_from_args(args)
    model = getattr(args, "model", None)
    if model:
        entry = _get_or_create_model_entry(bucket, model)
        entry.update(payload)
    else:
        default_payload = bucket.get("default")
        if not isinstance(default_payload, dict):
            default_payload = {}
            bucket["default"] = default_payload
        default_payload.update(payload)

    if getattr(args, "activate_plan", False):
        active_plans = overrides.setdefault("active_plans", {})
        if not isinstance(active_plans, dict):
            active_plans = {}
            overrides["active_plans"] = active_plans
        if not plan:
            raise SystemExit("--activate-plan requires --plan")
        active_plans[provider] = plan

    config_path = _write_user_config(config)
    print(f"Saved pricing override in {config_path}")
    return 0


def remove_pricing(args) -> int:
    provider = _normalize_provider(getattr(args, "provider", ""))
    if not provider:
        raise SystemExit("--provider is required")
    plan = _normalize_plan(getattr(args, "plan", ""))
    model = getattr(args, "model", None)

    config = _read_user_config()
    overrides = _custom_overrides(config, create=False)
    if not overrides:
        print("No custom pricing overrides configured.")
        return 0
    providers = overrides.get("providers")
    if not isinstance(providers, list):
        print("No custom pricing overrides configured.")
        return 0
    bucket = _find_bucket(providers, provider, plan)
    if bucket is None:
        print("No matching pricing override bucket found.")
        return 0

    changed = False
    if model:
        models = bucket.get("models")
        if isinstance(models, list):
            target = str(model).strip().lower()
            kept = [item for item in models if not (isinstance(item, dict) and str(item.get("model", "")).strip().lower() == target)]
            if len(kept) != len(models):
                bucket["models"] = kept
                changed = True
    else:
        providers.remove(bucket)
        changed = True

    active_plans = overrides.get("active_plans")
    if changed and not bucket.get("models") and not bucket.get("default") and bucket in providers:
        providers.remove(bucket)
    if isinstance(active_plans, dict) and not any(
        isinstance(item, dict) and _normalize_provider(item.get("provider")) == provider and _normalize_plan(item.get("plan")) == plan
        for item in providers
    ):
        if active_plans.get(provider) == plan:
            active_plans.pop(provider, None)

    if not changed:
        print("No matching pricing override entry found.")
        return 0

    config_path = _write_user_config(config)
    print(f"Removed pricing override from {config_path}")
    return 0


def import_pricing(args) -> int:
    config = _read_user_config()
    path = Path(getattr(args, "file_path"))
    if not path.exists():
        raise SystemExit(f"File not found: {path}")
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
    else:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))

    imported: Any = payload
    if isinstance(payload, dict) and isinstance(payload.get("pricing"), dict):
        pricing = payload.get("pricing") or {}
        if isinstance(pricing.get("custom_overrides"), dict):
            imported = pricing["custom_overrides"]
    elif isinstance(payload, dict) and isinstance(payload.get("custom_overrides"), dict):
        imported = payload["custom_overrides"]

    if not isinstance(imported, dict):
        raise SystemExit("Import file must contain a pricing.custom_overrides mapping")

    if getattr(args, "merge", False):
        overrides = _custom_overrides(config, create=True)
        assert overrides is not None
        for key, value in imported.items():
            overrides[key] = value
    else:
        pricing = config.get("pricing")
        if not isinstance(pricing, dict):
            pricing = {}
            config["pricing"] = pricing
        pricing["custom_overrides"] = imported

    config_path = _write_user_config(config)
    print(f"Imported pricing overrides into {config_path}")
    return 0


def pricing_command(args) -> int:
    subcmd = getattr(args, "pricing_command", None) or "list"
    if subcmd == "list":
        return list_pricing()
    if subcmd == "set":
        return set_pricing(args)
    if subcmd == "remove":
        return remove_pricing(args)
    if subcmd == "import":
        return import_pricing(args)
    raise SystemExit(f"Unknown pricing command: {subcmd}")


def register_pricing_subparser(subparsers) -> None:
    pricing_parser = subparsers.add_parser(
        "pricing",
        help="Manage custom pricing overrides for usage-cost estimation",
        description="Manage custom pricing overrides for usage-cost estimation",
    )
    pricing_subparsers = pricing_parser.add_subparsers(dest="pricing_command")

    pricing_subparsers.add_parser("list", help="List pricing overrides")

    pricing_set = pricing_subparsers.add_parser("set", help="Create or update a pricing override")
    pricing_set.add_argument("--provider", required=True, help="Provider slug (e.g. openrouter, custom)")
    pricing_set.add_argument("--plan", help="Optional plan name for plan-scoped overrides")
    pricing_set.add_argument("--activate-plan", action="store_true", help="Mark this plan active for runtime lookup")
    pricing_set.add_argument("--model", help="Model ID to override; omit for a provider-wide fallback override")
    pricing_set.add_argument("--billing-mode", choices=sorted(_ALLOWED_BILLING_MODES), help="Override source label")
    pricing_set.add_argument("--input", dest="input_cost_per_million", type=float, help="Input-token USD cost per million")
    pricing_set.add_argument("--output", dest="output_cost_per_million", type=float, help="Output-token USD cost per million")
    pricing_set.add_argument("--cache-read", dest="cache_read_cost_per_million", type=float, help="Cache-read USD cost per million")
    pricing_set.add_argument("--cache-write", dest="cache_write_cost_per_million", type=float, help="Cache-write USD cost per million")
    pricing_set.add_argument("--request", dest="request_cost", type=float, help="Fixed USD cost per request")
    pricing_set.add_argument("--reason", help="Human reason/label for this override")
    pricing_set.add_argument("--effective-from", help="Inclusive start date (YYYY-MM-DD)")
    pricing_set.add_argument("--effective-until", help="Inclusive end date (YYYY-MM-DD)")

    pricing_remove = pricing_subparsers.add_parser("remove", help="Remove a pricing override")
    pricing_remove.add_argument("--provider", required=True, help="Provider slug")
    pricing_remove.add_argument("--plan", help="Optional plan name")
    pricing_remove.add_argument("--model", help="Model ID to remove; omit to remove the whole bucket")

    pricing_import = pricing_subparsers.add_parser("import", help="Import pricing overrides from JSON or YAML")
    pricing_import.add_argument("--file", dest="file_path", required=True, help="Path to a JSON or YAML file")
    pricing_import.add_argument("--merge", action="store_true", help="Merge into existing pricing.custom_overrides instead of replacing it")

    pricing_parser.set_defaults(func=pricing_command)
