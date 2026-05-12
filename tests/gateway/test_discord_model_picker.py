"""Regression tests for the Discord /model picker.

Uses the shared discord mock from tests/gateway/conftest.py (installed
at collection time via _ensure_discord_mock()). Previously this file
installed its own mock at module-import time and clobbered sys.modules,
breaking other gateway tests under pytest-xdist.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from gateway.platforms.discord import ModelPickerView


def _make_view(models: list[str], *, allowed_user_ids: set[int] | None = None) -> ModelPickerView:
    view = ModelPickerView(
        providers=[
            {
                "slug": "ollama-cloud",
                "name": "Ollama Cloud",
                "models": models,
                "total_models": len(models),
                "is_current": False,
            }
        ],
        current_model="gpt-5.5",
        current_provider="openai-codex",
        session_key="session-1",
        on_model_selected=AsyncMock(return_value="Model switched"),
        allowed_user_ids=allowed_user_ids or set(),
    )
    view._selected_provider = "ollama-cloud"
    return view


def _child(view: ModelPickerView, custom_id: str):
    return next(
        child for child in view.children
        if getattr(child, "custom_id", "") == custom_id
    )


def _model_values(view: ModelPickerView) -> list[str]:
    return [option.value for option in _child(view, "model_model_select").options]


def _page_interaction(user_id: int = 123) -> SimpleNamespace:
    return SimpleNamespace(
        user=SimpleNamespace(id=user_id),
        response=SimpleNamespace(
            send_message=AsyncMock(),
            edit_message=AsyncMock(),
        ),
    )


@pytest.mark.asyncio
async def test_model_picker_clears_controls_before_running_switch_callback():
    events: list[object] = []

    async def on_model_selected(chat_id: str, model_id: str, provider_slug: str) -> str:
        events.append(("switch", chat_id, model_id, provider_slug))
        return "Model switched"

    async def edit_message(**kwargs):
        events.append(
            (
                "initial-edit",
                kwargs["embed"].title,
                kwargs["embed"].description,
                kwargs["view"],
            )
        )

    async def edit_original_response(**kwargs):
        events.append((
            "final-edit",
            kwargs["embed"].title,
            kwargs["embed"].description,
            kwargs["view"],
        ))

    view = ModelPickerView(
        providers=[
            {
                "slug": "copilot",
                "name": "GitHub Copilot",
                "models": ["gpt-5.4"],
                "total_models": 1,
                "is_current": True,
            }
        ],
        current_model="gpt-5-mini",
        current_provider="copilot",
        session_key="session-1",
        on_model_selected=on_model_selected,
        allowed_user_ids=set(),
    )
    view._selected_provider = "copilot"

    interaction = SimpleNamespace(
        user=SimpleNamespace(id=123),
        channel_id=456,
        data={"values": ["gpt-5.4"]},
        response=SimpleNamespace(
            defer=AsyncMock(),
            send_message=AsyncMock(),
            edit_message=AsyncMock(side_effect=edit_message),
        ),
        edit_original_response=AsyncMock(side_effect=edit_original_response),
    )

    await view._on_model_selected(interaction)

    assert events == [
        ("initial-edit", "⚙ Switching Model", "Switching to `gpt-5.4`...", None),
        ("switch", "456", "gpt-5.4", "copilot"),
        ("final-edit", "⚙ Model Switched", "Model switched", None),
    ]
    interaction.response.edit_message.assert_awaited_once()
    interaction.response.defer.assert_not_called()
    interaction.edit_original_response.assert_awaited_once()


@pytest.mark.asyncio
async def test_model_picker_paginates_provider_models_past_discord_select_limit():
    """Models after Discord's 25-option select cap must still be reachable."""
    models = [f"model-{i:02d}" for i in range(1, 33)] + ["kimi-k2.6"]
    view = _make_view(models)

    view._build_model_select("ollama-cloud")

    assert _model_values(view) == models[:25]
    next_button = _child(view, "model_next")
    assert next_button.disabled is False

    interaction = _page_interaction()
    await next_button.callback(interaction)

    assert _model_values(view) == models[25:]
    assert "kimi-k2.6" in _model_values(view)
    interaction.response.edit_message.assert_awaited_once()


def test_model_picker_omits_pagination_controls_at_discord_select_limit():
    models = [f"model-{i:02d}" for i in range(1, 26)]
    view = _make_view(models)

    view._build_model_select("ollama-cloud")

    assert _model_values(view) == models
    custom_ids = {getattr(child, "custom_id", "") for child in view.children}
    assert "model_prev" not in custom_ids
    assert "model_next" not in custom_ids


def test_model_picker_clamps_out_of_range_model_page():
    models = [f"model-{i:02d}" for i in range(1, 54)]
    view = _make_view(models)

    view._build_model_select("ollama-cloud", page=999)

    assert view._model_page == 2
    assert _model_values(view) == models[50:]
    assert _child(view, "model_prev").disabled is False
    assert _child(view, "model_next").disabled is True


@pytest.mark.asyncio
async def test_model_picker_rejects_unauthorized_model_page_turn():
    models = [f"model-{i:02d}" for i in range(1, 28)]
    view = _make_view(models, allowed_user_ids={999})
    view._build_model_select("ollama-cloud")

    interaction = _page_interaction(user_id=123)
    await _child(view, "model_next").callback(interaction)

    interaction.response.send_message.assert_awaited_once_with(
        "You're not authorized~", ephemeral=True
    )
    interaction.response.edit_message.assert_not_called()
    assert _model_values(view) == models[:25]
