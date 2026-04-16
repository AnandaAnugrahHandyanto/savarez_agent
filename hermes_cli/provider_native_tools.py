"""Setup-time defaults for chat providers that also serve TTS / image / vision / video / music.

Mirrors ``hermes_cli.nous_subscription``: one apply hook for the wizard,
plus lightweight helpers consumed by the tool files.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Iterable, Set, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# hostname → provider_label
_NATIVE_HOSTS: Dict[str, str] = {
    "api.minimax.io":        "minimax",
    "api-uw.minimax.io":     "minimax",
    "api.minimaxi.com":      "minimax-cn",
    "api-apac.minimaxi.com": "minimax-cn",
}

_NATIVE_TOOLS = ("tts", "image_gen", "vision", "video_gen", "music_gen")

_TOOL_DEFAULTS: Dict[str, Tuple[str, str, set]] = {
    "tts":       ("tts",       "provider", {"", "edge"}),
    "image_gen": ("image_gen", "provider", {"", "auto", "fal"}),
    "video_gen": ("video_gen", "provider", {"", "auto"}),
    "music_gen": ("music_gen", "provider", {"", "auto"}),
}

_TOOL_SUMMARIES: Dict[str, str] = {
    "tts":       "TTS \u2192 speech-2.6-hd (30+ voices)",
    "image_gen": "Image generation \u2192 image-01",
    "vision":    "Vision analysis \u2192 MiniMax-VL-01",
    "video_gen": "Video generation \u2192 MiniMax-Hailuo-2.3",
    "music_gen": "Music generation \u2192 music-2.6",
}

# env vars to try, in order — covers both international and CN keys
_CREDENTIAL_VARS = ("MINIMAX_API_KEY", "MINIMAX_CN_API_KEY")


def _api_host(config: Dict[str, Any]) -> str:
    url = (config.get("model") or {}).get("base_url", "")
    try:
        return urlparse(url).hostname or ""
    except Exception:
        return ""


def _provider_label(config: Dict[str, Any]) -> str:
    return _NATIVE_HOSTS.get(_api_host(config), "")


def _credential() -> str:
    for var in _CREDENTIAL_VARS:
        v = os.environ.get(var, "").strip()
        if v:
            return v
    return ""


def _safe_load_config() -> Dict[str, Any]:
    try:
        from hermes_cli.config import load_config
        cfg = load_config()
        return cfg if isinstance(cfg, dict) else {}
    except Exception:
        return {}


def active_provider_api_root(config: Dict[str, Any]) -> str:
    """API root derived from ``model.base_url``, stripping ``/anthropic``."""
    model = config.get("model")
    if not isinstance(model, dict):
        return ""
    base = str(model.get("base_url") or "").strip().rstrip("/")
    if not base:
        return ""
    return base[: -len("/anthropic")] if base.endswith("/anthropic") else base


def endpoint_and_key(subpath: str, config: Dict[str, Any] = None) -> Tuple[str, str]:
    """``(url, api_key)`` for a native subpath, or ``("", "")``."""
    cfg = config if config is not None else _safe_load_config()
    if not _provider_label(cfg):
        return "", ""
    root = active_provider_api_root(cfg).rstrip("/")
    key = _credential()
    if not root or not key:
        return "", ""
    return f"{root}{subpath}", key


def get_native_tools(config: Dict[str, Any]) -> Tuple[str, ...]:
    """Tool categories served natively by the active provider, or ``()``."""
    return _NATIVE_TOOLS if _provider_label(config) else ()


def provider_has_native_tool(tool: str, config: Dict[str, Any]) -> bool:
    return tool in get_native_tools(config)


def apply_provider_native_tool_defaults(config: Dict[str, Any]) -> Set[str]:
    """Wire config defaults for providers that serve tools natively."""
    label = _provider_label(config)
    if not label:
        return set()
    changed: Set[str] = set()
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
    if changed:
        logger.info("Provider-native tool defaults applied: %s", sorted(changed))
    return changed


def describe_changes(changed: Iterable[str], config: Dict[str, Any]) -> str:
    """Bullet-list summary used by the setup wizard."""
    items = sorted(changed)
    if not items:
        return "No changes \u2014 existing tool choices were preserved."
    return "\n".join(f"  \u2022 {_TOOL_SUMMARIES.get(k, k)}" for k in items)
