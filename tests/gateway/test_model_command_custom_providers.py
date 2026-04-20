"""Regression tests for gateway /model support of config.yaml custom_providers."""

import yaml
import pytest
from unittest.mock import patch

from gateway.config import Platform
from gateway.platforms.base import MessageEvent, MessageType
from gateway.run import GatewayRunner
from gateway.session import SessionSource
from hermes_cli.model_switch import ModelSwitchResult


def _make_runner():
    runner = object.__new__(GatewayRunner)
    runner.adapters = {}
    runner._voice_mode = {}
    runner._session_model_overrides = {}
    runner._ephemeral_system_prompt = ""
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
async def test_handle_personality_command_persists_system_prompt_via_shared_writer(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()

    import gateway.run as gateway_run

    monkeypatch.setattr(gateway_run, "_hermes_home", hermes_home)

    with patch(
        "gateway.run._read_gateway_user_config",
        return_value={"agent": {"personalities": {"research": "Careful analytical mode"}}},
    ):
        result = await _make_runner()._handle_personality_command(_make_event("/personality research"))

    saved = yaml.safe_load((hermes_home / "config.yaml").read_text(encoding="utf-8"))
    assert result is not None
    assert "Personality set to **research**" in result
    assert saved["agent"]["system_prompt"] == "Careful analytical mode"


@pytest.mark.asyncio
async def test_handle_set_home_command_persists_home_channel_via_shared_writer(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()

    import gateway.run as gateway_run

    monkeypatch.setattr(gateway_run, "_hermes_home", hermes_home)
    event = _make_event("/sethome")
    event.source.chat_name = "Bot Home"

    result = await _make_runner()._handle_set_home_command(event)

    saved = yaml.safe_load((hermes_home / "config.yaml").read_text(encoding="utf-8"))
    assert result is not None
    assert "Home channel set to **Bot Home**" in result
    assert saved["TELEGRAM_HOME_CHANNEL"] == "12345"


@pytest.mark.asyncio
async def test_handle_model_command_global_persists_model_config(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    (hermes_home / "config.yaml").write_text(
        yaml.safe_dump({"model": {"default": "old-model", "provider": "openrouter"}}),
        encoding="utf-8",
    )

    import gateway.run as gateway_run

    runner = _make_runner()
    runner._evict_cached_agent = lambda _session_key: None
    monkeypatch.setattr(gateway_run, "_hermes_home", hermes_home)
    monkeypatch.setattr("agent.models_dev.fetch_models_dev", lambda: {})
    with patch("hermes_cli.model_switch.switch_model", lambda **kwargs: ModelSwitchResult(
        success=True,
        new_model="gpt-5.4",
        target_provider="openai",
        api_key="***",
        base_url="https://api.openai.com/v1",
        api_mode="responses",
        provider_label="OpenAI",
        is_global=True,
    )):
        result = await runner._handle_model_command(_make_event("/model gpt-5.4 --global"))

    saved = yaml.safe_load((hermes_home / "config.yaml").read_text(encoding="utf-8"))
    assert result is not None
    assert "Saved to config.yaml" in result
    assert saved["model"]["default"] == "gpt-5.4"
    assert saved["model"]["provider"] == "openai"


@pytest.mark.asyncio
async def test_handle_model_command_global_clears_stale_base_url_when_switch_result_has_none(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    (hermes_home / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "model": {
                    "default": "old-model",
                    "provider": "custom-provider",
                    "base_url": "https://stale.example/v1",
                }
            }
        ),
        encoding="utf-8",
    )

    import gateway.run as gateway_run

    runner = _make_runner()
    runner._evict_cached_agent = lambda _session_key: None
    monkeypatch.setattr(gateway_run, "_hermes_home", hermes_home)
    monkeypatch.setattr("agent.models_dev.fetch_models_dev", lambda: {})
    with patch("hermes_cli.model_switch.switch_model", lambda **kwargs: ModelSwitchResult(
        success=True,
        new_model="gpt-5.4",
        target_provider="openai",
        api_key="***",
        base_url=None,
        api_mode="responses",
        provider_label="OpenAI",
        is_global=True,
    )):
        result = await runner._handle_model_command(_make_event("/model gpt-5.4 --global"))

    saved = yaml.safe_load((hermes_home / "config.yaml").read_text(encoding="utf-8"))
    assert result is not None
    assert "Saved to config.yaml" in result
    assert saved["model"]["default"] == "gpt-5.4"
    assert saved["model"]["provider"] == "openai"
    assert "base_url" not in saved["model"]
