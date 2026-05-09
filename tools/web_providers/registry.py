"""Provider Registry — auto-discovery for web capability providers.

This module scans ``tools/web_providers/`` and automatically discovers all
``WebSearchProvider`` and ``WebExtractProvider`` subclasses.  Adding a new
search backend requires exactly one new file in this directory — no changes
to ``web_tools.py`` wiring, ``_get_backend()``, ``_is_backend_available()``,
``check_web_api_key()``, or the ``hermes tools`` picker hardcoded lists.

Architecture
------------

::

    tools/web_providers/
        base.py          — WebSearchProvider / WebExtractProvider ABCs
        registry.py      — this file (ProviderRegistry)
        brave.py         — BraveSearchProvider
        searxng.py       — SearXNGSearchProvider
        ddgs.py          — DDGSSearchProvider
        parallel.py      — ParallelSearchProvider / ParallelExtractProvider
        exa.py           — ExaSearchProvider / ExaExtractProvider
        tavily.py        — TavilySearchProvider / TavilyExtractProvider
        …                — drop any new provider here, zero wiring

Usage
-----

    from tools.web_providers.registry import ProviderRegistry

    # Is a backend available?
    ProviderRegistry.is_search_available("brave")   → True/False

    # Get a configured provider instance
    provider = ProviderRegistry.get_search_provider("searxng")   → WebSearchProvider

    # List all registered providers
    ProviderRegistry.list_search_providers()   → {"brave": BraveSearchProvider, …}

    # Are any search providers available at all?
    ProviderRegistry.any_search_available()    → True/False

    # All env vars needed by registered providers
    ProviderRegistry.all_required_env_vars()   → {"BRAVE_API_KEY", "EXA_API_KEY", …}
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from typing import Dict, List, Optional, Set, Type

import tools.web_providers as _pkg

from tools.web_providers.base import WebExtractProvider, WebSearchProvider

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """Auto-discovering registry for web capability providers.

    Scans ``tools/web_providers/`` on first access and caches results.
    All public methods are safe to call at import time (no network I/O).
    """

    # ── internal state ──────────────────────────────────────────────────────

    _scanned: bool = False
    _search_providers: Dict[str, Type[WebSearchProvider]] = {}
    _extract_providers: Dict[str, Type[WebExtractProvider]] = {}
    _priority_order: List[str] = []  # registration order = priority

    # ── public helpers ──────────────────────────────────────────────────────

    @classmethod
    def _ensure_scanned(cls) -> None:
        """Lazily scan the provider directory on first access."""
        if cls._scanned:
            return
        cls._scanned = True

        for _, name, _ in pkgutil.iter_modules(_pkg.__path__):
            if name in ("base", "registry", "__init__"):
                continue

            try:
                mod = importlib.import_module(f"tools.web_providers.{name}")
            except ImportError as exc:
                # Some providers depend on optional packages (e.g. ddgs
                # needs the ``ddgs`` pip package).  Import failures are
                # non-fatal — the provider simply won't appear in the
                # registry.
                logger.debug(
                    "Skipping web_providers.%s — import failed: %s", name, exc
                )
                continue

            for attr_name in dir(mod):
                obj = getattr(mod, attr_name)
                if not isinstance(obj, type):
                    continue

                # Search providers
                if issubclass(obj, WebSearchProvider) and obj is not WebSearchProvider:
                    try:
                        instance = obj()
                        pname = instance.provider_name()
                    except Exception:
                        continue
                    cls._search_providers[pname] = obj
                    if pname not in cls._priority_order:
                        cls._priority_order.append(pname)

                # Extract providers
                if (
                    issubclass(obj, WebExtractProvider)
                    and obj is not WebExtractProvider
                ):
                    try:
                        instance = obj()
                        pname = instance.provider_name()
                    except Exception:
                        continue
                    cls._extract_providers[pname] = obj
                    if pname not in cls._priority_order:
                        cls._priority_order.append(pname)

        logger.debug(
            "ProviderRegistry scanned: search=%s extract=%s",
            list(cls._search_providers.keys()),
            list(cls._extract_providers.keys()),
        )

    # ── listing ─────────────────────────────────────────────────────────────

    @classmethod
    def list_search_providers(cls) -> Dict[str, Type[WebSearchProvider]]:
        """Return ``{provider_name: ProviderClass}`` for all search providers."""
        cls._ensure_scanned()
        return dict(cls._search_providers)

    @classmethod
    def list_extract_providers(cls) -> Dict[str, Type[WebExtractProvider]]:
        """Return ``{provider_name: ProviderClass}`` for all extract providers."""
        cls._ensure_scanned()
        return dict(cls._extract_providers)

    # ── lookup ──────────────────────────────────────────────────────────────

    @classmethod
    def get_search_provider(cls, name: str) -> Optional[Type[WebSearchProvider]]:
        """Return the provider class for *name*, or ``None``."""
        cls._ensure_scanned()
        return cls._search_providers.get(name)

    @classmethod
    def get_extract_provider(cls, name: str) -> Optional[Type[WebExtractProvider]]:
        """Return the provider class for *name*, or ``None``."""
        cls._ensure_scanned()
        return cls._extract_providers.get(name)

    # ── availability gates ──────────────────────────────────────────────────

    @classmethod
    def is_search_available(cls, name: str) -> bool:
        """Return ``True`` when *name* is registered and its env vars are set."""
        cls._ensure_scanned()
        provider_cls = cls._search_providers.get(name)
        if provider_cls is None:
            return False
        try:
            return provider_cls().is_configured()
        except Exception:
            return False

    @classmethod
    def is_extract_available(cls, name: str) -> bool:
        """Return ``True`` when *name* is registered and its env vars are set."""
        cls._ensure_scanned()
        provider_cls = cls._extract_providers.get(name)
        if provider_cls is None:
            return False
        try:
            return provider_cls().is_configured()
        except Exception:
            return False

    @classmethod
    def any_search_available(cls) -> bool:
        """Return ``True`` when at least one search provider is configured."""
        cls._ensure_scanned()
        for name in cls._search_providers:
            if cls.is_search_available(name):
                return True
        return False

    @classmethod
    def any_extract_available(cls) -> bool:
        """Return ``True`` when at least one extract provider is configured."""
        cls._ensure_scanned()
        for name in cls._extract_providers:
            if cls.is_extract_available(name):
                return True
        return False

    @classmethod
    def find_first_available(cls) -> Optional[str]:
        """Return the name of the highest-priority configured provider.

        Priority is registration order (first found = highest).
        Used as the auto-detect fallback when no config key is set.
        """
        cls._ensure_scanned()
        for name in cls._priority_order:
            if cls.is_search_available(name):
                return name
        return None

    @classmethod
    def find_first_extract_available(cls) -> Optional[str]:
        """Return the name of the highest-priority configured extract provider."""
        cls._ensure_scanned()
        for name in cls._priority_order:
            if cls.is_extract_available(name):
                return name
        return None

    # ── env var collection ──────────────────────────────────────────────────

    @classmethod
    def all_required_env_vars(cls) -> Set[str]:
        """Collect all env vars declared by registered providers.

        Used for ``requires_env`` metadata in tool registration.
        """
        cls._ensure_scanned()
        env_vars: Set[str] = set()
        for provider_cls in list(cls._search_providers.values()) + list(
            cls._extract_providers.values()
        ):
            try:
                instance = provider_cls()
                if hasattr(instance, "required_env_vars"):
                    env_vars.update(instance.required_env_vars)
            except Exception:
                pass
        return env_vars
