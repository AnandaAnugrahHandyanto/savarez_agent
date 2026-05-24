"""Camofox web extraction plugin — bundled, auto-loaded.

Backed by a local Camofox REST API server. Extract-only (no search).
Returns deterministic Markdown derived from accessibility snapshots,
bypassing the auxiliary-LLM summarization step.
"""

from __future__ import annotations

from plugins.web.camofox.provider import CamofoxWebSearchProvider


def register(ctx) -> None:
    """Register the Camofox provider with the plugin context."""
    ctx.register_web_search_provider(CamofoxWebSearchProvider())
