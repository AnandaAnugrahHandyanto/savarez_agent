import asyncio
import json
from types import SimpleNamespace

import pytest

from tools import mixture_of_agents_tool as moa


def _choice_response(content: str):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content, reasoning=None))]
    )


def test_moa_configuration_reads_subscription_specs(monkeypatch):
    monkeypatch.setattr(
        moa,
        "load_config",
        lambda: {
            "model": {"provider": "openai-codex", "default": "gpt-5.5"},
            "moa": {
                "reference_models": [
                    {"provider": "openai-codex", "model": "gpt-5.5", "label": "codex"},
                    {"provider": "anthropic", "model": "claude-opus-4-7", "label": "claude"},
                ],
                "aggregator_model": {"provider": "openai-codex", "model": "gpt-5.5", "label": "agg"},
                "min_successful_references": 1,
            },
        },
    )

    cfg = moa.get_moa_configuration()

    assert cfg["reference_models"] == [
        {"provider": "openai-codex", "model": "gpt-5.5", "label": "codex"},
        {"provider": "anthropic", "model": "claude-opus-4-7", "label": "claude"},
    ]
    assert cfg["aggregator_model"] == {"provider": "openai-codex", "model": "gpt-5.5", "label": "agg"}


def test_moa_requirements_use_configured_provider_router_not_openrouter(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(
        moa,
        "load_config",
        lambda: {
            "model": {"provider": "openai-codex", "default": "gpt-5.5"},
            "moa": {
                "reference_models": [{"provider": "openai-codex", "model": "gpt-5.5"}],
                "aggregator_model": {"provider": "openai-codex", "model": "gpt-5.5"},
                "min_successful_references": 1,
            },
        },
    )
    calls = []

    def fake_resolve(provider, model=None, **kwargs):
        calls.append((provider, model))
        return object(), model

    monkeypatch.setattr(moa, "resolve_provider_client", fake_resolve)

    assert moa.check_moa_requirements() is True
    assert calls == [("openai-codex", "gpt-5.5"), ("openai-codex", "gpt-5.5")]


def test_moa_tool_routes_calls_through_subscription_providers(monkeypatch):
    monkeypatch.setattr(
        moa,
        "load_config",
        lambda: {
            "model": {"provider": "openai-codex", "default": "gpt-5.5"},
            "moa": {
                "reference_models": [
                    {"provider": "openai-codex", "model": "gpt-5.5", "label": "codex-ref"},
                    {"provider": "anthropic", "model": "claude-opus-4-7", "label": "claude-ref"},
                ],
                "aggregator_model": {"provider": "openai-codex", "model": "gpt-5.5", "label": "codex-agg"},
                "min_successful_references": 1,
                "max_retries": 1,
            },
        },
    )
    calls = []

    async def fake_async_call_llm(**kwargs):
        calls.append((kwargs["provider"], kwargs["model"], kwargs["messages"]))
        if len(kwargs["messages"]) == 1:
            return _choice_response(f"reference from {kwargs['provider']}")
        return _choice_response("aggregated answer")

    monkeypatch.setattr(moa, "async_call_llm", fake_async_call_llm)

    result = json.loads(asyncio.run(moa.mixture_of_agents_tool("hard question")))

    assert result["success"] is True
    assert result["response"] == "aggregated answer"
    assert [(provider, model) for provider, model, _ in calls] == [
        ("openai-codex", "gpt-5.5"),
        ("anthropic", "claude-opus-4-7"),
        ("openai-codex", "gpt-5.5"),
    ]
