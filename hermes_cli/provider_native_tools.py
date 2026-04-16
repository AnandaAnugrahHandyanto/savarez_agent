"""Setup-time defaults for chat providers that also serve TTS / image / vision / video / music."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Iterable, Set, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# category → (config_section, config_key, overridable_values)
_TOOL_DEFAULTS = {
    "tts":       ("tts",       "provider", {"", "edge"}),
    "image_gen": ("image_gen", "provider", {"", "auto", "fal"}),
    "video_gen": ("video_gen", "provider", {"", "auto"}),
    "music_gen": ("music_gen", "provider", {"", "auto"}),
}

_TOOL_LABELS = {
    "tts": "Text-to-speech",
    "image_gen": "Image generation",
    "vision": "Vision analysis",
    "video_gen": "Video generation",
    "music_gen": "Music generation",
}


def _api_host(config):
    url = (config.get("model") or {}).get("base_url", "")
    try:
        return urlparse(url).hostname or ""
    except Exception:
        return ""


def _is_native_provider(config):
    return "minimax" in _api_host(config)


def _provider_label(config):
    model = config.get("model") or {}
    if isinstance(model, dict):
        return str(model.get("provider") or "").strip().lower()
    return ""


def _safe_load_config():
    try:
        from hermes_cli.config import load_config
        cfg = load_config()
        return cfg if isinstance(cfg, dict) else {}
    except Exception:
        return {}


def active_provider_api_root(config):
    """API root derived from ``model.base_url``, stripping ``/anthropic``."""
    model = config.get("model")
    if not isinstance(model, dict):
        return ""
    base = str(model.get("base_url") or "").strip().rstrip("/")
    if not base:
        return ""
    return base[: -len("/anthropic")] if base.endswith("/anthropic") else base


def endpoint_and_key(subpath, config=None):
    """``(url, api_key)`` for a native subpath, or ``("", "")``."""
    cfg = config if config is not None else _safe_load_config()
    if not _is_native_provider(cfg):
        return "", ""
    root = active_provider_api_root(cfg).rstrip("/")
    key = (os.environ.get("MINIMAX_API_KEY", "").strip()
           or os.environ.get("MINIMAX_CN_API_KEY", "").strip())
    if not root or not key:
        return "", ""
    return f"{root}{subpath}", key


def get_native_tools(config):
    """Tool categories served natively by the active provider, or ``()``."""
    if not _is_native_provider(config):
        return ()
    return tuple(_TOOL_DEFAULTS) + ("vision",)


def provider_has_native_tool(tool, config):
    return tool in get_native_tools(config)


def apply_provider_native_tool_defaults(config):
    """Wire config defaults for providers that serve tools natively."""
    if not _is_native_provider(config):
        return set()
    label = _provider_label(config)
    if not label:
        return set()
    changed = set()
    for cat, (section, key, overridable) in _TOOL_DEFAULTS.items():
        cfg = config.setdefault(section, {})
        if isinstance(cfg, dict) and str(cfg.get(key) or "").strip().lower() in overridable:
            cfg[key] = label
            changed.add(cat)
    if changed:
        aux = config.get("auxiliary") if isinstance(config.get("auxiliary"), dict) else {}
        vis = aux.get("vision") if isinstance(aux.get("vision"), dict) else {}
        if str(vis.get("provider") or "").strip().lower() in {"", "auto", "main"}:
            changed.add("vision")
    return changed


def describe_changes(changed, config):
    """Bullet-list summary used by the setup wizard."""
    items = sorted(changed)
    if not items:
        return "No changes \u2014 existing tool choices were preserved."
    return "\n".join(f"  \u2022 {_TOOL_LABELS.get(k, k)}" for k in items)
