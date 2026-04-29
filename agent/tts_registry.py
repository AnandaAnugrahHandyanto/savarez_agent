"""
Text-to-Speech Provider Registry
================================

Central map of registered TTS providers. Populated by plugins at import
time via ``PluginContext.register_tts_provider()``; consulted by
``tools.tts_tool`` when ``tts.provider`` in ``config.yaml`` names a
non-legacy backend.

Active selection
----------------
Unlike :mod:`agent.image_gen_registry` — which auto-selects FAL / the sole
registered provider as a fallback — the TTS registry is **purely
additive**. :func:`get_active_provider` returns ``None`` whenever
``tts.provider`` is unset. The dispatcher in ``tools.tts_tool`` then falls
through to the legacy Edge default path. This preserves existing user
setups that have no ``tts.provider`` in their ``config.yaml``.

To migrate a legacy provider (e.g. ``edge``) into the plugin interface in
a future PR, update ``tools.tts_tool._dispatch_to_plugin_tts_provider``'s
``LEGACY_TTS_PROVIDERS`` set and remove the corresponding hardcoded
branch at the same time.
"""

from __future__ import annotations

import logging
import threading
from typing import Dict, List, Optional

from agent.tts_provider import TtsProvider

logger = logging.getLogger(__name__)


_providers: Dict[str, TtsProvider] = {}
_lock = threading.Lock()


def register_provider(provider: TtsProvider) -> None:
    """Register a TTS provider under ``provider.name``.

    Re-registration with the same name silently replaces the previous
    entry and logs at debug level — this makes test fixtures and
    hot-reload loops behave predictably.
    """
    if not isinstance(provider, TtsProvider):
        raise TypeError(
            f"register_provider() expects a TtsProvider instance, "
            f"got {type(provider).__name__}"
        )
    name = provider.name
    if not isinstance(name, str) or not name.strip():
        raise ValueError("TTS provider .name must be a non-empty string")
    with _lock:
        existing = _providers.get(name)
        _providers[name] = provider
    if existing is not None:
        logger.debug(
            "TTS provider '%s' re-registered (was %r)",
            name, type(existing).__name__,
        )
    else:
        logger.debug(
            "Registered TTS provider '%s' (%s)",
            name, type(provider).__name__,
        )


def list_providers() -> List[TtsProvider]:
    """Return all registered providers, sorted by name."""
    with _lock:
        items = list(_providers.values())
    return sorted(items, key=lambda p: p.name)


def get_provider(name: str) -> Optional[TtsProvider]:
    """Return the provider registered under ``name``, or None."""
    if not isinstance(name, str):
        return None
    with _lock:
        return _providers.get(name.strip())


def get_active_provider() -> Optional[TtsProvider]:
    """Resolve the currently-active plugin provider from ``tts.provider``.

    Returns ``None`` when ``tts.provider`` is unset, not a string, or
    names a provider that isn't registered. Callers (the
    ``text_to_speech`` tool dispatcher, the setup-wizard status probe)
    use ``None`` to mean "no plugin to route to; fall through to legacy".
    """
    configured: Optional[str] = None
    try:
        from hermes_cli.config import load_config

        cfg = load_config()
        section = cfg.get("tts") if isinstance(cfg, dict) else None
        if isinstance(section, dict):
            raw = section.get("provider")
            if isinstance(raw, str) and raw.strip():
                configured = raw.strip()
    except Exception as exc:  # pragma: no cover - defensive logging only
        logger.debug("Could not read tts.provider from config: %s", exc)

    if not configured:
        return None

    with _lock:
        return _providers.get(configured)


def _reset_for_tests() -> None:
    """Clear the registry. **Test-only.**"""
    with _lock:
        _providers.clear()
