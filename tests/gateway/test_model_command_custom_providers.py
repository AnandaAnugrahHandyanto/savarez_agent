"""Regression tests for gateway /model support of config.yaml custom_providers."""

import yaml
import pytest

from hermes_cli.model_switch import ModelSwitchResult
from gateway.config import Platform
from gateway.platforms.base import MessageEvent, MessageType
from gateway.run import GatewayRunner
from gateway.session import SessionSource


def _make_runner():
    runner = object.__new__(GatewayRunner)
    runner.adapters = {}
    runner._voice_mode = {}
    runner._session_model_overrides = {}
    runner._session_key_for_source = lambda source: f"{source.platform.value}:{source.chat_id}"
    runner._evict_cached_agent = lambda session_key: None
    return runner


def _make_event(text="/model"):
    return MessageEvent(
        text=text,
        message_type=MessageType.TEXT,
        source=SessionSource(platform=Platform.TELEGRAM, chat_id="12345", chat_type="dm"),
    )


@pytest.mark.asyncio
async def test_handle_model_command_lists_saved_custom_provider(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    (hermes_home / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "model": {
                    "default": "gpt-5.4",
                    "provider": "openai-codex",
                    "base_url": "https://chatgpt.com/backend-api/codex",
                },
                "providers": {},
                "custom_providers": [
                    {
                        "name": "Local (127.0.0.1:4141)",
                        "base_url": "http://127.0.0.1:4141/v1",
                        "model": "rotator-openrouter-coding",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    import gateway.run as gateway_run

    monkeypatch.setattr(gateway_run, "_hermes_home", hermes_home)
    monkeypatch.setattr("agent.models_dev.fetch_models_dev", lambda: {})

    result = await _make_runner()._handle_model_command(_make_event())

    assert result is not None
    assert "Local (127.0.0.1:4141)" in result
    assert "custom:local-(127.0.0.1:4141)" in result
    assert "rotator-openrouter-coding" in result


@pytest.mark.asyncio
async def test_handle_model_command_prefers_display_context_length_for_custom_provider_switch(
    tmp_path,
    monkeypatch,
):
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    (hermes_home / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "model": {
                    "default": "glm-5",
                    "provider": "openrouter",
                    "base_url": "https://openrouter.ai/api/v1",
                },
                "providers": {},
                "custom_providers": [
                    {
                        "name": "yunfeiplus",
                        "base_url": "https://api.yunfeiplus.com/v1",
                        "models": {
                            "gpt-5.4": {"context_length": 524288},
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    import gateway.run as gateway_run
    import hermes_cli.model_switch as model_switch

    monkeypatch.setattr(gateway_run, "_hermes_home", hermes_home)
    monkeypatch.setattr("agent.models_dev.fetch_models_dev", lambda: {})
    monkeypatch.setattr(
        model_switch,
        "switch_model",
        lambda **_: ModelSwitchResult(
            success=True,
            new_model="gpt-5.4",
            target_provider="custom:yunfeiplus",
            provider_changed=True,
            api_key="***",
            base_url="https://api.yunfeiplus.com/v1",
            api_mode="chat_completions",
            provider_label="yunfeiplus",
            display_context_length=524288,
            model_info=None,
        ),
    )

    result = await _make_runner()._handle_model_command(
        _make_event("/model gpt-5.4 --provider yunfeiplus")
    )

    assert result is not None
    assert "Model switched to `gpt-5.4`" in result
    assert "Provider: yunfeiplus" in result
    assert "Context: 524,288 tokens" in result


def test_format_session_info_prefers_custom_provider_context_override(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    (hermes_home / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "model": {
                    "default": "gpt-5.4",
                    "provider": "openrouter",
                    "base_url": "https://openrouter.ai/api/v1",
                    "context_length": 200000,
                },
                "custom_providers": [
                    {
                        "name": "yunfeiplus",
                        "base_url": "https://api.yunfeiplus.com/v1",
                        "models": {
                            "gpt-5.4": {"context_length": 524288},
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    import gateway.run as gateway_run

    monkeypatch.setattr(gateway_run, "_hermes_home", hermes_home)
    monkeypatch.setattr(gateway_run, "_resolve_gateway_model", lambda config=None: "gpt-5.4")
    monkeypatch.setattr(
        gateway_run,
        "_resolve_runtime_agent_kwargs",
        lambda: {
            "provider": "custom:yunfeiplus",
            "base_url": "https://api.yunfeiplus.com/v1",
            "api_key": "***",
        },
    )

    result = _make_runner()._format_session_info()

    assert "◆ Model: `gpt-5.4`" in result
    assert "◆ Provider: custom:yunfeiplus" in result
    assert "◆ Context: 524K tokens (config)" in result


@pytest.mark.asyncio
async def test_handle_model_command_ignores_boolean_context_length_in_config(
    tmp_path,
    monkeypatch,
):
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    (hermes_home / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "model": {
                    "default": "gpt-5.4",
                    "provider": "openrouter",
                    "base_url": "https://openrouter.ai/api/v1",
                    "context_length": True,
                },
                "providers": {},
                "custom_providers": [],
            }
        ),
        encoding="utf-8",
    )

    import gateway.run as gateway_run
    import hermes_cli.model_switch as model_switch

    captured = {}

    def _fake_switch_model(**kwargs):
        captured.update(kwargs)
        return ModelSwitchResult(
            success=True,
            new_model="gpt-5.4",
            target_provider="openrouter",
            provider_changed=False,
            api_key="***",
            base_url="https://openrouter.ai/api/v1",
            api_mode="chat_completions",
            provider_label="OpenRouter",
            display_context_length=128000,
            model_info=None,
        )

    monkeypatch.setattr(gateway_run, "_hermes_home", hermes_home)
    monkeypatch.setattr("agent.models_dev.fetch_models_dev", lambda: {})
    monkeypatch.setattr(model_switch, "switch_model", _fake_switch_model)

    result = await _make_runner()._handle_model_command(_make_event("/model gpt-5.4"))

    assert result is not None
    assert captured["config_context_length"] is None
    assert "Context: 128,000 tokens" in result
