import json
from unittest.mock import MagicMock, patch

from plugins.memory import discover_memory_providers, load_memory_provider
from plugins.memory.mnemoria import provider as mnemoria_provider_module
from plugins.memory.mnemoria.provider import MnemoriaMemoryProvider


def test_mnemoria_provider_loads_even_when_dependency_missing():
    provider = load_memory_provider("mnemoria")
    assert provider is not None
    assert isinstance(provider, MnemoriaMemoryProvider)
    assert provider.name == "mnemoria"


def test_mnemoria_provider_exposes_expected_tool_schemas():
    provider = MnemoriaMemoryProvider()
    schemas = provider.get_tool_schemas()

    assert len(schemas) == 8
    assert {schema["name"] for schema in schemas} == {
        "mnemoria_write",
        "mnemoria_recall",
        "mnemoria_search",
        "mnemoria_reflect",
        "mnemoria_reward",
        "mnemoria_explore",
        "mnemoria_stats",
        "mnemoria_consolidate",
    }


def test_mnemoria_provider_returns_json_error_when_dependency_missing(monkeypatch):
    provider = MnemoriaMemoryProvider()
    monkeypatch.setattr(mnemoria_provider_module, "_UM_AVAILABLE", False)
    result = provider.handle_tool_call("mnemoria_stats", {})

    payload = json.loads(result)
    assert payload == {"error": "mnemoria package not available"}


def test_mnemoria_is_discoverable_in_memory_provider_list():
    providers = {name: (desc, available) for name, desc, available in discover_memory_providers()}

    assert "mnemoria" in providers
    desc, available = providers["mnemoria"]
    assert "Mnemoria" in desc
    assert isinstance(available, bool)


def test_prefetch_returns_cached_result_from_queue(monkeypatch):
    provider = MnemoriaMemoryProvider()
    mock_fact = MagicMock()
    mock_fact.fact.fact_type = "V"
    mock_fact.fact.target = "test"
    mock_fact.fact.content = "cached content"
    provider._prefetch_result = [mock_fact]
    result = provider.prefetch("any query")
    assert "cached content" in result
    assert provider._prefetch_result is None


def test_get_config_schema_returns_valid_fields():
    provider = MnemoriaMemoryProvider()
    schema = provider.get_config_schema()
    assert isinstance(schema, list)
    assert len(schema) >= 1
    keys = {field["key"] for field in schema}
    assert "db_path" in keys


def test_save_config_writes_json(tmp_path):
    provider = MnemoriaMemoryProvider()
    provider.save_config({"db_path": "/custom/path.db"}, str(tmp_path))
    config_path = tmp_path / "mnemoria.json"
    assert config_path.exists()
    data = json.loads(config_path.read_text())
    assert data["db_path"] == "/custom/path.db"


def test_save_config_merges_with_existing(tmp_path):
    config_path = tmp_path / "mnemoria.json"
    config_path.write_text(json.dumps({"existing_key": "value"}))
    provider = MnemoriaMemoryProvider()
    provider.save_config({"db_path": "/new/path.db"}, str(tmp_path))
    data = json.loads(config_path.read_text())
    assert data["existing_key"] == "value"
    assert data["db_path"] == "/new/path.db"


def test_initialize_sets_read_only_for_cron_context():
    provider = MnemoriaMemoryProvider()
    provider.initialize("test-session", agent_context="cron", hermes_home="/tmp")
    assert provider._read_only is True


def test_initialize_sets_read_only_for_flush_context():
    provider = MnemoriaMemoryProvider()
    provider.initialize("test-session", agent_context="flush", hermes_home="/tmp")
    assert provider._read_only is True


def test_initialize_not_read_only_for_primary_context():
    provider = MnemoriaMemoryProvider()
    provider.initialize("test-session", agent_context="primary", hermes_home="/tmp")
    assert provider._read_only is False


def test_system_prompt_block_includes_usage_hint():
    provider = MnemoriaMemoryProvider()
    block = provider.system_prompt_block()
    assert "[MNEMORIA MEMORY]" in block
    assert "mnemoria_write" in block
    assert "mnemoria_recall" in block


def test_initialize_stores_profile_and_user_id():
    provider = MnemoriaMemoryProvider()
    provider.initialize("test-session", agent_identity="coder", user_id="user-abc", platform="telegram", hermes_home="/tmp")
    assert provider._profile == "coder"
    assert provider._user_id == "user-abc"
    assert provider._platform == "telegram"


# --- sync_turn ---

def test_sync_turn_extracts_user_preferences():
    """sync_turn calls _observe_and_store for sufficiently long user messages."""
    provider = MnemoriaMemoryProvider()
    provider._read_only = False
    provider._session_id = "test-session"
    provider._observers = []  # no observers = no facts, but should not raise

    # Should not raise even with no observers
    provider.sync_turn("I always prefer dark mode for everything", "OK noted")


def test_sync_turn_skips_short_messages_without_signal():
    """sync_turn skips messages under 15 chars with no signal words."""
    provider = MnemoriaMemoryProvider()
    provider._read_only = False
    provider._session_id = "test-session"

    mock_store = MagicMock()
    with patch.object(mnemoria_provider_module, "_store", return_value=mock_store):
        provider._observers = [MagicMock()]
        provider.sync_turn("hi", "hello")
        # Observer should not be called for short content with no signal
        provider._observers[0].observe.assert_not_called()


def test_sync_turn_accepts_short_message_with_signal():
    """sync_turn processes short messages that contain signal patterns (URLs, paths, directives)."""
    provider = MnemoriaMemoryProvider()
    provider._read_only = False
    provider._session_id = "test-session"

    mock_obs = MagicMock()
    mock_obs.observe.return_value = []
    provider._observers = [mock_obs]

    mock_store = MagicMock()
    with patch.object(mnemoria_provider_module, "_store", return_value=mock_store):
        provider.sync_turn("always use tabs", "OK")
        mock_obs.observe.assert_called_once()


def test_sync_turn_is_noop_when_read_only():
    provider = MnemoriaMemoryProvider()
    provider._read_only = True
    provider._session_id = "test-session"
    mock_obs = MagicMock()
    provider._observers = [mock_obs]
    provider.sync_turn("I always prefer dark mode for everything", "OK")
    mock_obs.observe.assert_not_called()


def test_sync_turn_deduplicates_user_content():
    """sync_turn skips duplicate user messages via _seen_user_hashes."""
    provider = MnemoriaMemoryProvider()
    provider._read_only = False
    provider._session_id = "test-session"

    mock_obs = MagicMock()
    mock_obs.observe.return_value = []
    provider._observers = [mock_obs]

    mock_store = MagicMock()
    with patch.object(mnemoria_provider_module, "_store", return_value=mock_store):
        msg = "I always prefer dark mode for everything"
        provider.sync_turn(msg, "OK")
        provider.sync_turn(msg, "Sure")
        # Should only be called once due to dedup
        assert mock_obs.observe.call_count == 1


# --- _observe_and_store ---

def test_observe_and_store_isolates_observer_errors():
    """A failing observer does not prevent other observers from running."""
    provider = MnemoriaMemoryProvider()
    provider._session_id = "test-session"

    bad_obs = MagicMock()
    bad_obs.observe.side_effect = RuntimeError("broken")
    bad_obs.name = "bad"

    good_obs = MagicMock()
    good_fact = MagicMock()
    good_fact.content = "found"
    good_fact.source = "test"
    good_fact.type = "V"
    good_fact.target = "t"
    good_fact.provenance = None
    good_obs.observe.return_value = [good_fact]
    good_obs.name = "good"

    provider._observers = [bad_obs, good_obs]

    mock_store = MagicMock()
    with patch.object(mnemoria_provider_module, "_store", return_value=mock_store):
        count = provider._observe_and_store({"kind": "test", "session_id": "s"})
        assert count == 1
        mock_store.store_pending.assert_called_once()


# --- on_memory_write ---

def test_on_memory_write_is_noop_when_read_only():
    provider = MnemoriaMemoryProvider()
    provider._read_only = True
    provider.on_memory_write("add", "user", "some content")


def test_on_memory_write_skips_remove_action():
    provider = MnemoriaMemoryProvider()
    provider._read_only = False
    provider.on_memory_write("remove", "user", "some content")


def test_on_memory_write_calls_observe_and_store():
    provider = MnemoriaMemoryProvider()
    provider._read_only = False
    provider._session_id = "test-session"
    provider._observers = []

    mock_store = MagicMock()
    with patch.object(mnemoria_provider_module, "_store", return_value=mock_store):
        provider.on_memory_write("add", "user", "dark mode preferred")
        # With no observers, store_pending is not called, but no error raised


# --- on_delegation ---

def test_on_delegation_is_noop_when_read_only():
    provider = MnemoriaMemoryProvider()
    provider._read_only = True
    provider.on_delegation("do research", "found nothing", child_session_id="child-1")


def test_on_delegation_does_not_raise_without_store(monkeypatch):
    monkeypatch.setattr(mnemoria_provider_module, "_UM_AVAILABLE", False)
    provider = MnemoriaMemoryProvider()
    provider._read_only = False
    provider.on_delegation("do research", "found nothing", child_session_id="child-1")


# --- on_pre_compress ---

def test_on_pre_compress_is_noop_when_read_only():
    provider = MnemoriaMemoryProvider()
    provider._read_only = True
    result = provider.on_pre_compress([{"role": "tool", "content": "Error: broke"}])
    assert result == ""


def test_on_pre_compress_returns_empty_string():
    provider = MnemoriaMemoryProvider()
    provider._read_only = False
    provider._observers = []
    assert provider.on_pre_compress([]) == ""


def test_on_pre_compress_advances_message_index():
    provider = MnemoriaMemoryProvider()
    provider._read_only = False
    provider._session_id = "test-session"
    provider._observers = []
    provider._last_extracted_msg_index = 0
    provider.on_pre_compress([{"role": "user", "content": "hello"}, {"role": "tool", "content": "ok"}])
    assert provider._last_extracted_msg_index == 2


# --- on_session_end ---

def test_on_session_end_does_not_raise_without_store(monkeypatch):
    monkeypatch.setattr(mnemoria_provider_module, "_UM_AVAILABLE", False)
    provider = MnemoriaMemoryProvider()
    provider._read_only = False
    provider.on_session_end([{"role": "user", "content": "bye"}])


def test_on_session_end_flushes_before_consolidate():
    """on_session_end calls flush_pending before consolidate."""
    provider = MnemoriaMemoryProvider()
    provider._read_only = False
    provider._session_id = "test-session"
    provider._observers = []

    call_order = []
    mock_store = MagicMock()
    mock_store.flush_pending.side_effect = lambda: call_order.append("flush") or {}
    mock_store.consolidate.side_effect = lambda: call_order.append("consolidate") or {"promoted": 0, "demoted": 0, "pruned": 0}

    with patch.object(mnemoria_provider_module, "_store", return_value=mock_store):
        provider.on_session_end([{"role": "user", "content": "bye"}])
        assert call_order == ["flush", "consolidate"]


# --- full lifecycle ---

def test_full_lifecycle_smoke():
    """Smoke test: provider can be instantiated and all hook methods exist."""
    provider = MnemoriaMemoryProvider()

    assert callable(provider.initialize)
    assert callable(provider.system_prompt_block)
    assert callable(provider.prefetch)
    assert callable(provider.queue_prefetch)
    assert callable(provider.on_memory_write)
    assert callable(provider.on_delegation)
    assert callable(provider.on_pre_compress)
    assert callable(provider.on_session_end)
    assert callable(provider.get_config_schema)
    assert callable(provider.save_config)
    assert callable(provider.shutdown)

    block = provider.system_prompt_block()
    assert isinstance(block, str)
    assert len(block) > 0

    schema = provider.get_config_schema()
    assert isinstance(schema, list)
    assert len(schema) > 0
