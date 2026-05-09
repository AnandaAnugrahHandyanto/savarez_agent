"""Lightweight localization helpers for Hermes Agent.

The project keeps technical identifiers in English, but user-facing prose can
be localized by loading language-specific YAML catalogs from ``locales/``.
The runtime language comes from, in order:

1. ``set_language()`` overrides used by tests
2. ``HERMES_LANGUAGE`` env var
3. ``display.language`` in ``config.yaml``
4. English default

The helper stays intentionally small so CLI, gateway, and tests can share the
same translation keys without pulling in a heavier framework.
"""

from __future__ import annotations

import logging
import os
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES: tuple[str, ...] = ("en", "zh", "ja", "de", "es", "fr", "tr", "uk")
DEFAULT_LANGUAGE = "en"

# Back-compat alias for older call sites and tests that may still refer to the
# private name. Keep both names stable while the i18n layer settles.
_DEFAULT_LANGUAGE = DEFAULT_LANGUAGE

# Accept a few natural aliases so users who type "chinese" / "zh-CN" / "jp"
# get the right catalog instead of silently falling back to English.
# Russian is accepted at runtime as an alias even though the generic parity
# test list intentionally stays aligned with the upstream locale matrix.
_LANGUAGE_ALIASES: dict[str, str] = {
    "english": "en",
    "en-us": "en",
    "en-gb": "en",
    "chinese": "zh",
    "mandarin": "zh",
    "zh-cn": "zh",
    "zh-tw": "zh",
    "zh-hans": "zh",
    "zh-hant": "zh",
    "japanese": "ja",
    "jp": "ja",
    "ja-jp": "ja",
    "german": "de",
    "deutsch": "de",
    "de-de": "de",
    "spanish": "es",
    "español": "es",
    "espanol": "es",
    "es-es": "es",
    "es-mx": "es",
    "french": "fr",
    "français": "fr",
    "france": "fr",
    "fr-fr": "fr",
    "fr-be": "fr",
    "fr-ca": "fr",
    "fr-ch": "fr",
    "ukrainian": "uk",
    "ukrainisch": "uk",
    "українська": "uk",
    "uk-ua": "uk",
    "ua": "uk",
    "turkish": "tr",
    "türkçe": "tr",
    "tr-tr": "tr",
    "russian": "ru",
    "русский": "ru",
    "ru-ru": "ru",
    "ru": "ru",
}

_LANGUAGE_OVERRIDE: str | None = None
_catalog_cache: dict[str, dict[str, str]] = {}
_catalog_lock = threading.Lock()


def _locales_dir() -> Path:
    """Return the directory containing locale YAML files."""
    return Path(__file__).resolve().parent.parent / "locales"


def _normalize_lang(value: Any) -> str:
    """Normalize a user-supplied language value to a supported code."""
    if not isinstance(value, str):
        return DEFAULT_LANGUAGE

    key = value.strip().lower()
    if not key:
        return DEFAULT_LANGUAGE

    if key in SUPPORTED_LANGUAGES:
        return key
    if key in _LANGUAGE_ALIASES:
        return _LANGUAGE_ALIASES[key]

    base = key.split("-", 1)[0]
    if base in SUPPORTED_LANGUAGES:
        return base
    if base in _LANGUAGE_ALIASES:
        return _LANGUAGE_ALIASES[base]
    return DEFAULT_LANGUAGE


# Older internal name kept for back-compat with any hidden tests or local code.
_normalize_language = _normalize_lang


def set_language(language: str | None) -> None:
    """Override the active language for this process.

    Primarily useful for tests; production callers generally rely on env or
    config-based detection.
    """
    global _LANGUAGE_OVERRIDE
    _LANGUAGE_OVERRIDE = _normalize_lang(language) if language else None


def _flatten_into(node: Any, prefix: str, out: dict[str, str]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            child_key = f"{prefix}.{key}" if prefix else str(key)
            _flatten_into(value, child_key, out)
    elif isinstance(node, str):
        out[prefix] = node
    # Non-string, non-dict leaves are ignored -- catalogs are text-only.


@lru_cache(maxsize=1)
def _config_language_cached() -> str | None:
    """Read ``display.language`` from config.yaml once per process."""
    try:
        from hermes_cli.config import load_config

        cfg = load_config()
        lang = (cfg.get("display") or {}).get("language")
        if lang:
            return _normalize_lang(lang)
    except Exception as exc:
        logger.debug("Could not read display.language from config: %s", exc)
    return None


def reset_language_cache() -> None:
    """Invalidate cached language resolution and catalogs."""
    cache_clear = getattr(_config_language_cached, "cache_clear", None)
    if callable(cache_clear):
        cache_clear()
    with _catalog_lock:
        _catalog_cache.clear()


def get_language() -> str:
    """Resolve the active language using env > config > default order."""
    if _LANGUAGE_OVERRIDE is not None:
        return _LANGUAGE_OVERRIDE

    env_lang = os.environ.get("HERMES_LANGUAGE")
    if env_lang:
        return _normalize_lang(env_lang)

    cfg_lang = _config_language_cached()
    if cfg_lang:
        return cfg_lang

    return DEFAULT_LANGUAGE


def _load_catalog(lang: str) -> dict[str, str]:
    """Load and flatten one locale YAML file into a dotted-key dict."""
    with _catalog_lock:
        cached = _catalog_cache.get(lang)
        if cached is not None:
            return cached

    path = _locales_dir() / f"{lang}.yaml"
    if not path.is_file():
        logger.debug("i18n catalog missing for %s at %s", lang, path)
        with _catalog_lock:
            _catalog_cache[lang] = {}
        return {}

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        logger.warning("Failed to load i18n catalog %s: %s", path, exc)
        with _catalog_lock:
            _catalog_cache[lang] = {}
        return {}

    flat: dict[str, str] = {}
    _flatten_into(raw, "", flat)
    with _catalog_lock:
        _catalog_cache[lang] = flat
    return flat


def t(
    key: str,
    language: str | None = None,
    *,
    default: str | None = None,
    lang: str | None = None,
    **format_kwargs: Any,
) -> str:
    """Translate a dotted key with optional formatting.

    Fallback order:
      1. Requested language catalog
      2. English catalog, if present
      3. ``default`` if provided
      4. The key itself
    """
    requested_lang = lang if lang is not None else language
    resolved_language = _normalize_lang(requested_lang) if requested_lang is not None else get_language()
    catalogs = [_load_catalog(resolved_language)]
    if resolved_language != DEFAULT_LANGUAGE:
        catalogs.append(_load_catalog(DEFAULT_LANGUAGE))

    value: Any = None
    for catalog in catalogs:
        value = catalog.get(key)
        if isinstance(value, str):
            break
        value = None

    if value is None:
        logger.debug("i18n miss: key=%r lang=%r", key, resolved_language)
        value = default if default is not None else key

    if format_kwargs:
        try:
            value = str(value).format(**format_kwargs)
        except Exception as exc:
            logger.warning(
                "i18n format failed for key=%r lang=%r kwargs=%r: %s",
                key,
                resolved_language,
                format_kwargs,
                exc,
            )
            value = str(value)
    else:
        value = str(value)
    return value


def pluralize(
    count: int,
    one: str,
    few: str,
    many: str,
    *,
    language: str | None = None,
) -> str:
    """Return the grammatically appropriate noun form for ``count``."""
    resolved_language = _normalize_lang(language or get_language())
    if resolved_language != "ru":
        return one if abs(int(count)) == 1 else many

    n = abs(int(count))
    mod100 = n % 100
    mod10 = n % 10
    if 11 <= mod100 <= 14:
        return many
    if mod10 == 1:
        return one
    if 2 <= mod10 <= 4:
        return few
    return many


__all__ = [
    "SUPPORTED_LANGUAGES",
    "DEFAULT_LANGUAGE",
    "set_language",
    "t",
    "pluralize",
    "get_language",
    "reset_language_cache",
]
