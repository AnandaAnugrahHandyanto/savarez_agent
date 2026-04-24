"""Tests for Feishu interactive clarify/choice cards."""

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _ensure_feishu_mocks():
    """Provide stubs for lark-oapi / aiohttp.web so the import succeeds."""
    if importlib.util.find_spec("lark_oapi") is None and "lark_oapi" not in sys.modules:
        for name in (
            "lark_oapi", "lark_oapi.api.im.v1",
            "lark_oapi.event", "lark_oapi.event.callback_type",
        ):
            mod = MagicMock()
            mod.__spec__ = importlib.machinery.ModuleSpec(name, loader=None)
            sys.modules.setdefault(name, mod)
    if importlib.util.find_spec("aiohttp") is None and "aiohttp" not in sys.modules:
        aio = MagicMock()
        aio.__spec__ = importlib.machinery.ModuleSpec("aiohttp", loader=None)
        sys.modules.setdefault("aiohttp", aio)
        sys.modules.setdefault("aiohttp.web", aio.web)


_repo = str(Path(__file__).resolve().parents[2])
if _repo not in sys.path:
    sys.path.insert(0, _repo)

_ensure_feishu_mocks()

from gateway.config import PlatformConfig
import gateway.platforms.feishu as feishu_module
from gateway.platforms.feishu import FeishuAdapter


def _make_adapter() -> FeishuAdapter:
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


def _close_submitted_coro(coro, _loop):
    coro.close()
    return SimpleNamespace(add_done_callback=lambda *_args, **_kwargs: None)


class _FakeCallBackCard:
    def __init__(self):
        self.type = None
        self.data = None


class _FakeP2Response:
    def __init__(self):
        self.card = None


@pytest.fixture(autouse=False)
def _patch_callback_card_types(monkeypatch):
    monkeypatch.setattr(feishu_module, "P2CardActionTriggerResponse", _FakeP2Response)
    monkeypatch.setattr(feishu_module, "CallBackCard", _FakeCallBackCard)


class TestFeishuClarifyCard:
    @pytest.mark.asyncio
    async def test_sends_interactive_clarify_card(self):
        adapter = _make_adapter()
        mock_response = SimpleNamespace(
            success=lambda: True,
            data=SimpleNamespace(message_id="msg_101"),
        )

        with patch.object(
            adapter,
            "_feishu_send_with_retry",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_send:
            result = await adapter.send_clarify_card(
                chat_id="oc_12345",
                question="Which plan should I draft?",
                choices=["Fast path", "Safe path"],
                session_key="agent:main:feishu:group:oc_12345",
                clarify_id=77,
            )

        assert result.success is True
        assert result.message_id == "msg_101"
        kwargs = mock_send.call_args[1]
        assert kwargs["msg_type"] == "interactive"

        card = json.loads(kwargs["payload"])
        assert card["header"]["title"]["content"] == "❓ 请先确认"
        assert "如果你想自己输入答案" in card["elements"][2]["content"]
        actions = card["elements"][1]["actions"]
        assert [item["value"]["choice"] for item in actions] == ["Fast path", "Safe path"]
        assert all(item["value"]["clarify_id"] == 77 for item in actions)

    @pytest.mark.asyncio
    async def test_stores_clarify_state_after_send(self):
        adapter = _make_adapter()
        mock_response = SimpleNamespace(
            success=lambda: True,
            data=SimpleNamespace(message_id="msg_102"),
        )

        with patch.object(
            adapter,
            "_feishu_send_with_retry",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            await adapter.send_clarify_card(
                chat_id="oc_12345",
                question="Choose",
                choices=["A", "B"],
                session_key="sess-clarify",
                clarify_id=88,
            )

        assert adapter._clarify_state[88]["session_key"] == "sess-clarify"
        assert adapter._clarify_state[88]["message_id"] == "msg_102"

    @pytest.mark.asyncio
    async def test_resolve_clarify_calls_gateway_resolver(self):
        adapter = _make_adapter()
        adapter._clarify_state[99] = {
            "session_key": "sess-99",
            "message_id": "msg_99",
            "chat_id": "oc_99",
            "question": "Pick one",
        }
        adapter.resume_typing_for_chat = MagicMock()

        with patch("tools.clarify_state.resolve_gateway_clarify", return_value=1) as mock_resolve:
            await adapter._resolve_clarify(99, "Safe path", "Alice")

        mock_resolve.assert_called_once_with("sess-99", "Safe path", clarify_id=99)
        adapter.resume_typing_for_chat.assert_called_once_with("oc_99")
        assert 99 not in adapter._clarify_state

    def test_returns_card_for_clarify_action(self, _patch_callback_card_types):
        adapter = _make_adapter()
        adapter._loop = MagicMock()
        adapter._loop.is_closed = MagicMock(return_value=False)
        adapter._clarify_state[66] = {
            "session_key": "sess-66",
            "message_id": "msg_66",
            "chat_id": "oc_66",
            "question": "Which plan should I draft?",
        }
        adapter._sender_name_cache["ou_bob"] = ("Bob", 9999999999)
        data = _make_card_action_data(
            {"hermes_action": "clarify_choice", "clarify_id": 66, "choice": "Safe path"},
            open_id="ou_bob",
        )

        with patch("asyncio.run_coroutine_threadsafe", side_effect=_close_submitted_coro):
            response = adapter._on_card_action_trigger(data)

        assert response.card is not None
        assert response.card.type == "raw"
        card = response.card.data
        assert card["header"]["title"]["content"] == "✅ 已完成选择"
        assert "**问题：**" in card["elements"][0]["content"]
        assert "**选择：** Safe path" in card["elements"][0]["content"]
        assert "**选择人：** Bob" in card["elements"][0]["content"]
