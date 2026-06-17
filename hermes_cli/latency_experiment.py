from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import TypeAlias

from hermes_cli.latency_routing import (
    _is_claude_opus,
    _is_short_low_complexity_turn,
    _target_for_provider,
)


ExperimentConfig: TypeAlias = dict[str, object]


@dataclass(frozen=True, slots=True)
class LatencyRouteDecision:
    effective_model: str
    metadata: dict[str, str | float | bool | None]


def decide_latency_route(
    *,
    model: str,
    provider: str | None,
    user_message: str,
    experiment_config: ExperimentConfig | None,
    platform: str | None,
    bucket_key: str | None,
) -> LatencyRouteDecision:
    turn_class = _classify_turn(model, user_message)
    metadata = _base_metadata(model, turn_class)
    if not _is_experiment_enabled(experiment_config):
        return LatencyRouteDecision(effective_model=model, metadata=metadata)

    mode = _experiment_mode(experiment_config)
    rollout = _experiment_rollout(experiment_config)
    configured_treatment = _experiment_treatment_model(experiment_config)
    proposed_model = configured_treatment or _target_for_provider(model, provider)
    bucket_key_value = bucket_key or "default"
    bucket = _stable_bucket(bucket_key_value, _experiment_seed(experiment_config))
    arm = "treatment" if bucket < rollout else "control"
    metadata.update(
        {
            "enabled": True,
            "mode": mode,
            "arm": arm,
            "proposed_model": proposed_model,
            "bucket_key": bucket_key_value,
            "bucket": bucket,
        }
    )

    if not _platform_included(platform, experiment_config):
        metadata["reason"] = "platform_excluded"
        return LatencyRouteDecision(effective_model=model, metadata=metadata)
    if turn_class != "short_chat":
        metadata["reason"] = turn_class
        return LatencyRouteDecision(effective_model=model, metadata=metadata)
    if arm != "treatment":
        metadata["reason"] = "control"
        return LatencyRouteDecision(effective_model=model, metadata=metadata)
    if mode == "shadow":
        metadata["reason"] = "shadow"
        return LatencyRouteDecision(effective_model=model, metadata=metadata)

    metadata["effective_model"] = proposed_model
    metadata["routed"] = True
    metadata["reason"] = "ab_treatment"
    return LatencyRouteDecision(effective_model=proposed_model, metadata=metadata)


def latency_experiment_config(config: ExperimentConfig | None) -> ExperimentConfig | None:
    node = config
    for key in ("bob", "routing", "experiment"):
        if not isinstance(node, dict):
            return None
        value = node.get(key)
        if not isinstance(value, dict):
            return None
        node = value
    return node


def _classify_turn(model: str, user_message: str) -> str:
    if not _is_claude_opus(model):
        return "non_opus"
    if _is_short_low_complexity_turn(user_message):
        return "short_chat"
    return "complex"


def _base_metadata(model: str, turn_class: str) -> dict[str, str | float | bool | None]:
    return {
        "enabled": False,
        "mode": None,
        "arm": "control",
        "class": turn_class,
        "original_model": model,
        "effective_model": model,
        "proposed_model": None,
        "bucket_key": None,
        "bucket": None,
        "routed": False,
        "reason": "disabled",
    }


def _is_experiment_enabled(experiment_config: ExperimentConfig | None) -> bool:
    return isinstance(experiment_config, dict) and experiment_config.get("enabled") is True


def _experiment_mode(experiment_config: ExperimentConfig | None) -> str:
    if isinstance(experiment_config, dict) and str(experiment_config.get("mode") or "").lower() == "ab":
        return "ab"
    return "shadow"


def _experiment_rollout(experiment_config: ExperimentConfig | None) -> float:
    if not isinstance(experiment_config, dict):
        return 0.5
    raw = experiment_config.get("rollout", 0.5)
    if isinstance(raw, bool):
        return 0.5
    if not isinstance(raw, (str, int, float)):
        return 0.5
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 0.5
    return min(1.0, max(0.0, value))


def _experiment_seed(experiment_config: ExperimentConfig | None) -> str:
    if not isinstance(experiment_config, dict):
        return ""
    return str(experiment_config.get("seed") or "")


def _experiment_treatment_model(experiment_config: ExperimentConfig | None) -> str | None:
    if not isinstance(experiment_config, dict):
        return None
    treatment = str(experiment_config.get("treatment_model") or "").strip()
    return treatment or None


def _platform_included(platform: str | None, experiment_config: ExperimentConfig | None) -> bool:
    if not isinstance(experiment_config, dict):
        return True
    raw = experiment_config.get("include_platforms")
    if raw in (None, ""):
        return True
    if not isinstance(raw, list):
        return True
    allowed = {str(item).strip().lower() for item in raw if str(item).strip()}
    if not allowed:
        return True
    return (platform or "").strip().lower() in allowed


def _stable_bucket(bucket_key: str, seed: str) -> float:
    digest = sha256(f"{seed}:{bucket_key}".encode("utf-8")).hexdigest()
    value = int(digest[:16], 16)
    return value / float(0xFFFFFFFFFFFFFFFF)
