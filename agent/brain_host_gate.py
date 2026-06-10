"""Flag-gated construction chokepoint for AIAgent (central-brain-openclaw.md §11 "3c/3d").

``build_agent(intent, **kwargs)`` is the one-line form of the HERMES_BRAIN_HOST
gate that every migrated construction site uses::

    from agent.brain_host_gate import build_agent
    agent = build_agent("cron", model=model, api_key=..., ...)

This module is deliberately separate from ``agent.brain_host`` and imports
nothing heavy at module level: when the flag is off (the default),
``agent.brain_host`` is never imported at all — the zero-footprint property
that the flag-gate tests assert — and ``run_agent`` is only imported at call
time, preserving the lazy-import behaviour of the call sites it replaces.
"""

from __future__ import annotations

import os


def brain_host_enabled() -> bool:
    """True when the HERMES_BRAIN_HOST opt-in flag is set to exactly "1"."""
    return os.environ.get("HERMES_BRAIN_HOST", "").strip() == "1"


def build_agent(intent: str, **kwargs):
    """Construct an AIAgent, routing through BrainHost when the flag is on.

    intent: short tag for the construction site (e.g. ``"cron"``,
        ``"delegate"``) — recorded on the AgentSpec for logging and future
        per-intent routing.
    kwargs: the exact keyword arguments the call site would have passed to
        ``AIAgent(...)`` directly.  Both paths forward them unchanged, so
        flag off/on parity is structural.
    """
    if brain_host_enabled():
        from agent.brain_host import AgentSpec, BrainHost

        return BrainHost.get().build_agent(AgentSpec(intent=intent, kwargs=kwargs))

    from run_agent import AIAgent

    return AIAgent(**kwargs)
