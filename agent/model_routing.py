"""Plugin-driven per-turn model routing helpers."""

from __future__ import annotations

import logging
import os
from typing import Any, Mapping

logger = logging.getLogger(__name__)


_RUNTIME_KEYS = (
    "api_key",
    "base_url",
    "provider",
    "api_mode",
    "command",
    "args",
    "credential_pool",
    "max_tokens",
)


def _as_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _runtime_copy(runtime: Mapping[str, Any]) -> dict[str, Any]:
    copied = {key: runtime.get(key) for key in _RUNTIME_KEYS if key in runtime}
    if "args" in copied:
        copied["args"] = list(copied.get("args") or [])
    if "max_tokens" not in copied:
        max_output_tokens = runtime.get("max_output_tokens")
        if isinstance(max_output_tokens, int) and max_output_tokens > 0:
            copied["max_tokens"] = max_output_tokens
    return copied


def _freeze_mapping(value: Mapping[str, Any] | None) -> tuple | None:
    if not isinstance(value, Mapping):
        return None
    return tuple(sorted((str(key), str(val)) for key, val in value.items()))


def _signature(
    model: str,
    runtime: Mapping[str, Any],
    reasoning_config: Mapping[str, Any] | None = None,
) -> tuple:
    return (
        model,
        runtime.get("provider"),
        runtime.get("base_url"),
        runtime.get("api_mode"),
        runtime.get("command"),
        tuple(runtime.get("args") or []),
        runtime.get("max_tokens"),
        _freeze_mapping(reasoning_config),
    )


def primary_route(
    model: str,
    runtime: Mapping[str, Any],
    *,
    reasoning_config: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the canonical route dict for the primary model/runtime."""
    runtime_copy = _runtime_copy(runtime)
    route = {
        "model": model,
        "runtime": runtime_copy,
        "signature": _signature(model, runtime_copy, reasoning_config),
    }
    if reasoning_config is not None:
        route["reasoning_config"] = dict(reasoning_config)
    if metadata:
        route["model_route"] = dict(metadata)
    return route


def _configured_secret(entry: Mapping[str, Any]) -> str | None:
    api_key = str(entry.get("api_key") or "").strip()
    if api_key:
        return api_key
    env_name = str(entry.get("api_key_env") or entry.get("key_env") or "").strip()
    if env_name:
        return os.getenv(env_name, "").strip() or None
    return None


def _coerce_reasoning(value: Any) -> dict[str, Any] | None:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, bool):
        return {"enabled": value}
    if isinstance(value, str):
        raw = value.strip().lower()
        if not raw or raw in {"inherit", "default"}:
            return None
        if raw in {"off", "false", "none", "disabled"}:
            return {"enabled": False}
        return {"enabled": True, "effort": raw}
    return None


def _runtime_from_hook_result(
    result: Mapping[str, Any],
    *,
    target_model: str,
    primary_runtime: Mapping[str, Any],
) -> dict[str, Any]:
    raw_runtime = result.get("runtime")
    if isinstance(raw_runtime, Mapping):
        runtime = _runtime_copy(primary_runtime)
        runtime.update(_runtime_copy(raw_runtime))
    else:
        provider = (
            str(result.get("provider") or primary_runtime.get("provider") or "auto")
            .strip()
            or "auto"
        )
        base_url = str(result.get("base_url") or "").strip() or None
        api_key = _configured_secret(result)
        from hermes_cli.runtime_provider import resolve_runtime_provider

        runtime = resolve_runtime_provider(
            requested=provider,
            explicit_api_key=api_key,
            explicit_base_url=base_url,
            target_model=target_model or None,
        )
        runtime = _runtime_copy(runtime)
        if (
            "max_tokens" not in runtime
            and primary_runtime.get("max_tokens") is not None
        ):
            runtime["max_tokens"] = primary_runtime.get("max_tokens")

    for key in (
        "api_key",
        "base_url",
        "provider",
        "api_mode",
        "command",
        "credential_pool",
        "max_tokens",
    ):
        if key in result and result.get(key) is not None:
            runtime[key] = result.get(key)
    if "max_output_tokens" in result and result.get("max_output_tokens") is not None:
        runtime["max_tokens"] = result.get("max_output_tokens")
    if "args" in result:
        runtime["args"] = list(result.get("args") or [])
    return runtime


def _coerce_hook_result(
    result: Any,
    *,
    primary_model: str,
    primary_runtime: Mapping[str, Any],
    default_reasoning_config: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(result, Mapping):
        return None
    if result.get("action") in {"skip", "ignore", "none"}:
        return None

    if "model" in result and not str(result.get("model") or "").strip():
        return None
    target_model = str(
        result.get("model") if "model" in result else primary_model
    ).strip()
    if not target_model:
        return None
    if target_model.lower() in {"primary", "default", "inherit"}:
        return primary_route(
            primary_model,
            primary_runtime,
            reasoning_config=default_reasoning_config,
            metadata=_as_mapping(result.get("metadata")),
        )

    runtime = _runtime_from_hook_result(
        result,
        target_model=target_model,
        primary_runtime=primary_runtime,
    )
    reasoning = _coerce_reasoning(
        result.get("reasoning_config", result.get("reasoning"))
    )
    if reasoning is None:
        reasoning = dict(default_reasoning_config) if default_reasoning_config else None

    metadata = _as_mapping(result.get("metadata"))
    route = {
        "model": target_model,
        "runtime": runtime,
        "signature": _signature(target_model, runtime, reasoning),
    }
    if reasoning is not None:
        route["reasoning_config"] = reasoning
    if metadata:
        route["model_route"] = metadata
    return route


def resolve_model_route(
    *,
    user_message: Any,
    config: Mapping[str, Any] | None,
    primary_model: str,
    primary_runtime: Mapping[str, Any],
    platform: str,
    session_id: str = "",
    task_id: str = "",
    reasoning_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve a per-turn model route through plugin hooks.

    Plugins can register ``resolve_model_route`` and return a dict with
    ``model``, optional runtime/provider fields, optional ``reasoning_config``,
    and optional ``metadata``.  The first valid plugin result wins.  Failures
    are logged and fall back to the primary model.
    """
    primary = primary_route(
        primary_model,
        primary_runtime,
        reasoning_config=reasoning_config,
    )
    try:
        from hermes_cli.plugins import discover_plugins, has_hook, invoke_hook

        discover_plugins()
        if not has_hook("resolve_model_route"):
            return primary
        results = invoke_hook(
            "resolve_model_route",
            user_message=user_message,
            config=dict(config or {}),
            primary_model=primary_model,
            primary_runtime=_runtime_copy(primary_runtime),
            platform=platform,
            session_id=session_id,
            task_id=task_id,
            reasoning_config=dict(reasoning_config or {}),
        )
    except Exception as exc:
        logger.warning("resolve_model_route hook failed; using primary model: %s", exc)
        return primary

    for result in results:
        try:
            route = _coerce_hook_result(
                result,
                primary_model=primary_model,
                primary_runtime=primary_runtime,
                default_reasoning_config=reasoning_config,
            )
        except Exception as exc:
            logger.warning(
                "resolve_model_route result ignored; using next route if available: %s",
                exc,
            )
            continue
        if route is not None:
            return route
    return primary
