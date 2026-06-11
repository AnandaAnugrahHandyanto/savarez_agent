"""Phase 3 Brain Host seam (central-brain-openclaw.md §11 "3c/3d").

The host is the single home for cross-construction-site sharing:
  * credential-pool / API-key sharing across the ~20 AIAgent construction sites
  * tool-schema caching
  * memory-session sharing
  * per-intent model/policy selection

Construction-cost caching (TASK 2.6).  Profiling AIAgent.__init__ showed the
dominant *repeat* cost is the model-context-length resolution inside
``ContextCompressor.__init__`` (~0.8 s per construction: the Ollama
``/api/show`` probe POSTs to the live base_url and only persists successful
probes, so OpenRouter/Anthropic-style endpoints re-probe every time).  Tool
definitions — the other obvious candidate — are already memoized process-wide
by ``model_tools.get_tool_definitions`` keyed on ``registry._generation``,
which bumps on every MCP register/deregister (initial discovery and
``tools/list_changed`` refresh), so duplicating that cache here would add
nothing.  ``build_agent`` therefore installs a context-length resolution memo
(the dict lives on this singleton) into ``agent.model_metadata``; see
``install_context_length_cache`` there for the key/TTL/exclusion rules.

Richer fields on AgentSpec (toolsets, model_policy, memory_key …) will be added
as later construction sites migrate.  Until then, ``kwargs`` carries the exact
constructor kwargs that the call site already builds.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentSpec:
    """Descriptor passed from a construction site to BrainHost.

    intent: short human-readable tag for the construction site
        (e.g. ``"tui_gateway"``).  Used for logging and future routing.
    kwargs: the exact keyword arguments to forward to AIAgent.__init__.
        This thin representation is intentional: additional fields
        (toolsets, model_policy, memory_key) will be added here as
        individual sites migrate; for now the host acts as a transparent
        proxy so parity with direct construction is provably trivially true.
    """

    intent: str
    kwargs: dict[str, Any] = field(default_factory=dict)


class BrainHost:
    """Process-singleton that owns AIAgent construction for migrated call sites.

    Phase 3 "Brain host" seam — one place that owns cross-site sharing for
    the ~20 construction sites.  Construction forwards kwargs identically to
    direct calls (parity-tested); the host's first real value is the
    process-level context-length resolution memo installed by
    :meth:`build_agent` (TASK 2.6 — see module docstring for why that cache,
    not tool schemas, was the measured win).

    Usage::

        from agent.brain_host import AgentSpec, BrainHost
        agent = BrainHost.get().build_agent(AgentSpec(intent="tui_gateway", kwargs=kw))
    """

    _instance: BrainHost | None = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        # Model-context-length resolution memo (TASK 2.6).  Entries are
        # ``key tuple -> (monotonic deadline, ctx)``; the key/TTL/exclusion
        # rules live next to the consumer in agent.model_metadata
        # (install_context_length_cache).  The dict lives here — not in
        # model_metadata — so flag-off processes never allocate it and the
        # host owns explicit invalidation (clear_context_length_cache).
        self._context_length_cache: dict[tuple, tuple[float, int]] = {}

    @classmethod
    def get(cls) -> "BrainHost":
        """Return (or create) the process-level BrainHost singleton."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def clear_context_length_cache(self) -> None:
        """Explicitly drop all memoized context-length resolutions.

        For callers that change provider state out from under the resolver
        (tests, future model-switch hooks).  Safe at any time — the next
        construction simply re-resolves.
        """
        self._context_length_cache.clear()

    def build_agent(self, spec: AgentSpec):
        """Construct and return an AIAgent for *spec*.

        Construction is identical to ``AIAgent(**spec.kwargs)`` — same kwargs,
        same defaults (parity-tested) — but runs with the host's
        context-length resolution memo installed, so repeat constructions
        skip the per-construction network probe inside
        ``ContextCompressor.__init__``.  Tool definitions stay covered by the
        ``registry._generation``-keyed memo in ``model_tools`` (MCP discovery
        bumps the generation, so post-discovery constructions rebuild).
        """
        from agent import model_metadata

        # Idempotent: re-installing the same dict heals module reloads and
        # costs one attribute assignment.
        model_metadata.install_context_length_cache(self._context_length_cache)

        from run_agent import AIAgent  # lazy: heavy import, only when used

        return AIAgent(**spec.kwargs)
