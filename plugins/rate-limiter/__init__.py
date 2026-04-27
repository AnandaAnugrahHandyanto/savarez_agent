"""Rate limiter plugin for Hermes Agent.

Provides runtime controls for the built-in rate limiter via /ratelimit slash command.

Core enforcement is always active via run_agent.py — this plugin adds runtime controls
to enable/disable rate limiting and adjust RPM without editing config.yaml.
"""

from __future__ import annotations

from . import commands


def register(ctx) -> None:
    """Register the rate limiter plugin with the plugin system."""
    ctx.register_command(
        "ratelimit",
        handler=commands.handle,
        description="Runtime controls for the built-in rate limiter.",
    )
