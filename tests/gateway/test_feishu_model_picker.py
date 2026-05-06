"""Tests for the Feishu /model interactive card picker.

Covers card builders and the synchronous _handle_model_picker_card_action
dispatch that drives the two-layer provider→model drill-down.
"""

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from gateway.platforms.feishu import FeishuAdapter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dummy_providers():
    return [
        {
            "slug": "openrouter",
            "name": "OpenRouter",
            "models": ["openai/gpt-5.4", "anthropic/claude-sonnet-4",
                       "google/gemini-2.5-pro", "meta-llama/llama-4",
                       "deepseek/deepseek-chat", "qwen/qwen3-235b"],
            "total_models": 6,
            "is_current": True,
        },
        {
            "slug": "copilot",
            "name": "GitHub Copilot",
            "models": ["gpt-5.4"],
            "total_models": 1,
            "is_current": False,
        },
    ]


def _skeleton_adapter(**kw) -> FeishuAdapter:
    """Return a bare FeishuAdapter with the attrs our picker needs."""
    adapter = object.__new__(FeishuAdapter)
    adapter._client = object()  # truthy so send_model_picker passes guard
    adapter._model_picker_state = {}
    adapter._MODEL_PAGE_SIZE = 6
    # minimal attrs for _feishu_send_with_retry / _finalize_send_result
    adapter._loop = Mock()
    adapter._loop_accepts_callbacks = Mock(return_value=True)
    adapter._submit_on_loop = Mock()
    adapter._card_action_tokens = {}
    adapter._app_id = "test-app"
    adapter.edit_message = AsyncMock()
    for k, v in kw.items():
        setattr(adapter, k, v)
    return adapter


# ---------------------------------------------------------------------------
# Card-builder tests
# ---------------------------------------------------------------------------

class TestProviderCard:
    def test_provider_card_structure(self):
        adapter = _skeleton_adapter()
        card = adapter._build_model_picker_provider_card(
            _dummy_providers(), "openai/gpt-5.4", "openrouter"
        )
        assert card["config"]["wide_screen_mode"] is True
        assert card["header"]["title"]["content"] == "⚙️ 模型設定"

        # At least one markdown + one action element
        tags = [e["tag"] for e in card["elements"]]
        assert "markdown" in tags
        assert "action" in tags

        # All buttons carry mp:<slug>
        for el in card["elements"]:
            if el["tag"] != "action":
                continue
            for btn in el["actions"]:
                val = btn["value"]["hermes_action"]
                assert val.startswith("mp:"), f"unexpected action {val}"

    def test_provider_card_marks_current(self):
        adapter = _skeleton_adapter()
        card = adapter._build_model_picker_provider_card(
            _dummy_providers(), "openai/gpt-5.4", "openrouter"
        )
        all_btn_texts = []
        for el in card["elements"]:
            if el["tag"] == "action":
                for btn in el["actions"]:
                    all_btn_texts.append(btn["text"]["content"])
        current_labels = [t for t in all_btn_texts if t.startswith("✓")]
        assert len(current_labels) == 1  # only openrouter


class TestModelCard:
    def test_model_card_structure(self):
        adapter = _skeleton_adapter()
        models = ["openai/gpt-5.4", "anthropic/claude-sonnet-4",
                  "google/gemini-2.5-pro", "meta-llama/llama-4"]
        card = adapter._build_model_picker_model_card("OpenRouter", models, 0)
        assert card["header"]["title"]["content"] == "⚙️ 模型設定"

        # Model buttons carry mm:<idx>
        mm_actions = []
        for el in card["elements"]:
            if el["tag"] != "action":
                continue
            for btn in el["actions"]:
                val = btn["value"]["hermes_action"]
                if val.startswith("mm:"):
                    mm_actions.append(val)
        assert len(mm_actions) == len(models)

    def test_model_card_no_pagination_when_few_models(self):
        adapter = _skeleton_adapter()
        models = ["a", "b"]
        card = adapter._build_model_picker_model_card("X", models, 0)
        nav_buttons = []
        for el in card["elements"]:
            if el["tag"] == "action":
                for btn in el["actions"]:
                    v = btn["value"]["hermes_action"]
                    if v.startswith("mg:") or v == "mx:noop":
                        nav_buttons.append(v)
        # 2 models fit on one page → no prev/next, only page counter + back + cancel
        page_counters = [v for v in nav_buttons if v == "mx:noop"]
        assert len(page_counters) == 1

    def test_model_card_has_back_and_cancel(self):
        adapter = _skeleton_adapter()
        card = adapter._build_model_picker_model_card("X", ["m1", "m2"], 0)
        bottom_actions = []
        for el in card["elements"]:
            if el["tag"] == "action":
                for btn in el["actions"]:
                    v = btn["value"]["hermes_action"]
                    if v in ("mb", "mx"):
                        bottom_actions.append(v)
        assert "mb" in bottom_actions
        assert "mx" in bottom_actions

    def test_model_card_pagination(self):
        """With 7 models and page_size=2, page 0 should show prev disabled, next enabled."""
        adapter = _skeleton_adapter()
        adapter._MODEL_PAGE_SIZE = 2
        models = [f"model-{i}" for i in range(7)]
        card = adapter._build_model_picker_model_card("P", models, 0)
        nav = []
        for el in card["elements"]:
            if el["tag"] == "action":
                for btn in el["actions"]:
                    v = btn["value"]["hermes_action"]
                    if v.startswith("mg:") or v == "mx:noop":
                        nav.append(v)
        # page 0 / 4 → no prev button, has next
        assert not any(v.startswith("mg:0") for v in nav if v != "mx:noop")
        has_next = any("mg:1" in v for v in nav)
        assert has_next


# ---------------------------------------------------------------------------
# Card-action dispatch tests
# ---------------------------------------------------------------------------

def _make_event(chat_id="oc_test", hermes_action="mp:openrouter"):
    return SimpleNamespace(
        context=SimpleNamespace(open_chat_id=chat_id),
        action=SimpleNamespace(
            tag="button",
            value={"hermes_action": hermes_action},
        ),
    )


class TestCardActionDispatch:
    """Synchronous dispatch (_handle_model_picker_card_action)."""

    def test_provider_selection_switches_to_model_list(self):
        adapter = _skeleton_adapter()
        adapter._model_picker_state["oc_test"] = {
            "providers": _dummy_providers(),
            "current_model": "a", "current_provider": "p",
            "msg_id": "m1",
        }
        event = _make_event(hermes_action="mp:openrouter")
        resp = adapter._handle_model_picker_card_action(
            event=event, action_value={"hermes_action": "mp:openrouter"},
            hermes_action="mp:openrouter", loop=Mock(),
        )
        assert resp is not None
        card = resp.card.data
        assert "OpenRouter" in card["elements"][0]["content"]
        # state updated
        st = adapter._model_picker_state["oc_test"]
        assert st["selected_provider"] == "openrouter"
        assert st["model_page"] == 0

    def test_page_navigation(self):
        adapter = _skeleton_adapter()
        adapter._MODEL_PAGE_SIZE = 2
        models = [f"m{i}" for i in range(5)]
        adapter._model_picker_state["oc_test"] = {
            "providers": _dummy_providers(),
            "model_list": models,
            "model_page": 0,
            "selected_provider": "x",
            "selected_provider_name": "X",
            "current_model": "a", "current_provider": "p",
        }
        event = _make_event(hermes_action="mg:1")
        resp = adapter._handle_model_picker_card_action(
            event=event, action_value={}, hermes_action="mg:1", loop=Mock(),
        )
        assert resp is not None
        card = resp.card.data
        # should show page 1/3
        md = card["elements"][0]["content"]
        assert "3–4" in md or "3–4" in md  # items 3-4 of 5
        assert adapter._model_picker_state["oc_test"]["model_page"] == 1

    def test_back_to_provider_list(self):
        adapter = _skeleton_adapter()
        adapter._model_picker_state["oc_test"] = {
            "providers": _dummy_providers(),
            "model_list": ["m1"],
            "model_page": 0,
            "selected_provider": "x",
            "current_model": "a", "current_provider": "p",
        }
        event = _make_event(hermes_action="mb")
        resp = adapter._handle_model_picker_card_action(
            event=event, action_value={}, hermes_action="mb", loop=Mock(),
        )
        assert resp is not None
        card = resp.card.data
        md = card["elements"][0]["content"]
        assert "Provider" in md

    def test_model_selected_schedules_async_and_returns_processing_card(self):
        adapter = _skeleton_adapter()
        adapter._submit_on_loop = Mock()
        adapter._model_picker_state["oc_test"] = {
            "providers": _dummy_providers(),
            "model_list": ["openai/gpt-5.4"],
            "model_page": 0,
            "selected_provider": "openrouter",
            "selected_provider_name": "OpenRouter",
            "current_model": "a", "current_provider": "p",
            "msg_id": "m1",
        }
        event = _make_event(hermes_action="mm:0")
        resp = adapter._handle_model_picker_card_action(
            event=event, action_value={}, hermes_action="mm:0", loop=Mock(),
        )
        assert resp is not None
        card = resp.card.data
        assert "正在切換" in card["elements"][0]["content"]
        # Verify async work was scheduled
        adapter._submit_on_loop.assert_called_once()

    def test_cancel_schedules_cleanup_and_returns_cancel_card(self):
        adapter = _skeleton_adapter()
        adapter._submit_on_loop = Mock()
        adapter._model_picker_state["oc_test"] = {
            "providers": _dummy_providers(),
            "current_model": "a", "current_provider": "p",
        }
        event = _make_event(hermes_action="mx")
        resp = adapter._handle_model_picker_card_action(
            event=event, action_value={}, hermes_action="mx", loop=Mock(),
        )
        assert resp is not None
        card = resp.card.data
        assert "已取消" in card["elements"][0]["content"]
        adapter._submit_on_loop.assert_called_once()

    def test_expired_state_returns_expired_card(self):
        adapter = _skeleton_adapter()
        # no state for this chat_id
        event = _make_event(hermes_action="mp:openrouter")
        resp = adapter._handle_model_picker_card_action(
            event=event, action_value={}, hermes_action="mp:openrouter", loop=Mock(),
        )
        assert resp is not None
        card = resp.card.data
        assert "過期" in card["elements"][0]["content"]
