"""Tests for Discord EntryAdapter MVP."""

import inspect
import textwrap

import pytest

from agent.managed_agents.discord_adapter import (
    DiscordAdapter,
    register_discord_adapter,
    _validate_discord_payload,
    _is_bot_message,
    _workspace_for,
    _session_for,
    _detect_intent,
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

def _valid_discord_payload(**overrides) -> dict:
    """Return a minimal valid Discord message payload."""
    base = {
        "id": "msg-001",
        "guild_id": "guild-123",
        "channel_id": "ch-456",
        "category_id": "cat-789",
        "author": {"id": "user-111", "username": "testuser"},
        "content": "hello hermes",
    }
    base.update(overrides)
    return base


def _valid_discord_thread_payload(**overrides) -> dict:
    """Return a valid Discord thread message payload."""
    base = _valid_discord_payload()
    base["thread_id"] = "999"
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def test_discord_adapter_registration():
    """Discord adapter can be registered and retrieved."""
    reg = EntryAdapterRegistry()
    adapter = register_discord_adapter(reg)
    assert reg.get("discord") is adapter
    assert adapter.entrypoint == "discord"


def test_discord_adapter_registration_with_bot_user_id():
    """Registration passes bot_user_id to the adapter."""
    reg = EntryAdapterRegistry()
    adapter = register_discord_adapter(reg, bot_user_id="bot-001")
    assert adapter.bot_user_id == "bot-001"


def test_discord_adapter_duplicate_rejected():
    """Registering a second discord adapter raises ValueError."""
    reg = EntryAdapterRegistry()
    register_discord_adapter(reg)
    with pytest.raises(ValueError, match="already registered"):
        register_discord_adapter(reg)


def test_discord_adapter_satisfies_protocol():
    """DiscordAdapter is structurally conformant with EntryAdapter protocol."""
    adapter = DiscordAdapter()
    assert isinstance(adapter, EntryAdapter)


# ---------------------------------------------------------------------------
# Normalization: valid message -> EntryEvent
# ---------------------------------------------------------------------------

def test_normalize_valid_message_produces_entry_event():
    """A valid Discord payload normalizes into an EntryEvent."""
    adapter = DiscordAdapter()
    raw = _valid_discord_payload()
    event = adapter.normalize_event(raw)

    assert event.event_id == "msg-001"
    assert event.entrypoint == "discord"
    assert event.origin_entrypoint == "discord"
    assert event.message == "hello hermes"
    assert event.external_user_id == "user-111"
    assert event.external_source_id == "guild-123"
    assert event.external_channel_id == "ch-456"
    assert event.workspace_id == "ws-discord-cat-789"
    assert event.session_id == "ses-discord-ch-456"


def test_normalize_preserves_dedupe_key():
    """Event includes a dedupe_key based on Discord message ID."""
    adapter = DiscordAdapter()
    raw = _valid_discord_payload()
    event = adapter.normalize_event(raw)
    assert event.dedupe_key == "discord:msg-001"


def test_normalize_includes_thread_id():
    """Thread payloads include external_thread_id."""
    adapter = DiscordAdapter()
    raw = _valid_discord_thread_payload()
    event = adapter.normalize_event(raw)
    assert event.external_thread_id == "999"
    assert event.session_id == "ses-discord-thread-999"


# ---------------------------------------------------------------------------
# Workspace / Session mapping
# ---------------------------------------------------------------------------

def test_workspace_with_category():
    """Category present -> ws-discord-{category_id}."""
    assert _workspace_for("g1", "cat-789") == "ws-discord-cat-789"


def test_workspace_without_category():
    """No category -> ws-discord-guild-{guild_id}."""
    assert _workspace_for("g1", "") == "ws-discord-guild-g1"


def test_session_with_thread():
    """Thread present -> ses-discord-thread-{thread_id}."""
    assert _session_for("ch-1", "999") == "ses-discord-thread-999"


def test_session_without_thread():
    """No thread -> ses-discord-{channel_id}."""
    assert _session_for("ch-1", None) == "ses-discord-ch-1"


def test_resolve_workspace_returns_mapped_workspace():
    """resolve_workspace returns a Workspace when workspace_id is non-default."""
    adapter = DiscordAdapter()
    raw = _valid_discord_payload()
    event = adapter.normalize_event(raw)
    ws = adapter.resolve_workspace(event)
    assert ws is not None
    assert ws.workspace_id == "ws-discord-cat-789"
    assert ws.entrypoint == "discord"


def test_resolve_workspace_returns_none_for_default():
    """resolve_workspace returns None when workspace_id is DEFAULT."""
    adapter = DiscordAdapter()
    event = EntryEvent(event_id="e", entrypoint="discord", workspace_id=DEFAULT_WORKSPACE_ID)
    assert adapter.resolve_workspace(event) is None


def test_resolve_session_returns_mapped_session():
    """resolve_session returns a Session when session_id is non-default."""
    adapter = DiscordAdapter()
    raw = _valid_discord_payload()
    event = adapter.normalize_event(raw)
    ws = Workspace(workspace_id=event.workspace_id, name="W", entrypoint="discord")
    session = adapter.resolve_session(event, ws)
    assert session is not None
    assert session.session_id == "ses-discord-ch-456"
    assert session.entrypoint == "discord"


def test_resolve_session_returns_none_for_default():
    """resolve_session returns None when session_id is DEFAULT."""
    adapter = DiscordAdapter()
    event = EntryEvent(event_id="e", entrypoint="discord", session_id=DEFAULT_SESSION_ID)
    ws = Workspace(workspace_id="ws-test", name="W", entrypoint="discord")
    assert adapter.resolve_session(event, ws) is None


# ---------------------------------------------------------------------------
# Missing required fields -> ValueError
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("missing_field", ["guild_id", "channel_id", "author", "content"])
def test_missing_required_field_raises(missing_field):
    """Each required field must be present; missing one raises ValueError."""
    adapter = DiscordAdapter()
    raw = _valid_discord_payload()
    del raw[missing_field]
    with pytest.raises(ValueError, match="missing required fields"):
        adapter.normalize_event(raw)


def test_empty_payload_raises():
    """An empty payload raises ValueError for missing fields."""
    adapter = DiscordAdapter()
    with pytest.raises(ValueError, match="missing required fields"):
        adapter.normalize_event({})


def test_validate_discord_payload_raises_for_missing():
    """_validate_discord_payload helper raises for incomplete payloads."""
    with pytest.raises(ValueError, match="missing required fields"):
        _validate_discord_payload({"guild_id": "g"})


def test_validate_discord_payload_passes_for_complete():
    """_validate_discord_payload helper passes for complete payloads."""
    raw = _valid_discord_payload()
    _validate_discord_payload(raw)  # no exception


# ---------------------------------------------------------------------------
# Bot / self message rejection
# ---------------------------------------------------------------------------

def test_bot_author_flag_rejects():
    """author.bot=True raises ValueError."""
    adapter = DiscordAdapter()
    raw = _valid_discord_payload(author={"id": "user-1", "bot": True})
    with pytest.raises(ValueError, match="bot/self messages"):
        adapter.normalize_event(raw)


def test_self_message_rejected_by_bot_user_id():
    """Message from bot_user_id raises ValueError."""
    adapter = DiscordAdapter(bot_user_id="user-111")
    raw = _valid_discord_payload(author={"id": "user-111", "username": "bot"})
    with pytest.raises(ValueError, match="bot/self messages"):
        adapter.normalize_event(raw)


def test_non_bot_message_accepted():
    """Message from a non-bot user with a different bot_user_id is accepted."""
    adapter = DiscordAdapter(bot_user_id="bot-999")
    raw = _valid_discord_payload(author={"id": "user-111"})
    event = adapter.normalize_event(raw)
    assert event.external_user_id == "user-111"


def test_is_bot_message_true_when_flag_set():
    """_is_bot_message returns True when author.bot is True."""
    assert _is_bot_message({"id": "u1", "bot": True}, None) is True


def test_is_bot_message_true_when_matches_bot_user_id():
    """_is_bot_message returns True when author.id matches bot_user_id."""
    assert _is_bot_message({"id": "bot-1"}, "bot-1") is True


def test_is_bot_message_false_for_regular_user():
    """_is_bot_message returns False for regular users."""
    assert _is_bot_message({"id": "user-1"}, "bot-1") is False


# ---------------------------------------------------------------------------
# Unsupported entrypoint via registry
# ---------------------------------------------------------------------------

def test_unsupported_entrypoint_raises_via_registry():
    """Ingesting via 'discord' when not registered raises UnsupportedEntryPointError."""
    reg = EntryAdapterRegistry()
    with pytest.raises(UnsupportedEntryPointError) as exc_info:
        reg.ingest(_valid_discord_payload(), "discord")
    assert exc_info.value.entrypoint == "discord"


def test_unsupported_entrypoint_after_unregister_raises():
    """After unregistration, discord entrypoint raises UnsupportedEntryPointError."""
    reg = EntryAdapterRegistry()
    register_discord_adapter(reg)
    reg.unregister("discord")
    with pytest.raises(UnsupportedEntryPointError):
        reg.ingest(_valid_discord_payload(), "discord")


# ---------------------------------------------------------------------------
# Adapter isolation: no direct agent/task/router/policy calls
# ---------------------------------------------------------------------------

def test_adapter_does_not_call_agents():
    """DiscordAdapter methods must not reference agent execution internals."""
    src = textwrap.dedent(inspect.getsource(DiscordAdapter))
    assert "execute" not in src
    assert "decide_execution_policy" not in src
    assert "run_agent" not in src

    src_normalize = textwrap.dedent(inspect.getsource(DiscordAdapter.normalize_event))
    assert "route" not in src_normalize.lower()


# ---------------------------------------------------------------------------
# Health: configured vs unconfigured
# ---------------------------------------------------------------------------

def test_health_configured():
    """Health reports 'configured' when bot_user_id is set."""
    adapter = DiscordAdapter(bot_user_id="bot-001")
    h = adapter.health()
    assert h["entrypoint"] == "discord"
    assert h["status"] == "configured"
    assert h["bot_user_id"] == "bot-001"


def test_health_unconfigured():
    """Health reports 'unconfigured' when bot_user_id is not set."""
    adapter = DiscordAdapter()
    h = adapter.health()
    assert h["entrypoint"] == "discord"
    assert h["status"] == "unconfigured"
    assert "reason" in h


def test_health_via_registry():
    """Registry.health() includes discord adapter health."""
    reg = EntryAdapterRegistry()
    register_discord_adapter(reg, bot_user_id="bot-001")
    h = reg.health("discord")
    assert h["status"] == "configured"


# ---------------------------------------------------------------------------
# Intent detection
# ---------------------------------------------------------------------------

def test_detect_intent_mention():
    """mentions_me=True -> intent='mention'."""
    raw = _valid_discord_payload(mentions_me=True)
    assert _detect_intent(raw) == "mention"


def test_detect_intent_command():
    """Content starting with '!' -> intent='command'."""
    raw = _valid_discord_payload(content="!deploy")
    assert _detect_intent(raw) == "command"


def test_detect_intent_none():
    """Regular message with no mention -> intent=None."""
    raw = _valid_discord_payload()
    assert _detect_intent(raw) is None


# ---------------------------------------------------------------------------
# Integration: full pipeline via registry
# ---------------------------------------------------------------------------

def test_full_pipeline_normalize_via_registry():
    """Full pipeline: register adapter -> ingest -> EntryEvent."""
    reg = EntryAdapterRegistry()
    register_discord_adapter(reg, bot_user_id="bot-001")
    raw = _valid_discord_payload(author={"id": "user-111", "username": "alice"})
    event = reg.ingest(raw, "discord")

    assert event.entrypoint == "discord"
    assert event.origin_entrypoint == "discord"
    assert event.workspace_id == "ws-discord-cat-789"
    assert event.session_id == "ses-discord-ch-456"
    assert event.external_user_id == "user-111"


def test_full_pipeline_thread_via_registry():
    """Full pipeline with thread: session maps to thread, not channel."""
    reg = EntryAdapterRegistry()
    register_discord_adapter(reg)
    raw = _valid_discord_thread_payload(author={"id": "user-222"})
    event = reg.ingest(raw, "discord")

    assert event.session_id == "ses-discord-thread-999"
    assert event.external_thread_id == "999"
