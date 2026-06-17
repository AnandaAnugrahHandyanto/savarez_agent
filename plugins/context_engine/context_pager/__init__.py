"""Context Pager — Semantic Dedup context engine plugin.

Registers itself as a ContextEngine implementation via the plugin
registration protocol (``register(ctx)`` pattern).

Usage:
    Set ``context.engine: "context_pager"`` in config.yaml to activate.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from .engine import ContextPagerEngine

logger = logging.getLogger(__name__)


def register(ctx) -> None:
    """Register the ContextPagerEngine with the plugin system.

    The engine reads optional configuration from ``ctx.config``
    (which maps to Hermes config.yaml).
    """
    config: Dict[str, Any] = getattr(ctx, "config", {})
    context_pager_cfg = config.get("context_pager", {})

    engine = ContextPagerEngine(
        protect_last_n=context_pager_cfg.get("protect_last_n", 6),
        protect_first_n=context_pager_cfg.get("protect_first_n", 3),
        threshold_percent=context_pager_cfg.get("threshold_percent", 0.75),
        sqlite_path=context_pager_cfg.get("sqlite_path"),
        openviking_enabled=context_pager_cfg.get("openviking", {}).get("enabled", True),
        context_length=config.get("context_length", 128_000),
        fallback_compressor=context_pager_cfg.get("fallback_compressor", False),
    )

    ctx.register_context_engine(engine)
    logger.info("ContextPagerEngine registered")
