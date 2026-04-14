"""Canonical OpenRouter picker catalog for Hermes model selection."""

from __future__ import annotations

import json
import re
import urllib.request
from typing import Any

_openrouter_live_items_cache: list[dict[str, Any]] | None = None
_openrouter_picker_cache: list[str] | None = None
_openrouter_groups_cache: list[tuple[str, tuple[str, ...]]] | None = None

_OPENROUTER_PICKER_NOISE_PATTERNS: re.Pattern[str] = re.compile(
    r"-tts\b|embedding|live-|-(preview|exp)-\d{2,4}[-_]|"
    r"-image\b|-image-preview\b|-customtools\b",
    re.IGNORECASE,
)
_OPENROUTER_EXCLUDED_PICKER_IDS: frozenset[str] = frozenset({
    "openrouter/free",
    "openrouter/auto",
})
_OPENROUTER_VENDOR_LABELS: dict[str, str] = {
    "anthropic": "Anthropic",
    "arcee-ai": "Arcee",
    "deepseek": "DeepSeek",
    "google": "Google",
    "meta-llama": "Meta Llama",
    "minimax": "MiniMax",
    "moonshotai": "Moonshot",
    "nvidia": "Nvidia",
    "openai": "OpenAI",
    "qwen": "Qwen",
    "stepfun": "StepFun",
    "x-ai": "X.AI",
    "xiaomi": "Xiaomi",
    "z-ai": "Z.AI",
}


def _fetch_openrouter_live_items(
    timeout: float = 8.0,
    *,
    force_refresh: bool = False,
) -> list[dict[str, Any]]:
    """Fetch the live OpenRouter catalog, caching the raw model entries."""
    global _openrouter_live_items_cache

    if _openrouter_live_items_cache is not None and not force_refresh:
        return list(_openrouter_live_items_cache)

    try:
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/models",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode())
    except Exception:
        return list(_openrouter_live_items_cache or [])

    live_items = payload.get("data", [])
    if not isinstance(live_items, list):
        return list(_openrouter_live_items_cache or [])

    filtered = [item for item in live_items if isinstance(item, dict)]
    _openrouter_live_items_cache = filtered
    return list(filtered)


def _openrouter_model_is_free(pricing: Any) -> bool:
    """Return True when both prompt and completion pricing are zero."""
    if not isinstance(pricing, dict):
        return False
    try:
        return float(pricing.get("prompt", "0")) == 0 and float(pricing.get("completion", "0")) == 0
    except (TypeError, ValueError):
        return False


def _openrouter_live_item_is_agentic(item: dict[str, Any]) -> bool:
    """Heuristic filter for OpenRouter models that are useful for Hermes."""
    model_id = str(item.get("id") or "").strip()
    if (
        not model_id
        or model_id in _OPENROUTER_EXCLUDED_PICKER_IDS
        or _OPENROUTER_PICKER_NOISE_PATTERNS.search(model_id)
    ):
        return False

    supported_parameters = {
        str(param).strip().lower()
        for param in (item.get("supported_parameters") or [])
        if str(param).strip()
    }
    if "tools" not in supported_parameters and "tool_choice" not in supported_parameters:
        return False

    architecture = item.get("architecture")
    if not isinstance(architecture, dict):
        return False

    input_modalities = {
        str(modality).strip().lower()
        for modality in (architecture.get("input_modalities") or [])
        if str(modality).strip()
    }
    output_modalities = {
        str(modality).strip().lower()
        for modality in (architecture.get("output_modalities") or [])
        if str(modality).strip()
    }
    return "text" in input_modalities and "text" in output_modalities


def _openrouter_picker_sort_key(model_id: str) -> tuple[str, int, str]:
    if "/" in model_id:
        vendor, bare = model_id.split("/", 1)
    else:
        vendor, bare = "", model_id
    return (vendor, 1 if bare.endswith(":free") else 0, bare)


def openrouter_vendor_label(vendor_slug: str) -> str:
    """Return a human-friendly label for an OpenRouter vendor slug."""
    label = _OPENROUTER_VENDOR_LABELS.get(vendor_slug)
    if label:
        return label
    bits = [part for part in vendor_slug.replace("_", "-").split("-") if part]
    return " ".join(part[:1].upper() + part[1:] for part in bits) or vendor_slug


def _discover_openrouter_picker_ids(*, force_refresh: bool = False) -> list[str]:
    """Return the canonical OpenRouter picker IDs without grouping."""
    models_dev_ids: set[str] = set()
    try:
        from agent.models_dev import list_agentic_models

        models_dev_ids = {
            mid for mid in list_agentic_models("openrouter")
            if isinstance(mid, str) and mid.strip()
        }
    except Exception:
        models_dev_ids = set()

    discovered_ids: list[str] = []
    discovered_seen: set[str] = set()

    live_items = _fetch_openrouter_live_items(force_refresh=force_refresh)
    if live_items:
        for item in live_items:
            model_id = str(item.get("id") or "").strip()
            if (
                not model_id
                or model_id in _OPENROUTER_EXCLUDED_PICKER_IDS
                or model_id in discovered_seen
            ):
                continue
            if model_id in models_dev_ids or _openrouter_live_item_is_agentic(item):
                discovered_ids.append(model_id)
                discovered_seen.add(model_id)
        discovered_ids.sort(key=_openrouter_picker_sort_key)
    elif models_dev_ids:
        discovered_ids = sorted(models_dev_ids, key=_openrouter_picker_sort_key)

    return discovered_ids


def openrouter_picker_model_ids(*, force_refresh: bool = False) -> list[str]:
    """Return the canonical automated OpenRouter picker catalog."""
    global _openrouter_picker_cache

    if _openrouter_picker_cache is not None and not force_refresh:
        return list(_openrouter_picker_cache)

    discovered_ids = _discover_openrouter_picker_ids(force_refresh=force_refresh)
    _openrouter_picker_cache = list(discovered_ids)
    return list(discovered_ids)


def openrouter_picker_groups(*, force_refresh: bool = False) -> list[tuple[str, tuple[str, ...]]]:
    """Return ``[(vendor_slug, (model_ids...)), ...]`` for the picker UI."""
    global _openrouter_groups_cache

    if _openrouter_groups_cache is not None and not force_refresh:
        return list(_openrouter_groups_cache)

    grouped: dict[str, list[str]] = {}
    for model_id in openrouter_picker_model_ids(force_refresh=force_refresh):
        if "/" not in model_id:
            continue
        vendor, _bare = model_id.split("/", 1)
        grouped.setdefault(vendor, []).append(model_id)

    groups = [
        (vendor, tuple(models))
        for vendor, models in sorted(grouped.items(), key=lambda item: item[0])
    ]
    _openrouter_groups_cache = groups
    return list(groups)


def fetch_openrouter_models(
    timeout: float = 8.0,
    *,
    force_refresh: bool = False,
) -> list[tuple[str, str]]:
    """Compatibility wrapper returning ``(model_id, desc)`` tuples.

    Hermes no longer has a featured shortlist; descriptions are now dynamic and
    only annotate models as ``free`` when the live OpenRouter catalog confirms
    zero-cost pricing.
    """
    del timeout

    live_items = _fetch_openrouter_live_items(force_refresh=force_refresh)
    live_by_id = {
        str(item.get("id") or "").strip(): item
        for item in live_items
        if str(item.get("id") or "").strip()
    }
    return [
        (
            model_id,
            "free" if _openrouter_model_is_free(live_by_id.get(model_id, {}).get("pricing")) else "",
        )
        for model_id in openrouter_picker_model_ids(force_refresh=force_refresh)
    ]
