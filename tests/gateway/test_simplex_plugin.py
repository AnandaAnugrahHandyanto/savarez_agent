"""Tests for the SimpleX Chat platform-plugin adapter.

Loaded via the ``_plugin_adapter_loader`` helper so this lives under
``plugin_adapter_simplex`` in ``sys.modules`` and cannot collide with
sibling platform-plugin tests on the same xdist worker.
"""

from __future__ import annotations

import json
import os
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.gateway._plugin_adapter_loader import load_plugin_adapter

_simplex = load_plugin_adapter("simplex")

SimplexAdapter = _simplex.SimplexAdapter
check_requirements = _simplex.check_requirements
validate_config = _simplex.validate_config
is_connected = _simplex.is_connected
register = _simplex.register
_env_enablement = _simplex._env_enablement
_standalone_send = _simplex._standalone_send
_guess_extension = _simplex._guess_extension
_is_image_ext = _simplex._is_image_ext
_is_audio_ext = _simplex._is_audio_ext
_CORR_PREFIX = _simplex._CORR_PREFIX


# ---------------------------------------------------------------------------
# 1. Platform enum (plugin-discovered, not bundled)
# ---------------------------------------------------------------------------

def test_platform_enum_resolves_via_plugin_scan():
    """The plugin filesystem scan should expose Platform("simplex")."""
    from gateway.config import Platform
    p = Platform("simplex")
    assert p.value == "simplex"
    # Identity stability — repeated lookups return the same pseudo-member
    assert Platform("simplex") is p


# ---------------------------------------------------------------------------
# 2. check_requirements / validate_config / is_connected
# ---------------------------------------------------------------------------

def test_check_requirements_needs_url(monkeypatch):
    monkeypatch.delenv("SIMPLEX_WS_URL", raising=False)
    assert check_requirements() is False


def test_check_requirements_true_when_configured(monkeypatch):
    monkeypatch.setenv("SIMPLEX_WS_URL", "ws://127.0.0.1:5225")
    # websockets is a dev dep in this repo via the test plugins; the
    # check_requirements() gate also asserts the package imports.
    websockets_present = True
    try:
        import websockets  # noqa: F401
    except ImportError:
        websockets_present = False
    assert check_requirements() is websockets_present


def test_validate_config_uses_env_or_extra():
    from gateway.config import PlatformConfig
    # Empty extra + no env → invalid
    cfg = PlatformConfig(enabled=True)
    assert validate_config(cfg) is False
    # extra-only path → valid
    cfg2 = PlatformConfig(enabled=True, extra={"ws_url": "ws://localhost:5225"})
    assert validate_config(cfg2) is True


def test_is_connected_mirrors_validate(monkeypatch):
    from gateway.config import PlatformConfig
    monkeypatch.delenv("SIMPLEX_WS_URL", raising=False)
    cfg = PlatformConfig(enabled=True, extra={"ws_url": "ws://x"})
    assert is_connected(cfg) is True
    assert is_connected(PlatformConfig(enabled=True)) is False


# ---------------------------------------------------------------------------
# 3. _env_enablement seeds PlatformConfig.extra
# ---------------------------------------------------------------------------

def test_env_enablement_none_when_unset(monkeypatch):
    monkeypatch.delenv("SIMPLEX_WS_URL", raising=False)
    assert _env_enablement() is None


def test_env_enablement_seeds_ws_url(monkeypatch):
    monkeypatch.setenv("SIMPLEX_WS_URL", "ws://127.0.0.1:5225")
    monkeypatch.delenv("SIMPLEX_HOME_CHANNEL", raising=False)
    seed = _env_enablement()
    assert seed == {"ws_url": "ws://127.0.0.1:5225"}


def test_env_enablement_seeds_home_channel(monkeypatch):
    monkeypatch.setenv("SIMPLEX_WS_URL", "ws://127.0.0.1:5225")
    monkeypatch.setenv("SIMPLEX_HOME_CHANNEL", "42")
    monkeypatch.setenv("SIMPLEX_HOME_CHANNEL_NAME", "Personal")
    seed = _env_enablement()
    assert seed["home_channel"] == {"chat_id": "42", "name": "Personal"}


def test_env_enablement_home_channel_defaults_name_to_id(monkeypatch):
    monkeypatch.setenv("SIMPLEX_WS_URL", "ws://127.0.0.1:5225")
    monkeypatch.setenv("SIMPLEX_HOME_CHANNEL", "42")
    monkeypatch.delenv("SIMPLEX_HOME_CHANNEL_NAME", raising=False)
    seed = _env_enablement()
    assert seed["home_channel"] == {"chat_id": "42", "name": "42"}


# ---------------------------------------------------------------------------
# 4. Adapter init
# ---------------------------------------------------------------------------

def test_adapter_init_custom_url():
    from gateway.config import PlatformConfig
    cfg = PlatformConfig(enabled=True, extra={"ws_url": "ws://localhost:5225"})
    adapter = SimplexAdapter(cfg)
    assert adapter.ws_url == "ws://localhost:5225"
    assert adapter._running is False
    assert adapter._ws is None


def test_adapter_init_default_url():
    from gateway.config import PlatformConfig
    cfg = PlatformConfig(enabled=True)
    adapter = SimplexAdapter(cfg)
    assert adapter.ws_url == "ws://127.0.0.1:5225"


def test_adapter_platform_identity():
    """Adapter should expose Platform("simplex") identity."""
    from gateway.config import Platform, PlatformConfig
    cfg = PlatformConfig(enabled=True)
    adapter = SimplexAdapter(cfg)
    assert adapter.platform is Platform("simplex")


# ---------------------------------------------------------------------------
# 5. Helper functions (magic-byte detection)
# ---------------------------------------------------------------------------

def test_guess_extension_png():
    assert _guess_extension(b"\x89PNG\r\n\x1a\n") == ".png"


def test_guess_extension_jpg():
    assert _guess_extension(b"\xff\xd8\xff\xe0") == ".jpg"


def test_guess_extension_ogg():
    assert _guess_extension(b"OggS\x00\x02") == ".ogg"


def test_guess_extension_unknown():
    assert _guess_extension(b"\x00\x01\x02\x03") == ".bin"


def test_is_image_ext():
    assert _is_image_ext(".png") is True
    assert _is_image_ext(".webp") is True
    assert _is_image_ext(".ogg") is False


def test_is_audio_ext():
    assert _is_audio_ext(".ogg") is True
    assert _is_audio_ext(".mp3") is True
    assert _is_audio_ext(".pdf") is False


# ---------------------------------------------------------------------------
# 6. Correlation IDs
# ---------------------------------------------------------------------------

def test_corr_id_starts_with_prefix_and_tracks_pending():
    from gateway.config import PlatformConfig
    cfg = PlatformConfig(enabled=True, extra={"ws_url": "ws://localhost:5225"})
    adapter = SimplexAdapter(cfg)
    corr_id = adapter._make_corr_id()
    assert corr_id.startswith(_CORR_PREFIX)
    assert corr_id in adapter._pending_corr_ids


def test_corr_id_pending_set_self_trims():
    from gateway.config import PlatformConfig
    cfg = PlatformConfig(enabled=True, extra={"ws_url": "ws://localhost:5225"})
    adapter = SimplexAdapter(cfg)
    adapter._max_pending_corr = 4
    for _ in range(10):
        adapter._make_corr_id()
    # After many additions, the pending set should be bounded by the trim
    # logic — at most one trim window above the cap.
    assert len(adapter._pending_corr_ids) <= adapter._max_pending_corr + 1


# ---------------------------------------------------------------------------
# 7. Outbound send (mocked WS)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_dm():
    from gateway.config import PlatformConfig
    cfg = PlatformConfig(enabled=True, extra={"ws_url": "ws://localhost:5225"})
    adapter = SimplexAdapter(cfg)

    mock_ws = AsyncMock()
    adapter._ws = mock_ws

    result = await adapter.send("contact-42", "Hello, SimpleX!")
    mock_ws.send.assert_called_once()
    payload = json.loads(mock_ws.send.call_args[0][0])
    assert payload["cmd"] == "@contact-42 Hello, SimpleX!"
    assert payload["corrId"].startswith(_CORR_PREFIX)
    assert result.success is True


@pytest.mark.asyncio
async def test_send_group():
    from gateway.config import PlatformConfig
    cfg = PlatformConfig(enabled=True, extra={"ws_url": "ws://localhost:5225"})
    adapter = SimplexAdapter(cfg)

    mock_ws = AsyncMock()
    adapter._ws = mock_ws

    result = await adapter.send("group:grp-99", "Hello, group!")
    payload = json.loads(mock_ws.send.call_args[0][0])
    assert payload["cmd"] == "#grp-99 Hello, group!"
    assert result.success is True


@pytest.mark.asyncio
async def test_send_quotes_display_names_with_spaces():
    from gateway.config import PlatformConfig
    cfg = PlatformConfig(enabled=True, extra={"ws_url": "ws://localhost:5225"})
    adapter = SimplexAdapter(cfg)

    mock_ws = AsyncMock()
    adapter._ws = mock_ws

    result = await adapter.send("Alice Smith", "Hello")
    payload = json.loads(mock_ws.send.call_args[0][0])
    assert payload["cmd"] == "@'Alice Smith' Hello"
    assert result.success is True


@pytest.mark.asyncio
async def test_send_quotes_group_names_with_spaces():
    from gateway.config import PlatformConfig
    cfg = PlatformConfig(enabled=True, extra={"ws_url": "ws://localhost:5225"})
    adapter = SimplexAdapter(cfg)

    mock_ws = AsyncMock()
    adapter._ws = mock_ws

    result = await adapter.send("group:Team Chat", "Hello")
    payload = json.loads(mock_ws.send.call_args[0][0])
    assert payload["cmd"] == "#'Team Chat' Hello"
    assert result.success is True


@pytest.mark.asyncio
async def test_send_when_ws_not_connected_reports_failure():
    from gateway.config import PlatformConfig
    cfg = PlatformConfig(enabled=True, extra={"ws_url": "ws://localhost:5225"})
    adapter = SimplexAdapter(cfg)
    adapter._send_ws = AsyncMock(return_value=False)  # type: ignore

    result = await adapter.send("contact-42", "hi")

    assert result.success is False
    assert "WebSocket unavailable" in (result.error or "")
    adapter._send_ws.assert_awaited_once()


# ---------------------------------------------------------------------------
# 8. Inbound: filter own-echo by corrId prefix
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_event_filters_own_corr_id():
    from gateway.config import PlatformConfig
    cfg = PlatformConfig(enabled=True, extra={"ws_url": "ws://localhost:5225"})
    adapter = SimplexAdapter(cfg)
    # Pretend we sent a command with this corrId
    own = adapter._make_corr_id()
    handler_mock = AsyncMock()
    adapter._handle_new_chat_item = handler_mock  # type: ignore

    await adapter._handle_event({"corrId": own, "type": "newChatItem"})
    handler_mock.assert_not_called()
    assert own not in adapter._pending_corr_ids  # discarded


@pytest.mark.asyncio
async def test_handle_event_unwraps_simplex_resp_new_chat_item():
    from gateway.config import PlatformConfig
    cfg = PlatformConfig(enabled=True, extra={"ws_url": "ws://localhost:5225"})
    adapter = SimplexAdapter(cfg)
    handler_mock = AsyncMock()
    adapter._handle_new_chat_item = handler_mock  # type: ignore

    payload = {"chatInfo": {"type": "direct"}, "chatItem": {"meta": {"itemId": 1}}}
    await adapter._handle_event({"corrId": "", "resp": {"type": "newChatItem", **payload}})

    handler_mock.assert_awaited_once_with({"type": "newChatItem", **payload})


@pytest.mark.asyncio
async def test_handle_event_unwraps_nested_simplex_new_chat_item():
    from gateway.config import PlatformConfig
    cfg = PlatformConfig(enabled=True, extra={"ws_url": "ws://localhost:5225"})
    adapter = SimplexAdapter(cfg)
    handler_mock = AsyncMock()
    adapter._handle_new_chat_item = handler_mock  # type: ignore

    wrapper = {"chatInfo": {"type": "direct"}, "chatItem": {"meta": {"itemId": 1}}}
    await adapter._handle_event({"corrId": "", "resp": {"type": "newChatItem", "chatItem": wrapper}})

    handler_mock.assert_awaited_once_with(wrapper)


@pytest.mark.asyncio
async def test_handle_event_normalizes_chatdata_catch_up_items():
    from gateway.config import PlatformConfig
    cfg = PlatformConfig(enabled=True, extra={"ws_url": "ws://localhost:5225"})
    adapter = SimplexAdapter(cfg)
    handler_mock = AsyncMock()
    adapter._handle_new_chat_item = handler_mock  # type: ignore
    adapter._catch_up_primed = True

    chat_info = {"type": "direct", "contact": {"contactId": 4, "localDisplayName": "gdg"}}
    item = {
        "meta": {"itemId": 2, "itemStatus": {"type": "rcvNew"}},
        "content": {"type": "rcvMsgContent", "msgContent": {"type": "text", "text": "hi"}},
    }
    await adapter._handle_event({
        "corrId": "simplex-catchup-tail-1",
        "resp": {"type": "chatItems", "chatItems": {"chatInfo": chat_info, "chatItems": [item]}},
    })

    handler_mock.assert_awaited_once_with({"chatInfo": chat_info, "chatItem": item}, dedupe=False)


@pytest.mark.asyncio
async def test_request_catch_up_uses_persistent_websocket_only():
    from gateway.config import PlatformConfig
    cfg = PlatformConfig(enabled=True, extra={"ws_url": "ws://localhost:5225"})
    adapter = SimplexAdapter(cfg)
    send_mock = AsyncMock(return_value=True)
    adapter._send_ws = send_mock  # type: ignore

    await adapter._request_catch_up()

    send_mock.assert_awaited_once()
    assert send_mock.await_args is not None
    args, kwargs = send_mock.await_args
    payload = args[0]
    assert payload["cmd"] == "/chats"
    assert kwargs == {"persistent_only": True}


@pytest.mark.asyncio
async def test_catch_up_chats_requests_tails_on_persistent_websocket_only():
    from gateway.config import PlatformConfig
    cfg = PlatformConfig(enabled=True, extra={"ws_url": "ws://localhost:5225"})
    adapter = SimplexAdapter(cfg)
    send_mock = AsyncMock(return_value=True)
    adapter._send_ws = send_mock  # type: ignore

    await adapter._handle_catch_up_chats([
        {"chatInfo": {"type": "direct", "contact": {"localDisplayName": "gdg"}}}
    ])

    send_mock.assert_awaited_once()
    assert send_mock.await_args is not None
    args, kwargs = send_mock.await_args
    payload = args[0]
    assert payload["cmd"] == "/tail @gdg 50"
    assert kwargs == {"persistent_only": True}
    assert adapter._catch_up_pending == 1


@pytest.mark.asyncio
async def test_catch_up_chat_items_primes_then_processes_only_new_received_items():
    from gateway.config import PlatformConfig
    cfg = PlatformConfig(enabled=True, extra={"ws_url": "ws://localhost:5225"})
    adapter = SimplexAdapter(cfg)
    handler_mock = AsyncMock()
    adapter._handle_new_chat_item = handler_mock  # type: ignore

    old_received = {
        "chatInfo": {"type": "direct", "contact": {"contactId": 4, "localDisplayName": "gdg"}},
        "chatItem": {
            "meta": {"itemId": 20, "itemStatus": {"type": "rcvNew"}},
            "content": {"type": "rcvMsgContent", "msgContent": {"type": "text", "text": "old"}},
        },
    }
    new_received = {
        "chatInfo": {"type": "direct", "contact": {"contactId": 4, "localDisplayName": "gdg"}},
        "chatItem": {
            "meta": {"itemId": 21, "itemStatus": {"type": "rcvNew"}},
            "content": {"type": "rcvMsgContent", "msgContent": {"type": "text", "text": "new"}},
        },
    }
    own_sent = {
        "chatInfo": {"type": "direct", "contact": {"contactId": 4, "localDisplayName": "gdg"}},
        "chatItem": {
            "meta": {"itemId": 22, "itemStatus": {"type": "sndRcvd"}},
            "content": {"type": "sndMsgContent", "msgContent": {"type": "text", "text": "sent"}},
        },
    }

    await adapter._handle_event({"corrId": "catchup-1", "resp": {"type": "chatItems", "chatItems": [old_received]}})
    handler_mock.assert_not_called()

    await adapter._handle_event({"corrId": "catchup-2", "resp": {"type": "chatItems", "chatItems": [old_received, own_sent, new_received]}})

    handler_mock.assert_awaited_once_with(new_received, dedupe=False)


@pytest.mark.asyncio
async def test_live_then_catch_up_duplicate_is_processed_once():
    from gateway.config import PlatformConfig
    cfg = PlatformConfig(enabled=True, extra={"ws_url": "ws://localhost:5225"})
    adapter = SimplexAdapter(cfg)
    handler_mock = AsyncMock()
    adapter.handle_message = handler_mock  # type: ignore

    item = {
        "chatInfo": {"type": "direct", "contact": {"contactId": 4, "localDisplayName": "gdg"}},
        "chatItem": {
            "meta": {"itemId": 30, "itemStatus": {"type": "rcvNew"}, "itemTs": "2026-05-15T18:20:00Z"},
            "content": {"type": "rcvMsgContent", "msgContent": {"type": "text", "text": "once"}},
        },
    }

    await adapter._handle_event({"corrId": "", "resp": {"type": "newChatItem", **item}})
    assert handler_mock.await_count == 1

    adapter._catch_up_primed = True
    await adapter._handle_event({"corrId": "catchup", "resp": {"type": "chatItems", "chatItems": [item]}})
    assert handler_mock.await_count == 1


@pytest.mark.asyncio
async def test_group_inbound_chat_id_uses_display_name_for_reply_target():
    from gateway.config import PlatformConfig
    cfg = PlatformConfig(enabled=True, extra={"ws_url": "ws://localhost:5225"})
    adapter = SimplexAdapter(cfg)
    handler_mock = AsyncMock()
    adapter.handle_message = handler_mock  # type: ignore

    await adapter._handle_new_chat_item({
        "chatInfo": {
            "type": "group",
            "groupInfo": {"groupId": 99, "localDisplayName": "Team Chat"},
        },
        "chatItem": {
            "meta": {"itemId": 31, "itemStatus": {"type": "rcvNew"}},
            "content": {"type": "rcvMsgContent", "msgContent": {"type": "text", "text": "hi"}},
            "chatItemMember": {"memberId": 7, "localDisplayName": "Alice"},
        },
    })

    assert handler_mock.await_args is not None
    event = handler_mock.await_args.args[0]
    assert event.source.chat_id == "group:Team Chat"
    assert event.source.chat_name == "Team Chat"


# ---------------------------------------------------------------------------
# 9. Standalone (out-of-process) send for cron
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_standalone_send_missing_websockets(monkeypatch):
    """When websockets is unimportable, return a clean error dict.

    Implementation detail: the standalone path does ``import websockets``
    inside the function body. We simulate the package being absent by
    pulling it out of ``sys.modules`` and pointing the finder at None.
    """
    import sys
    saved_websockets = sys.modules.pop("websockets", None)
    saved_meta = list(sys.meta_path)

    class _Blocker:
        @staticmethod
        def find_spec(name, path=None, target=None):
            if name == "websockets" or name.startswith("websockets."):
                raise ImportError("websockets blocked for test")
            return None

    sys.meta_path.insert(0, _Blocker())
    try:
        pconfig = MagicMock()
        pconfig.extra = {"ws_url": "ws://localhost:5225"}
        result = await _standalone_send(pconfig, "contact-42", "hi")
        assert isinstance(result, dict)
        assert "error" in result
        assert "websockets" in result["error"]
    finally:
        sys.meta_path[:] = saved_meta
        if saved_websockets is not None:
            sys.modules["websockets"] = saved_websockets


@pytest.mark.asyncio
async def test_standalone_send_missing_url(monkeypatch):
    monkeypatch.delenv("SIMPLEX_WS_URL", raising=False)
    pconfig = MagicMock()
    pconfig.extra = {}
    # We expect the URL fallback (extra+env both empty) to be empty string,
    # producing an error. We also need websockets to be importable for the
    # url-check branch to be reached, so skip when it's not.
    try:
        import websockets.client  # noqa: F401
    except ImportError:
        pytest.skip("websockets not installed")

    result = await _standalone_send(pconfig, "contact-42", "hi")
    assert isinstance(result, dict)
    # Either error about URL or a connection attempt failure — both are valid
    # signals that the standalone path requires configuration.
    assert "error" in result


# ---------------------------------------------------------------------------
# 10. register() — plugin-side metadata
# ---------------------------------------------------------------------------

def test_register_calls_register_platform():
    ctx = MagicMock()
    register(ctx)
    ctx.register_platform.assert_called_once()
    kwargs = ctx.register_platform.call_args.kwargs
    assert kwargs["name"] == "simplex"
    assert kwargs["label"] == "SimpleX Chat"
    assert kwargs["required_env"] == ["SIMPLEX_WS_URL"]
    assert kwargs["allowed_users_env"] == "SIMPLEX_ALLOWED_USERS"
    assert kwargs["allow_all_env"] == "SIMPLEX_ALLOW_ALL_USERS"
    assert kwargs["cron_deliver_env_var"] == "SIMPLEX_HOME_CHANNEL"
    assert callable(kwargs["check_fn"])
    assert callable(kwargs["validate_config"])
    assert callable(kwargs["is_connected"])
    assert callable(kwargs["env_enablement_fn"])
    assert callable(kwargs["standalone_sender_fn"])
    assert callable(kwargs["adapter_factory"])
    assert callable(kwargs["setup_fn"])
    # SimpleX uses opaque IDs only — no PII to redact.
    assert kwargs["pii_safe"] is True
