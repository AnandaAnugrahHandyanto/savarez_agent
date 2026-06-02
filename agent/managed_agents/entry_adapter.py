"""EntryAdapter interface and registry.

All external entrypoints (Feishu, Discord, Web, CLI, future Mac App) implement
the EntryAdapter protocol to normalize inbound events into EntryEvent.

Adapters must NOT call agents directly. They should normalize external input
into EntryEvent and rely on Hermes Core to resolve workspace/session, create
tasks, route agents, and write ledger events.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from .entry_event import EntryEvent
from .workspace import Entrypoint, Workspace
from .session import Session


class UnsupportedEntryPointError(ValueError):
    """Raised when an inbound event references an entrypoint with no registered adapter.

    Callers must handle this explicitly rather than relying on silent fallback.
    """

    def __init__(self, entrypoint: str) -> None:
        self.entrypoint = entrypoint
        super().__init__(
            f"No EntryAdapter registered for entrypoint '{entrypoint}'. "
            f"Register an adapter before ingesting events from this source."
        )


@runtime_checkable
class EntryAdapter(Protocol):
    """Protocol that every Hermes entry adapter must satisfy.

    Implementations should be stateless or self-contained. They must not
    modify core execution state (task creation, routing, policy) directly.
    """

    entrypoint: Entrypoint

    def normalize_event(self, raw: dict[str, Any]) -> EntryEvent:
        """Convert an adapter-specific inbound payload to a canonical EntryEvent.

        This is the single normalization point. Every adapter is responsible
        for mapping its own fields (e.g. Discord channel_id, Feishu thread_id)
        into the shared EntryEvent schema.
        """
        ...

    def resolve_workspace(self, event: EntryEvent) -> Workspace | None:
        """Map the event's external source/channel to a Workspace.

        May return None if no mapping exists; the caller should fall back
        to the default workspace.
        """
        ...

    def resolve_session(
        self, event: EntryEvent, workspace: Workspace
    ) -> Session | None:
        """Map the event's external channel/thread to a Session within a workspace.

        May return None if no mapping exists; the caller should fall back
        to the default session.
        """
        ...

    def health(self) -> dict[str, Any]:
        """Return a health snapshot dict for this adapter.

        Must include at least:
            entrypoint: str
            status: "connected" | "disconnected" | "unknown"
        May include additional adapter-specific fields.
        """
        ...


class EntryAdapterRegistry:
    """Thread-safe registry of EntryAdapter implementations.

    Registered at startup. Handles:
    - deterministic duplicate rejection
    - adapter lookup by entrypoint
    - ingest: raw -> normalize -> EntryEvent
    - health aggregation

    Ingesting from an unregistered entrypoint raises UnsupportedEntryPointError.
    """

    def __init__(self) -> None:
        self._adapters: dict[str, EntryAdapter] = {}

    # -- registration -------------------------------------------------------

    def register(self, adapter: EntryAdapter) -> None:
        """Register an adapter.

        Raises ValueError if an adapter for the same entrypoint is already
        registered. Use replace() if you need to override.
        """
        key = adapter.entrypoint
        if key in self._adapters:
            raise ValueError(
                f"EntryAdapter for entrypoint '{key}' is already registered. "
                f"Use replace() to override."
            )
        self._adapters[key] = adapter

    def replace(self, adapter: EntryAdapter) -> None:
        """Register or replace an adapter for an entrypoint (no error on dup)."""
        self._adapters[adapter.entrypoint] = adapter

    def unregister(self, entrypoint: str) -> None:
        """Remove a registered adapter."""
        self._adapters.pop(entrypoint, None)

    # -- lookup -------------------------------------------------------------

    def get(self, entrypoint: str) -> EntryAdapter | None:
        """Look up a registered adapter by entrypoint, or None."""
        return self._adapters.get(entrypoint)

    @property
    def entrypoints(self) -> list[str]:
        """Return a sorted list of registered entrypoint names."""
        return sorted(self._adapters.keys())

    # -- ingest -------------------------------------------------------------

    def ingest(self, raw: dict[str, Any], entrypoint: str) -> EntryEvent:
        """Route a raw inbound payload through the correct adapter.

        Raises UnsupportedEntryPointError if no adapter is registered for
        the given entrypoint. Callers must handle unsupported sources
        explicitly rather than relying on silent fallback.
        """
        adapter = self.get(entrypoint)
        if adapter is None:
            raise UnsupportedEntryPointError(entrypoint)
        return adapter.normalize_event(raw)

    # -- health -------------------------------------------------------------

    def health(self, entrypoint: str | None = None) -> dict[str, Any]:
        """Return health snapshot(s).

        If *entrypoint* is given, return that single adapter's health.
        Otherwise return a dict keyed by entrypoint.
        """
        if entrypoint is not None:
            adapter = self.get(entrypoint)
            if adapter is None:
                return {entrypoint: {"status": "unregistered"}}
            try:
                return adapter.health()
            except Exception:
                return {"entrypoint": entrypoint, "status": "error"}
        return {
            ep: _adapter_health_safe(ep, a) for ep, a in self._adapters.items()
        }


def _adapter_health_safe(entrypoint: str, adapter: EntryAdapter) -> dict[str, Any]:
    try:
        return adapter.health()
    except Exception:
        return {"entrypoint": entrypoint, "status": "error"}
