"""Episodic Memory — persistent self-hosted memory for Hermes Agent.

Provides structured episodic memory with SQLite FTS5 search, entity tracking,
session journaling, and temporal quality tools. Zero external dependencies
beyond what Hermes already uses.

Config in $HERMES_HOME/config.yaml:
  memory:
    memory_enabled: true
    provider: episodic
    memory_char_limit: 2200
"""

# Config FIRST — other submodules depend on these constants
from .config import ENABLE_SESSION_JOURNAL, ENABLE_LLM_EXTRACTION
from .store import EpisodicStore
from .provider import EpisodicMemoryProvider


def register(ctx) -> None:
    """Register Episodic Memory as a memory provider plugin.

    Called by both the memory provider system (which passes a collector
    with register_memory_provider) and the general plugin system (which
    passes a PluginContext without that method). Guard against the latter
    to avoid noisy startup warnings.
    """
    if hasattr(ctx, "register_memory_provider"):
        ctx.register_memory_provider(EpisodicMemoryProvider())
