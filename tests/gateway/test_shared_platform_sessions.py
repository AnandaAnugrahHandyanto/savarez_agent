from pathlib import Path

from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.session import SessionSource, SessionStore


def _store(tmp_path: Path) -> SessionStore:
    cfg = GatewayConfig(
        platforms={
            Platform.BLUEBUBBLES: PlatformConfig(
                enabled=True,
                extra={
                    "shared_session_key": "Rogher Mobile HQ",
                    "shared_session_title": "Rogher Mobile HQ",
                },
            )
        }
    )
    store = SessionStore(tmp_path / "sessions", cfg)
    # These tests only care about the gateway session index. Avoid coupling to
    # SQLite state.db setup in the unit test.
    store._db = None
    return store


def test_configured_platform_shared_session_key_reuses_session_across_chats(tmp_path):
    store = _store(tmp_path)
    first = SessionSource(
        platform=Platform.BLUEBUBBLES,
        chat_id="iMessage;+;chat-one",
        chat_type="dm",
        user_id="nick",
        chat_name="Thread One",
    )
    second = SessionSource(
        platform=Platform.BLUEBUBBLES,
        chat_id="iMessage;+;chat-two",
        chat_type="dm",
        user_id="nick",
        chat_name="Thread Two",
    )

    first_entry = store.get_or_create_session(first)
    second_entry = store.get_or_create_session(second)

    assert first_entry.session_key == "agent:main:bluebubbles:shared:rogher-mobile-hq"
    assert second_entry.session_key == first_entry.session_key
    assert second_entry.session_id == first_entry.session_id
    assert second_entry.display_name == "Rogher Mobile HQ"
    # Delivery metadata is not collapsed: replies can still target the real
    # iMessage thread that originally created the shared session.
    assert first_entry.origin is not None
    assert first_entry.origin.chat_id == "iMessage;+;chat-one"


def test_unconfigured_platform_keeps_default_dm_isolation(tmp_path):
    store = SessionStore(tmp_path / "sessions", GatewayConfig())
    store._db = None
    first = SessionSource(platform=Platform.BLUEBUBBLES, chat_id="one", chat_type="dm")
    second = SessionSource(platform=Platform.BLUEBUBBLES, chat_id="two", chat_type="dm")

    assert store.get_or_create_session(first).session_key == "agent:main:bluebubbles:dm:one"
    assert store.get_or_create_session(second).session_key == "agent:main:bluebubbles:dm:two"
