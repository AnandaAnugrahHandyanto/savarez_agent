import pytest
from unittest.mock import patch

from gateway.config import Platform
from gateway.platforms.base import MessageEvent, MessageType
from gateway.run import GatewayRunner
from gateway.session import SessionSource


def _make_runner():
    runner = object.__new__(GatewayRunner)
    runner.adapters = {}
    runner._voice_mode = {}
    runner._session_model_overrides = {}
    return runner


def _make_event(text: str):
    return MessageEvent(
        text=text,
        message_type=MessageType.TEXT,
        source=SessionSource(platform=Platform.TELEGRAM, chat_id="12345", chat_type="dm"),
    )


@pytest.mark.asyncio
async def test_handle_model_command_uses_shared_read_user_config(tmp_path, monkeypatch):
    import gateway.run as gateway_run

    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)
    monkeypatch.setattr("agent.models_dev.fetch_models_dev", lambda: {})
    called = {}

    def fake_read_user_config(*, expand_env=True, merge_defaults=False, config_path=None):
        called["args"] = (expand_env, merge_defaults, config_path)
        return {
            "model": {
                "default": "gpt-5.4",
                "provider": "openrouter",
                "base_url": "https://openrouter.ai/api/v1",
            },
            "providers": {},
            "custom_providers": [],
        }

    with patch("hermes_cli.config.read_user_config", side_effect=fake_read_user_config):
        result = await _make_runner()._handle_model_command(_make_event("/model"))

    assert result is not None
    assert "gpt-5.4" in result
    assert called["args"] == (True, False, tmp_path / "config.yaml")


@pytest.mark.asyncio
async def test_handle_provider_command_uses_shared_read_user_config(tmp_path, monkeypatch):
    import gateway.run as gateway_run

    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)
    called = {}

    def fake_read_user_config(*, expand_env=True, merge_defaults=False, config_path=None):
        called["args"] = (expand_env, merge_defaults, config_path)
        return {
            "model": {
                "provider": "openrouter",
                "base_url": "https://openrouter.ai/api/v1",
            }
        }

    with patch("hermes_cli.config.read_user_config", side_effect=fake_read_user_config):
        result = await _make_runner()._handle_provider_command(_make_event("/provider"))

    assert result is not None
    assert "openrouter" in result
    assert called["args"] == (True, False, tmp_path / "config.yaml")


@pytest.mark.asyncio
async def test_handle_personality_command_uses_shared_read_user_config(tmp_path, monkeypatch):
    import gateway.run as gateway_run

    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)
    called = {}

    def fake_read_user_config(*, expand_env=True, merge_defaults=False, config_path=None):
        called["args"] = (expand_env, merge_defaults, config_path)
        return {
            "agent": {
                "personalities": {
                    "research": "Careful analytical mode"
                }
            }
        }

    with patch("hermes_cli.config.read_user_config", side_effect=fake_read_user_config):
        result = await _make_runner()._handle_personality_command(_make_event("/personality"))

    assert result is not None
    assert "research" in result
    assert called["args"] == (True, False, tmp_path / "config.yaml")
