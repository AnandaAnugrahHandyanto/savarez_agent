"""Regression tests for gateway /model --global persistence."""
from types import SimpleNamespace

import pytest
import yaml

from gateway.config import Platform
from hermes_cli.model_switch import ModelSwitchResult


@pytest.mark.asyncio
async def test_gateway_model_global_persists_complete_runtime_state(monkeypatch, tmp_path):
    """Regression for #25107: gateway /model --global persists api_mode too."""
    from gateway import run as gateway_run

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump({
        "model": {
            "default": "old-model",
            "provider": "openrouter",
            "base_url": "https://openrouter.ai/api/v1",
        }
    }))
    saved = {}

    runner = object.__new__(gateway_run.GatewayRunner)
    runner.adapters = {}
    runner._session_model_overrides = {}
    runner._pending_model_notes = {}
    runner._agent_cache_lock = None
    runner._agent_cache = {}
    runner._session_key_for_source = lambda source: "telegram:u1:c1"
    runner._evict_cached_agent = lambda session_key: None

    event = SimpleNamespace(
        source=SimpleNamespace(platform=Platform.TELEGRAM, chat_id="c1"),
        get_command_args=lambda: "kimi-k2.6 --global --provider kimi-coding",
    )
    result = ModelSwitchResult(
        success=True,
        new_model="kimi-k2.6",
        target_provider="kimi-coding",
        provider_changed=True,
        api_key="sk-kimi-test",
        base_url="https://api.kimi.com/coding",
        api_mode="anthropic_messages",
        warning_message="",
        provider_label="Kimi Coding",
        capabilities=None,
        model_info=None,
        is_global=True,
    )

    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)
    monkeypatch.setattr("hermes_cli.model_switch.switch_model", lambda **kwargs: result)
    monkeypatch.setattr("hermes_cli.model_switch.resolve_display_context_length", lambda *a, **k: None)
    monkeypatch.setattr("hermes_cli.config.save_config", lambda cfg: saved.update(cfg))

    response = await runner._handle_model_command(event)

    assert "Saved" in response or "saved" in response
    assert saved["model"]["default"] == "kimi-k2.6"
    assert saved["model"]["provider"] == "kimi-coding"
    assert saved["model"]["base_url"] == "https://api.kimi.com/coding"
    assert saved["model"]["api_mode"] == "anthropic_messages"


@pytest.mark.asyncio
async def test_gateway_model_global_clears_stale_runtime_fields(monkeypatch, tmp_path):
    """Regression for #25107: stale base_url/api_mode must not survive switches."""
    from gateway import run as gateway_run

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump({
        "model": {
            "default": "old-model",
            "provider": "custom",
            "base_url": "https://stale.example/v1",
            "api_mode": "anthropic_messages",
        }
    }))
    saved = {}

    runner = object.__new__(gateway_run.GatewayRunner)
    runner.adapters = {}
    runner._session_model_overrides = {}
    runner._pending_model_notes = {}
    runner._agent_cache_lock = None
    runner._agent_cache = {}
    runner._session_key_for_source = lambda source: "telegram:u1:c1"
    runner._evict_cached_agent = lambda session_key: None

    event = SimpleNamespace(
        source=SimpleNamespace(platform=Platform.TELEGRAM, chat_id="c1"),
        get_command_args=lambda: "gpt-5.5 --global --provider openai-codex",
    )
    result = ModelSwitchResult(
        success=True,
        new_model="gpt-5.5",
        target_provider="openai-codex",
        provider_changed=True,
        api_key="",
        base_url="",
        api_mode="",
        warning_message="",
        provider_label="Codex",
        capabilities=None,
        model_info=None,
        is_global=True,
    )

    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)
    monkeypatch.setattr("hermes_cli.model_switch.switch_model", lambda **kwargs: result)
    monkeypatch.setattr("hermes_cli.model_switch.resolve_display_context_length", lambda *a, **k: None)
    monkeypatch.setattr("hermes_cli.config.save_config", lambda cfg: saved.update(cfg))

    await runner._handle_model_command(event)

    assert saved["model"]["default"] == "gpt-5.5"
    assert saved["model"]["provider"] == "openai-codex"
    assert "base_url" not in saved["model"]
    assert "api_mode" not in saved["model"]
