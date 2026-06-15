import importlib
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

fusion = importlib.import_module("tools.openrouter_fusion_tool")


def test_budget_parameters_use_cost_controlled_panel():
    params = fusion._build_fusion_parameters(
        preset="budget",
        analysis_models=None,
        judge_model="~anthropic/claude-opus-latest",
        max_tool_calls=4,
        max_completion_tokens=1200,
        temperature=0.2,
        reasoning={"effort": "low"},
    )

    assert params["analysis_models"] == fusion.BUDGET_ANALYSIS_MODELS
    assert params["model"] == "~anthropic/claude-opus-latest"
    assert params["max_tool_calls"] == 4
    assert params["max_completion_tokens"] == 1200
    assert params["temperature"] == 0.2
    assert params["reasoning"] == {"effort": "low"}


def test_quality_preset_leaves_panel_to_openrouter_default():
    params = fusion._build_fusion_parameters(
        preset="quality",
        analysis_models=None,
        judge_model=None,
        max_tool_calls=None,
        max_completion_tokens=None,
        temperature=None,
        reasoning=None,
    )

    assert "analysis_models" not in params


def test_custom_preset_requires_analysis_models():
    with pytest.raises(ValueError, match="requires at least one"):
        fusion._build_fusion_parameters(
            preset="custom",
            analysis_models=[],
            judge_model=None,
            max_tool_calls=None,
            max_completion_tokens=None,
            temperature=None,
            reasoning=None,
        )


@pytest.mark.asyncio
async def test_openrouter_fusion_tool_sends_server_tool_payload(monkeypatch):
    create = AsyncMock(
        return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="fused answer"))],
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )
    )
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(fusion, "get_async_client", lambda: fake_client)

    result = json.loads(
        await fusion.openrouter_fusion_tool(
            "核實這個說法",
            preset="budget",
            judge_model="~anthropic/claude-opus-latest",
            outer_model="~anthropic/claude-opus-latest",
            max_tool_calls=3,
        )
    )

    assert result["success"] is True
    assert result["response"] == "fused answer"
    create.assert_awaited_once()
    await_args = create.await_args
    assert await_args is not None
    kwargs = await_args.kwargs
    assert kwargs["model"] == "~anthropic/claude-opus-latest"
    assert kwargs["messages"] == [{"role": "user", "content": "核實這個說法"}]
    assert kwargs["tool_choice"] == "required"
    assert kwargs["tools"] == [
        {
            "type": "openrouter:fusion",
            "parameters": {
                "analysis_models": fusion.BUDGET_ANALYSIS_MODELS,
                "model": "~anthropic/claude-opus-latest",
                "max_tool_calls": 3,
            },
        }
    ]
    assert result["usage"] == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}


def test_tool_is_registered_under_fusion_toolset():
    entry = fusion.registry.get_entry("openrouter_fusion")

    assert entry is not None
    assert entry.toolset == "fusion"
    assert entry.is_async is True
    assert entry.schema["name"] == "openrouter_fusion"
