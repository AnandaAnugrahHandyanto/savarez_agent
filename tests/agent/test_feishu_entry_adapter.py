"""Tests for FeishuEntryAdapter wrapper."""

import inspect
import textwrap

import pytest

from agent.managed_agents.feishu_entry_adapter import (
    FeishuEntryAdapter,
    register_feishu_entry_adapter,
    _validate_feishu_payload,
    _workspace_for,
    _session_for,
    _detect_intent,
    _format_timestamp,
)
from agent.managed_agents.entry_adapter import (
    EntryAdapter,
    EntryAdapterRegistry,
    UnsupportedEntryPointError,
)
from agent.managed_agents.entry_event import EntryEvent
from agent.managed_agents.workspace import Workspace, DEFAULT_WORKSPACE_ID
from agent.managed_agents.session import Session, DEFAULT_SESSION_ID


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _valid_feishu_payload(**overrides) -> dict:
    """Return a minimal valid Feishu message payload."""
    base = {
        "chat_id": "oc_xxx",
        "message_id": "om_001",
        "open_id": "ou_111",
        "content": "hello hermes",
    }
    base.update(overrides)
    return base


def _valid_feishu_thread_payload(**overrides) -> dict:
    """Return a valid Feishu thread message payload."""
    base = _valid_feishu_payload()
    base["thread_id"] = "om_thread_999"
    base.update(overrides)
    return base


def _valid_feishu_with_session_key(**overrides) -> dict:
    """Return a Feishu payload with explicit session_key."""
    base = _valid_feishu_payload()
    base["session_key"] = "feishu:oc_xxx:thread:om_thread_999"
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def test_feishu_adapter_registration():
    """Feishu adapter can be registered and retrieved."""
    reg = EntryAdapterRegistry()
    adapter = register_feishu_entry_adapter(reg)
    assert reg.get("feishu") is adapter
    assert adapter.entrypoint == "feishu"


def test_feishu_adapter_registration_with_app_id():
    """Registration passes app_id to the adapter."""
    reg = EntryAdapterRegistry()
    adapter = register_feishu_entry_adapter(reg, app_id="app-001")
    assert adapter.app_id == "app-001"


def test_feishu_adapter_duplicate_rejected():
    """Registering a second feishu adapter raises ValueError."""
    reg = EntryAdapterRegistry()
    register_feishu_entry_adapter(reg)
    with pytest.raises(ValueError, match="already registered"):
        register_feishu_entry_adapter(reg)


def test_feishu_adapter_satisfies_protocol():
    """FeishuEntryAdapter is structurally conformant with EntryAdapter protocol."""
    adapter = FeishuEntryAdapter()
    assert isinstance(adapter, EntryAdapter)


# ---------------------------------------------------------------------------
# Normalization: valid message -> EntryEvent
# ---------------------------------------------------------------------------

def test_normalize_valid_message_produces_entry_event():
    """A valid Feishu payload normalizes into an EntryEvent."""
    adapter = FeishuEntryAdapter()
    raw = _valid_feishu_payload()
    event = adapter.normalize_event(raw)

    assert event.event_id == "om_001"
    assert event.entrypoint == "feishu"
    assert event.origin_entrypoint == "feishu"
    assert event.message == "hello hermes"
    assert event.external_user_id == "ou_111"
    assert event.external_channel_id == "oc_xxx"
    assert event.workspace_id == "ws-feishu-oc_xxx"
    assert event.session_id == "ses-feishu-oc_xxx"


def test_normalize_with_tenant_id():
    """Tenant ID present -> workspace includes tenant."""
    adapter = FeishuEntryAdapter()
    raw = _valid_feishu_payload(tenant_id="tenant-123")
    event = adapter.normalize_event(raw)
    assert event.workspace_id == "ws-feishu-tenant-123"


def test_normalize_with_user_id():
    """user_id present -> takes precedence over open_id for external_user_id."""
    adapter = FeishuEntryAdapter()
    raw = _valid_feishu_payload(user_id="u_222")
    event = adapter.normalize_event(raw)
    assert event.external_user_id == "u_222"


def test_normalize_preserves_dedupe_key():
    """Event includes a dedupe_key based on Feishu message ID."""
    adapter = FeishuEntryAdapter()
    raw = _valid_feishu_payload()
    event = adapter.normalize_event(raw)
    assert event.dedupe_key == "feishu:om_001"


def test_normalize_includes_thread_id():
    """Thread payloads include external_thread_id and thread-based session."""
    adapter = FeishuEntryAdapter()
    raw = _valid_feishu_thread_payload()
    event = adapter.normalize_event(raw)
    assert event.external_thread_id == "om_thread_999"
    assert event.session_id == "ses-feishu-thread-om_thread_999"


def test_normalize_with_session_key():
    """Explicit session_key takes precedence over generated session."""
    adapter = FeishuEntryAdapter()
    raw = _valid_feishu_with_session_key()
    event = adapter.normalize_event(raw)
    assert event.session_id == "feishu:oc_xxx:thread:om_thread_999"


def test_normalize_with_timestamp():
    """Timestamp is formatted to ISO 8601."""
    adapter = FeishuEntryAdapter()
    raw = _valid_feishu_payload(timestamp=1717200000)
    event = adapter.normalize_event(raw)
    assert event.created_at is not None
    assert "2024" in event.created_at


# ---------------------------------------------------------------------------
# Workspace / Session mapping
# ---------------------------------------------------------------------------

def test_workspace_with_tenant():
    """Tenant present -> ws-feishu-{tenant_id}."""
    assert _workspace_for("tenant-123", "oc_xxx") == "ws-feishu-tenant-123"


def test_workspace_without_tenant():
    """No tenant -> ws-feishu-{chat_id}."""
    assert _workspace_for("", "oc_xxx") == "ws-feishu-oc_xxx"


def test_session_with_session_key():
    """Session key present -> returns session_key directly."""
    assert _session_for("oc_xxx", None, "feishu:custom") == "feishu:custom"


def test_session_with_thread():
    """Thread present -> ses-feishu-thread-{thread_id}."""
    assert _session_for("oc_xxx", "thread-999", "") == "ses-feishu-thread-thread-999"


def test_session_without_thread():
    """No thread -> ses-feishu-{chat_id}."""
    assert _session_for("oc_xxx", None, "") == "ses-feishu-oc_xxx"


def test_resolve_workspace_returns_mapped_workspace():
    """resolve_workspace returns a Workspace when workspace_id is non-default."""
    adapter = FeishuEntryAdapter()
    raw = _valid_feishu_payload()
    event = adapter.normalize_event(raw)
    ws = adapter.resolve_workspace(event)
    assert ws is not None
    assert ws.workspace_id == "ws-feishu-oc_xxx"
    assert ws.entrypoint == "feishu"


def test_resolve_workspace_returns_none_for_default():
    """resolve_workspace returns None when workspace_id is DEFAULT."""
    adapter = FeishuEntryAdapter()
    event = EntryEvent(event_id="e", entrypoint="feishu", workspace_id=DEFAULT_WORKSPACE_ID)
    assert adapter.resolve_workspace(event) is None


def test_resolve_session_returns_mapped_session():
    """resolve_session returns a Session when session_id is non-default."""
    adapter = FeishuEntryAdapter()
    raw = _valid_feishu_payload()
    event = adapter.normalize_event(raw)
    ws = Workspace(workspace_id=event.workspace_id, name="W", entrypoint="feishu")
    session = adapter.resolve_session(event, ws)
    assert session is not None
    assert session.session_id == "ses-feishu-oc_xxx"
    assert session.entrypoint == "feishu"


def test_resolve_session_returns_none_for_default():
    """resolve_session returns None when session_id is DEFAULT."""
    adapter = FeishuEntryAdapter()
    event = EntryEvent(event_id="e", entrypoint="feishu", session_id=DEFAULT_SESSION_ID)
    ws = Workspace(workspace_id="ws-test", name="W", entrypoint="feishu")
    assert adapter.resolve_session(event, ws) is None


# ---------------------------------------------------------------------------
# Missing required fields -> ValueError
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("missing_field", ["chat_id", "message_id", "open_id", "content"])
def test_missing_required_field_raises(missing_field):
    """Each required field must be present; missing one raises ValueError."""
    adapter = FeishuEntryAdapter()
    raw = _valid_feishu_payload()
    del raw[missing_field]
    with pytest.raises(ValueError, match="missing required fields"):
        adapter.normalize_event(raw)


def test_empty_payload_raises():
    """An empty payload raises ValueError for missing fields."""
    adapter = FeishuEntryAdapter()
    with pytest.raises(ValueError, match="missing required fields"):
        adapter.normalize_event({})


def test_validate_feishu_payload_raises_for_missing():
    """_validate_feishu_payload helper raises for incomplete payloads."""
    with pytest.raises(ValueError, match="missing required fields"):
        _validate_feishu_payload({"chat_id": "oc_xxx"})


def test_validate_feishu_payload_passes_for_complete():
    """_validate_feishu_payload helper passes for complete payloads."""
    raw = _valid_feishu_payload()
    _validate_feishu_payload(raw)  # no exception


# ---------------------------------------------------------------------------
# Unsupported entrypoint via registry
# ---------------------------------------------------------------------------

def test_unsupported_entrypoint_raises_via_registry():
    """Ingesting via 'feishu' when not registered raises UnsupportedEntryPointError."""
    reg = EntryAdapterRegistry()
    with pytest.raises(UnsupportedEntryPointError) as exc_info:
        reg.ingest(_valid_feishu_payload(), "feishu")
    assert exc_info.value.entrypoint == "feishu"


def test_unsupported_entrypoint_after_unregister_raises():
    """After unregistration, feishu entrypoint raises UnsupportedEntryPointError."""
    reg = EntryAdapterRegistry()
    register_feishu_entry_adapter(reg)
    reg.unregister("feishu")
    with pytest.raises(UnsupportedEntryPointError):
        reg.ingest(_valid_feishu_payload(), "feishu")


# ---------------------------------------------------------------------------
# Adapter isolation: no direct agent/task/router/policy calls
# ---------------------------------------------------------------------------

def test_adapter_does_not_call_agents():
    """FeishuEntryAdapter methods must not reference agent execution internals."""
    src = textwrap.dedent(inspect.getsource(FeishuEntryAdapter))
    assert "execute" not in src
    assert "decide_execution_policy" not in src
    assert "run_agent" not in src

    src_normalize = textwrap.dedent(inspect.getsource(FeishuEntryAdapter.normalize_event))
    assert "route" not in src_normalize.lower()


# ---------------------------------------------------------------------------
# Health: configured vs unconfigured
# ---------------------------------------------------------------------------

def test_health_configured():
    """Health reports 'configured' when app_id is set."""
    adapter = FeishuEntryAdapter(app_id="app-001")
    h = adapter.health()
    assert h["entrypoint"] == "feishu"
    assert h["status"] == "configured"
    assert h["app_id"] == "app-001"


def test_health_unconfigured():
    """Health reports 'unconfigured' when app_id is not set."""
    adapter = FeishuEntryAdapter()
    h = adapter.health()
    assert h["entrypoint"] == "feishu"
    assert h["status"] == "unconfigured"
    assert "reason" in h


def test_health_via_registry():
    """Registry.health() includes feishu adapter health."""
    reg = EntryAdapterRegistry()
    register_feishu_entry_adapter(reg, app_id="app-001")
    h = reg.health("feishu")
    assert h["status"] == "configured"


# ---------------------------------------------------------------------------
# Intent detection
# ---------------------------------------------------------------------------

def test_detect_intent_command():
    """Content starting with '/' -> intent='command'."""
    assert _detect_intent("/deploy") == "command"


def test_detect_intent_mention():
    """Content containing '@' -> intent='mention'."""
    assert _detect_intent("hello @hermes") == "mention"


def test_detect_intent_none():
    """Regular message -> intent=None."""
    assert _detect_intent("hello") is None


# ---------------------------------------------------------------------------
# Timestamp formatting
# ---------------------------------------------------------------------------

def test_format_timestamp_epoch():
    """Epoch timestamp formatted to ISO 8601."""
    result = _format_timestamp(1717200000)
    assert "2024" in result
    assert "T" in result


def test_format_timestamp_string():
    """String timestamp returned as-is."""
    assert _format_timestamp("2024-06-01T00:00:00Z") == "2024-06-01T00:00:00Z"


# ---------------------------------------------------------------------------
# Integration: full pipeline via registry
# ---------------------------------------------------------------------------

def test_full_pipeline_normalize_via_registry():
    """Full pipeline: register adapter -> ingest -> EntryEvent."""
    reg = EntryAdapterRegistry()
    register_feishu_entry_adapter(reg, app_id="app-001")
    raw = _valid_feishu_payload(open_id="ou_222", user_id="u_333")
    event = reg.ingest(raw, "feishu")

    assert event.entrypoint == "feishu"
    assert event.origin_entrypoint == "feishu"
    assert event.workspace_id == "ws-feishu-oc_xxx"
    assert event.session_id == "ses-feishu-oc_xxx"
    assert event.external_user_id == "u_333"


def test_full_pipeline_thread_via_registry():
    """Full pipeline with thread: session maps to thread, not channel."""
    reg = EntryAdapterRegistry()
    register_feishu_entry_adapter(reg)
    raw = _valid_feishu_thread_payload(open_id="ou_444")
    event = reg.ingest(raw, "feishu")

    assert event.session_id == "ses-feishu-thread-om_thread_999"
    assert event.external_thread_id == "om_thread_999"


def test_full_pipeline_session_key_via_registry():
    """Full pipeline with explicit session_key: session uses the key."""
    reg = EntryAdapterRegistry()
    register_feishu_entry_adapter(reg)
    raw = _valid_feishu_with_session_key()
    event = reg.ingest(raw, "feishu")

    assert event.session_id == "feishu:oc_xxx:thread:om_thread_999"
