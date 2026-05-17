"""Tests for Feishu send_slash_confirm interactive card buttons."""

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Ensure the repo root is importable
# ---------------------------------------------------------------------------
_repo = str(Path(__file__).resolve().parents[2])
if _repo not in sys.path:
    sys.path.insert(0, _repo)


# ---------------------------------------------------------------------------
# Minimal Feishu mock so FeishuAdapter can be imported without lark-oapi
# ---------------------------------------------------------------------------
def _ensure_feishu_mocks():
    """Provide stubs for lark-oapi / aiohttp.web so the import succeeds."""
    if importlib.util.find_spec("lark_oapi") is None and "lark_oapi" not in sys.modules:
        mod = MagicMock()
        for name in (
            "lark_oapi", "lark_oapi.api.im.v1",
            "lark_oapi.event", "lark_oapi.event.callback_type",
        ):
            sys.modules.setdefault(name, mod)
    if importlib.util.find_spec("aiohttp") is None and "aiohttp" not in sys.modules:
        aio = MagicMock()
        sys.modules.setdefault("aiohttp", aio)
        sys.modules.setdefault("aiohttp.web", aio.web)


_ensure_feishu_mocks()

from gateway.config import PlatformConfig
from gateway.platforms.feishu import FeishuAdapter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_adapter() -> FeishuAdapter:
    """Create a FeishuAdapter with mocked internals."""
    config = PlatformConfig(enabled=True)
    adapter = FeishuAdapter(config)
    adapter._client = MagicMock()
    return adapter


def _make_card_action_data(
    action_value: dict,
    chat_id: str = "oc_12345",
    open_id: str = "ou_user1",
    token: str = "tok_abc",
) -> SimpleNamespace:
    """Create a mock Feishu card action callback data object."""
    return SimpleNamespace(
        event=SimpleNamespace(
            token=token,
            context=SimpleNamespace(open_chat_id=chat_id),
            operator=SimpleNamespace(open_id=open_id),
            action=SimpleNamespace(
                tag="button",
                value=action_value,
            ),
        ),
    )


# ===========================================================================
# send_slash_confirm — interactive card with buttons
# ===========================================================================

class TestFeishuSlashConfirmSend:
    """Test send_slash_confirm sends an interactive card with three buttons."""

    @pytest.mark.asyncio
    async def test_sends_interactive_card(self):
        adapter = _make_adapter()

        mock_response = SimpleNamespace(
            success=lambda: True,
            data=SimpleNamespace(message_id="msg_sc001"),
        )
        with patch.object(
            adapter, "_feishu_send_with_retry", new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_send:
            result = await adapter.send_slash_confirm(
                chat_id="oc_12345",
                title="Confirm /reload-mcp",
                message="This will invalidate the provider prompt cache.",
                session_key="agent:main:feishu:group:oc_12345",
                confirm_id="42",
            )

        assert result.success is True
        assert result.message_id == "msg_sc001"

        mock_send.assert_called_once()
        kwargs = mock_send.call_args[1]
        assert kwargs["chat_id"] == "oc_12345"
        assert kwargs["msg_type"] == "interactive"

        # Verify card payload
        card = json.loads(kwargs["payload"])
        assert card["header"]["template"] == "blue"
        assert "invalidate the provider prompt cache" in card["elements"][0]["content"]

        # Check buttons
        actions = card["elements"][1]["actions"]
        assert len(actions) == 3
        action_keys = [a["value"]["hermes_slash_confirm_action"] for a in actions]
        assert action_keys == ["sc_once", "sc_always", "sc_cancel"]
        # All buttons carry the same confirm_id
        confirm_ids = [a["value"]["confirm_id"] for a in actions]
        assert all(cid == "42" for cid in confirm_ids)

    @pytest.mark.asyncio
    async def test_stores_slash_confirm_state(self):
        adapter = _make_adapter()

        mock_response = SimpleNamespace(
            success=lambda: True,
            data=SimpleNamespace(message_id="msg_sc002"),
        )
        with patch.object(
            adapter, "_feishu_send_with_retry", new_callable=AsyncMock,
            return_value=mock_response,
        ):
            await adapter.send_slash_confirm(
                chat_id="oc_999",
                title="Confirm",
                message="Please confirm.",
                session_key="my-session-key",
                confirm_id="99",
            )

        assert adapter._slash_confirm_state.get("99") == "my-session-key"

    @pytest.mark.asyncio
    async def test_not_connected(self):
        adapter = _make_adapter()
        adapter._client = None
        result = await adapter.send_slash_confirm(
            chat_id="oc_12345",
            title="Confirm",
            message="msg",
            session_key="sk",
            confirm_id="1",
        )
        assert result.success is False

    @pytest.mark.asyncio
    async def test_send_failure_returns_error(self):
        adapter = _make_adapter()
        with patch.object(
            adapter, "_feishu_send_with_retry", new_callable=AsyncMock,
            side_effect=RuntimeError("send failed"),
        ):
            result = await adapter.send_slash_confirm(
                chat_id="oc_12345",
                title="T",
                message="m",
                session_key="sk",
                confirm_id="1",
            )
        assert result.success is False
        assert "send failed" in (result.error or "")


# ===========================================================================
# Card action callback routing for slash-confirm
# ===========================================================================

class TestFeishuSlashConfirmCardAction:
    """Test card action callback routing for slash-confirm buttons."""

    def test_routes_slash_confirm_action(self):
        adapter = _make_adapter()
        adapter._slash_confirm_state["42"] = "agent:main:feishu:group:oc_12345"
        adapter._loop = MagicMock()
        adapter._loop.is_closed = MagicMock(return_value=False)

        data = _make_card_action_data({
            "hermes_slash_confirm_action": "sc_once",
            "confirm_id": "42",
        })

        submitted = []

        def _fake_submit(loop, coro):
            submitted.append(coro)
            return SimpleNamespace(add_done_callback=lambda *a, **kw: None)

        with patch.object(adapter, "_submit_on_loop", side_effect=_fake_submit):
            with patch.object(adapter, "_is_interactive_operator_authorized", return_value=True):
                response = adapter._on_card_action_trigger(data)

        assert response is not None
        assert len(submitted) == 1

    def test_unauthorized_user_rejected(self):
        adapter = _make_adapter()
        adapter._slash_confirm_state["42"] = "sk"
        adapter._loop = MagicMock()
        adapter._loop.is_closed = MagicMock(return_value=False)

        data = _make_card_action_data({
            "hermes_slash_confirm_action": "sc_once",
            "confirm_id": "42",
        })

        with patch.object(adapter, "_submit_on_loop") as mock_submit:
            with patch.object(adapter, "_is_interactive_operator_authorized", return_value=False):
                response = adapter._on_card_action_trigger(data)

        # Should NOT have scheduled resolution
        mock_submit.assert_not_called()
        assert response is not None


# ===========================================================================
# _resolve_slash_confirm
# ===========================================================================

class TestFeishuSlashConfirmResolve:
    """Test _resolve_slash_confirm pops state and calls tools.slash_confirm.resolve."""

    @pytest.mark.asyncio
    async def test_resolves_via_slash_confirm_module(self):
        adapter = _make_adapter()
        adapter._slash_confirm_state["42"] = "agent:main:feishu:group:oc_12345"

        with patch(
            "tools.slash_confirm.resolve", new_callable=AsyncMock, return_value="Done",
        ) as mock_resolve:
            await adapter._resolve_slash_confirm("42", "once", "TestUser")

        mock_resolve.assert_called_once_with(
            "agent:main:feishu:group:oc_12345", "42", "once",
        )
        # State should be popped
        assert "42" not in adapter._slash_confirm_state

    @pytest.mark.asyncio
    async def test_ignores_unknown_confirm_id(self):
        adapter = _make_adapter()

        with patch(
            "tools.slash_confirm.resolve", new_callable=AsyncMock,
        ) as mock_resolve:
            await adapter._resolve_slash_confirm("nonexistent", "once", "User")

        mock_resolve.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_resolve_exception(self):
        adapter = _make_adapter()
        adapter._slash_confirm_state["42"] = "sk"

        with patch(
            "tools.slash_confirm.resolve", new_callable=AsyncMock,
            side_effect=RuntimeError("boom"),
        ):
            # Should not raise
            await adapter._resolve_slash_confirm("42", "always", "User")

        # State still popped even on error
        assert "42" not in adapter._slash_confirm_state
