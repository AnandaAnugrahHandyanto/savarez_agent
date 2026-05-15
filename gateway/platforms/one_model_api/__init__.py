"""Lightweight protocol adapter layer for API Server passthrough mode.

The one-model API intentionally only adapts protocols. Hermes remains
responsible for credentials, provider/runtime resolution, OAuth, account pools,
quota, cooldown, failover, and scheduling.
"""

from .registry import get_passthrough_adapter

__all__ = ["get_passthrough_adapter"]
