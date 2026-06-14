from types import SimpleNamespace

from gateway.config import Platform
from gateway.platforms.base import MessageEvent, MessageType
from gateway.session import SessionSource

import gateway.run as gateway_run


def _fast_response(text, *, platform=Platform.TELEGRAM, message_type=MessageType.TEXT):
    return gateway_run._pga_order_start_fast_response(
        text,
        platform=platform,
        message_type=message_type,
    )


def test_pga_order_start_fast_path_resolves_canonical_locations():
    assert _fast_response("start a new order for sj") == (
        "Starting an order for San Jose. What do you need?"
    )
    assert _fast_response("@d start order for Santa Cruz") == (
        "Starting an order for Santa Cruz. What do you need?"
    )
    assert _fast_response("new order sq") == (
        "Starting an order for Soquel. What do you need?"
    )
    assert _fast_response("start sj order") == (
        "Starting an order for San Jose. What do you need?"
    )


def test_pga_order_start_fast_path_asks_for_missing_or_unclear_location():
    assert _fast_response("start a new order") == (
        "Which location is this for: San Jose, Santa Cruz, or Soquel?"
    )
    assert _fast_response("start order for walnut creek") == (
        "Which location is this for: San Jose, Santa Cruz, or Soquel?"
    )


def test_pga_order_start_fast_path_leaves_inline_items_to_agent():
    assert _fast_response("start a new order for sj two cases eggs") is None
    assert _fast_response("start order for San Jose: oat milk and cashews") is None
    assert _fast_response("I need to order trash bags and eggs for Santa Cruz") is None


def test_pga_order_start_fast_path_is_telegram_text_only():
    assert _fast_response("start a new order for sj", platform=Platform.DISCORD) is None
    assert _fast_response("start a new order for sj", message_type=MessageType.VOICE) is None


def test_pga_location_followup_fast_path_resolves_prompt_answer():
    history = [
        {
            "role": "assistant",
            "content": "Which location is this for: San Jose, Santa Cruz, or Soquel?",
        }
    ]

    assert gateway_run._pga_order_location_followup_fast_response(
        "San jose",
        platform=Platform.TELEGRAM,
        message_type=MessageType.TEXT,
        history=history,
    ) == "Starting an order for San Jose. What do you need?"
    assert gateway_run._pga_order_location_followup_fast_response(
        "walnut creek",
        platform=Platform.TELEGRAM,
        message_type=MessageType.TEXT,
        history=history,
    ) == "Which location is this for: San Jose, Santa Cruz, or Soquel?"


def test_pga_location_followup_fast_path_requires_prior_prompt():
    history = [{"role": "assistant", "content": "Something else"}]

    assert gateway_run._pga_order_location_followup_fast_response(
        "San jose",
        platform=Platform.TELEGRAM,
        message_type=MessageType.TEXT,
        history=history,
    ) is None


class RecordingSessionStore:
    def __init__(self):
        self.messages = []
        self.updates = []
        self.resets = []
        self.reset_entry = None

    def append_to_transcript(self, session_id, message):
        self.messages.append((session_id, message))

    def update_session(self, session_key, last_prompt_tokens=None):
        self.updates.append((session_key, last_prompt_tokens))

    def reset_session(self, session_key):
        self.resets.append(session_key)
        return self.reset_entry


def test_runner_fast_path_persists_transcript_and_updates_session(monkeypatch, tmp_path):
    profile_home = tmp_path / "profiles" / "pga"
    profile_home.mkdir(parents=True)
    monkeypatch.setattr(gateway_run, "_hermes_home", profile_home)

    runner = object.__new__(gateway_run.GatewayRunner)
    runner.session_store = RecordingSessionStore()

    source = SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="chat-1",
        user_id="user-1",
    )
    event = MessageEvent(
        text="start a new order for sj",
        message_type=MessageType.TEXT,
        source=source,
    )
    session_entry = SimpleNamespace(
        session_id="session-1",
        was_auto_reset=True,
        auto_reset_reason="idle",
    )

    response = gateway_run.GatewayRunner._maybe_handle_pga_order_start_fast_path(
        runner,
        event=event,
        source=source,
        session_entry=session_entry,
        session_key="telegram:chat-1",
        is_new_session=True,
    )

    assert response == "Starting an order for San Jose. What do you need?"
    assert [msg["role"] for _, msg in runner.session_store.messages] == ["user", "assistant"]
    assert runner.session_store.messages[0][1]["content"] == "start a new order for sj"
    assert runner.session_store.messages[1][1]["content"] == response
    assert runner.session_store.updates == [("telegram:chat-1", 0)]
    assert session_entry.was_auto_reset is False
    assert session_entry.auto_reset_reason is None


def test_runner_fast_path_resets_existing_session_before_persisting(monkeypatch, tmp_path):
    profile_home = tmp_path / "profiles" / "pga"
    profile_home.mkdir(parents=True)
    monkeypatch.setattr(gateway_run, "_hermes_home", profile_home)

    runner = object.__new__(gateway_run.GatewayRunner)
    store = RecordingSessionStore()
    store.reset_entry = SimpleNamespace(session_id="session-new")
    runner.session_store = store
    runner._session_model_overrides = {"telegram:chat-1": {"model": "old"}}
    runner._pending_model_notes = {"telegram:chat-1": "old note"}
    runner._evict_cached_agent = lambda session_key: setattr(runner, "evicted", session_key)
    runner._set_session_reasoning_override = (
        lambda session_key, value: setattr(runner, "reasoning_reset", (session_key, value))
    )

    source = SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="chat-1",
        user_id="user-1",
    )
    event = MessageEvent(
        text="start a new order for sj",
        message_type=MessageType.TEXT,
        source=source,
    )
    session_entry = SimpleNamespace(session_id="session-old")

    response = gateway_run.GatewayRunner._maybe_handle_pga_order_start_fast_path(
        runner,
        event=event,
        source=source,
        session_entry=session_entry,
        session_key="telegram:chat-1",
        is_new_session=False,
    )

    assert response == "Starting an order for San Jose. What do you need?"
    assert store.resets == ["telegram:chat-1"]
    assert [session_id for session_id, _ in store.messages] == ["session-new", "session-new"]
    assert runner.evicted == "telegram:chat-1"
    assert runner.reasoning_reset == ("telegram:chat-1", None)
    assert runner._session_model_overrides == {}
    assert runner._pending_model_notes == {}


def test_runner_location_followup_fast_path_persists_transcript(monkeypatch, tmp_path):
    profile_home = tmp_path / "profiles" / "pga"
    profile_home.mkdir(parents=True)
    monkeypatch.setattr(gateway_run, "_hermes_home", profile_home)

    runner = object.__new__(gateway_run.GatewayRunner)
    runner.session_store = RecordingSessionStore()

    source = SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="chat-1",
        user_id="user-1",
    )
    event = MessageEvent(
        text="San jose",
        message_type=MessageType.TEXT,
        source=source,
    )
    session_entry = SimpleNamespace(session_id="session-1")
    history = [
        {
            "role": "assistant",
            "content": "Which location is this for: San Jose, Santa Cruz, or Soquel?",
        }
    ]

    response = gateway_run.GatewayRunner._maybe_handle_pga_order_location_followup_fast_path(
        runner,
        event=event,
        source=source,
        session_entry=session_entry,
        session_key="telegram:chat-1",
        history=history,
    )

    assert response == "Starting an order for San Jose. What do you need?"
    assert [msg["role"] for _, msg in runner.session_store.messages] == ["user", "assistant"]
    assert runner.session_store.messages[0][1]["content"] == "San jose"
    assert runner.session_store.messages[1][1]["content"] == response
    assert runner.session_store.updates == [("telegram:chat-1", 0)]


def test_runner_fast_path_is_profile_scoped(monkeypatch, tmp_path):
    profile_home = tmp_path / "profiles" / "cantaritos"
    profile_home.mkdir(parents=True)
    monkeypatch.setattr(gateway_run, "_hermes_home", profile_home)

    runner = object.__new__(gateway_run.GatewayRunner)
    runner.session_store = RecordingSessionStore()

    source = SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="chat-1",
        user_id="user-1",
    )
    event = MessageEvent(
        text="start a new order for sj",
        message_type=MessageType.TEXT,
        source=source,
    )
    session_entry = SimpleNamespace(session_id="session-1")

    response = gateway_run.GatewayRunner._maybe_handle_pga_order_start_fast_path(
        runner,
        event=event,
        source=source,
        session_entry=session_entry,
        session_key="telegram:chat-1",
        is_new_session=False,
    )

    assert response is None
    assert runner.session_store.messages == []
    assert runner.session_store.updates == []
