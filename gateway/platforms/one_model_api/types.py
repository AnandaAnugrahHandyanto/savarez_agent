"""Shared types for the one-model API protocol adapter layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class RuntimeContext:
    """Hermes-resolved upstream runtime passed into protocol adapters.

    This is deliberately not an account object. Account selection, credential
    pools, OAuth refresh, cooldown, failover, and concurrency are owned by
    Hermes before this layer runs. The adapter receives only the already
    resolved transport details it needs to speak the upstream protocol.
    """

    api_mode: str
    base_url: str | None
    model: str | None
    provider: str | None = None

    @classmethod
    def from_mapping(cls, runtime: Mapping[str, Any]) -> "RuntimeContext":
        return cls(
            api_mode=str(runtime.get("api_mode") or "").strip().lower(),
            base_url=str(runtime.get("base_url") or "") or None,
            model=str(runtime.get("model") or runtime.get("default_model") or "") or None,
            provider=str(runtime.get("provider") or "") or None,
        )
