"""Tests for EntryAdapter interface and registry."""

import pytest

from agent.managed_agents.entry_adapter import (
    EntryAdapter,
    EntryAdapterRegistry,
    UnsupportedEntryPointError,
)
from agent.managed_agents.entry_event import EntryEvent
from agent.managed_agents.workspace import Workspace, DEFAULT_WORKSPACE_ID
from agent.managed_agents.session import Session, DEFAULT_SESSION_ID


# ---------------------------------------------------------------------------
# Test adapter — minimal conformance
# ---------------------------------------------------------------------------

class _TestAdapter:
    """Minimal EntryAdapter conformance — used for registration/UAT tests."""

    entrypoint = "feishu"

    def normalize_event(self, raw: dict) -> EntryEvent:
        return EntryEvent(
            event_id="test-ev",
            entrypoint="feishu",
            message=raw.get("message", ""),
            external_user_id=raw.get("user_id"),
        )

    def resolve_workspace(self, event: EntryEvent) -> Workspace | None:
        return Workspace(workspace_id="ws-feishu", name="Feishu Workspace", entrypoint="feishu")

    def resolve_session(self, event: EntryEvent, workspace: Workspace) -> Session | None:
        return Session(session_id="s-feishu", workspace_id=workspace.workspace_id, entrypoint="feishu")

    def health(self) -> dict:
        return {"entrypoint": "feishu", "status": "connected"}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def test_registry_register_and_get():
    reg = EntryAdapterRegistry()
    reg.register(_TestAdapter())
    adapter = reg.get("feishu")
    assert adapter is not None
    assert adapter.entrypoint == "feishu"


def test_registry_duplicate_rejected():
    reg = EntryAdapterRegistry()
    reg.register(_TestAdapter())
    with pytest.raises(ValueError, match="already registered"):
        reg.register(_TestAdapter())


def test_registry_replace_overrides():
    reg = EntryAdapterRegistry()
    reg.register(_TestAdapter())

    class _Alt:
        entrypoint = "feishu"

        def normalize_event(self, raw):
            return EntryEvent(event_id="alt", entrypoint="feishu", message="alt")

        def resolve_workspace(self, event):
            return Workspace(workspace_id="ws-alt", name="Alt", entrypoint="feishu")

        def resolve_session(self, event, workspace):
            return Session(session_id="s-alt", workspace_id=workspace.workspace_id, entrypoint="feishu")

        def health(self):
            return {"entrypoint": "feishu", "status": "connected"}

    reg.replace(_Alt())
    event = reg.ingest({"message": "hello"}, "feishu")
    assert event.event_id == "alt"
    assert event.message == "alt"


def test_registry_unregister():
    reg = EntryAdapterRegistry()
    reg.register(_TestAdapter())
    reg.unregister("feishu")
    assert reg.get("feishu") is None


def test_registry_entrypoints():
    reg = EntryAdapterRegistry()
    assert reg.entrypoints == []
    reg.register(_TestAdapter())
    assert reg.entrypoints == ["feishu"]


# ---------------------------------------------------------------------------
# Ingest (normalization) + Protocol compliance
# ---------------------------------------------------------------------------

def test_ingest_routes_through_adapter():
    reg = EntryAdapterRegistry()
    reg.register(_TestAdapter())
    event = reg.ingest({"message": "ping", "user_id": "u1"}, "feishu")
    assert event.entrypoint == "feishu"
    assert event.message == "ping"
    assert event.external_user_id == "u1"


def test_ingest_unsupported_entrypoint_raises():
    """Unregistered entrypoints must raise UnsupportedEntryPointError,
    not silently normalize to 'cli'."""
    reg = EntryAdapterRegistry()
    with pytest.raises(UnsupportedEntryPointError) as exc_info:
        reg.ingest({"message": "hello"}, "discord")
    assert exc_info.value.entrypoint == "discord"
    assert "discord" in str(exc_info.value)


def test_ingest_unsupported_empty_payload_raises():
    """Even an empty payload must raise for unsupported entrypoints."""
    reg = EntryAdapterRegistry()
    with pytest.raises(UnsupportedEntryPointError) as exc_info:
        reg.ingest({}, "nonexistent")
    assert exc_info.value.entrypoint == "nonexistent"


def test_ingest_unsupported_after_unregister_raises():
    """After unregister, a previously supported entrypoint must raise."""
    reg = EntryAdapterRegistry()
    reg.register(_TestAdapter())
    reg.unregister("feishu")
    with pytest.raises(UnsupportedEntryPointError):
        reg.ingest({"message": "still here"}, "feishu")


def test_unsupported_entrypoint_error_is_value_error():
    """UnsupportedEntryPointError is a ValueError for catch compatibility."""
    err = UnsupportedEntryPointError("test")
    assert isinstance(err, ValueError)
    assert err.entrypoint == "test"


def test_test_adapter_satisfies_protocol():
    """Confirm _TestAdapter is structurally conformant."""
    a = _TestAdapter()
    assert isinstance(a, EntryAdapter)


def test_minimal_explicit_protocol():
    """Explicitly typed adapter passes isinstance check."""

    class _Explicit:
        entrypoint = "web"

        def normalize_event(self, raw):
            return EntryEvent(event_id="e1", entrypoint="web")

        def resolve_workspace(self, event):
            return None

        def resolve_session(self, event, workspace):
            return None

        def health(self):
            return {"entrypoint": "web", "status": "connected"}

    a: EntryAdapter = _Explicit()
    assert isinstance(a, EntryAdapter)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

def test_health_single_registered():
    reg = EntryAdapterRegistry()
    reg.register(_TestAdapter())
    h = reg.health("feishu")
    assert h["status"] == "connected"


def test_health_single_unregistered():
    reg = EntryAdapterRegistry()
    h = reg.health("discord")
    assert h == {"discord": {"status": "unregistered"}}


def test_health_aggregated():
    reg = EntryAdapterRegistry()
    reg.register(_TestAdapter())

    class _Broken:
        entrypoint = "discord"

        def normalize_event(self, raw):
            return EntryEvent(event_id="ev", entrypoint="discord", message="")

        def resolve_workspace(self, event):
            return None

        def resolve_session(self, event, workspace):
            return None

        def health(self):
            raise RuntimeError("oops")

    reg.register(_Broken())
    h = reg.health()
    assert h["feishu"]["status"] == "connected"
    assert h["discord"]["status"] == "error"


def test_health_no_adapters():
    reg = EntryAdapterRegistry()
    assert reg.health() == {}


# ---------------------------------------------------------------------------
# Workspace/Session resolution (pass-through to adapter)
# ---------------------------------------------------------------------------

def test_adapter_resolve_workspace():
    reg = EntryAdapterRegistry()
    reg.register(_TestAdapter())
    adapter = reg.get("feishu")
    event = EntryEvent(event_id="ev", entrypoint="feishu", message="test")
    ws = adapter.resolve_workspace(event)
    assert ws is not None
    assert ws.workspace_id == "ws-feishu"


def test_adapter_resolve_session():
    reg = EntryAdapterRegistry()
    reg.register(_TestAdapter())
    adapter = reg.get("feishu")
    event = EntryEvent(event_id="ev", entrypoint="feishu", message="test")
    ws = Workspace(workspace_id="ws-feishu", name="Feishu Workspace", entrypoint="feishu")
    s = adapter.resolve_session(event, ws)
    assert s is not None
    assert s.session_id == "s-feishu"


def test_adapter_does_not_call_agents():
    """Guard: EntryAdapter methods must not import or call core agent execution."""
    import inspect, textwrap
    src = textwrap.dedent(inspect.getsource(_TestAdapter.resolve_workspace))
    assert "execute" not in src
    assert "decide_execution_policy" not in src
    assert "route" not in src.lower()
    assert "run_agent" not in src
