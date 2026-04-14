"""Gateway inbound-prep config tests."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import yaml

from gateway.config import GatewayConfig, Platform, load_gateway_config
from gateway.platforms.base import MessageEvent, MessageType
from gateway.session import SessionSource


def test_gateway_config_stt_disabled_from_dict_nested():
    config = GatewayConfig.from_dict({"stt": {"enabled": False}})
    assert config.stt_enabled is False


def test_load_gateway_config_bridges_stt_enabled_from_config_yaml(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    (hermes_home / "config.yaml").write_text(
        yaml.dump({"stt": {"enabled": False}}),
        encoding="utf-8",
    )

    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    config = load_gateway_config()

    assert config.stt_enabled is False


def test_gateway_config_timestamp_prefix_from_nested_gateway_dict():
    config = GatewayConfig.from_dict({"gateway": {"message_timestamp_prefix": True}})
    assert config.message_timestamp_prefix is True


def test_load_gateway_config_bridges_timestamp_prefix_from_config_yaml(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    (hermes_home / "config.yaml").write_text(
        yaml.dump({"gateway": {"message_timestamp_prefix": True}}),
        encoding="utf-8",
    )

    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    config = load_gateway_config()

    assert config.message_timestamp_prefix is True


@pytest.mark.asyncio
async def test_enrich_message_with_transcription_skips_when_stt_disabled():
    from gateway.run import GatewayRunner

    runner = GatewayRunner.__new__(GatewayRunner)
    runner.config = GatewayConfig(stt_enabled=False)

    with patch(
        "tools.transcription_tools.transcribe_audio",
        side_effect=AssertionError("transcribe_audio should not be called when STT is disabled"),
    ):
        result = await runner._enrich_message_with_transcription(
            "caption",
            ["/tmp/voice.ogg"],
        )

    assert "transcription is disabled" in result.lower()
    assert "caption" in result


@pytest.mark.asyncio
async def test_enrich_message_with_transcription_avoids_bogus_no_provider_message_for_backend_key_errors():
    from gateway.run import GatewayRunner

    runner = GatewayRunner.__new__(GatewayRunner)
    runner.config = GatewayConfig(stt_enabled=True)

    with patch(
        "tools.transcription_tools.transcribe_audio",
        return_value={"success": False, "error": "VOICE_TOOLS_OPENAI_KEY not set"},
    ):
        result = await runner._enrich_message_with_transcription(
            "caption",
            ["/tmp/voice.ogg"],
        )

    assert "No STT provider is configured" not in result
    assert "trouble transcribing" in result
    assert "caption" in result


@pytest.mark.asyncio
async def test_prepare_inbound_message_text_transcribes_queued_voice_event():
    from gateway.run import GatewayRunner

    runner = GatewayRunner.__new__(GatewayRunner)
    runner.config = GatewayConfig(stt_enabled=True)
    runner.adapters = {}
    runner._model = "test-model"
    runner._base_url = ""
    runner._has_setup_skill = lambda: False

    source = SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="123",
        chat_type="dm",
    )
    event = MessageEvent(
        text="",
        message_type=MessageType.VOICE,
        source=source,
        media_urls=["/tmp/queued-voice.ogg"],
        media_types=["audio/ogg"],
    )

    with patch(
        "tools.transcription_tools.transcribe_audio",
        return_value={
            "success": True,
            "transcript": "queued voice transcript",
            "provider": "local_command",
        },
    ):
        result = await runner._prepare_inbound_message_text(
            event=event,
            source=source,
            history=[],
        )

    assert result is not None
    assert "queued voice transcript" in result
    assert "voice message" in result.lower()


@pytest.mark.asyncio
async def test_prepare_inbound_message_text_prepends_utc_timestamp_when_enabled():
    from gateway.run import GatewayRunner

    runner = GatewayRunner.__new__(GatewayRunner)
    runner.config = GatewayConfig(message_timestamp_prefix=True)

    source = SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="123",
        chat_type="dm",
    )
    event = MessageEvent(
        text="hey, what day is it?",
        message_type=MessageType.TEXT,
        source=source,
    )

    frozen = datetime(2026, 4, 14, 23, 47, tzinfo=timezone.utc)
    with patch("gateway.run.datetime") as mock_datetime:
        mock_datetime.now.return_value = frozen
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
        result = await runner._prepare_inbound_message_text(
            event=event,
            source=source,
            history=[],
        )

    assert result == "[04-14 23:47] hey, what day is it?"


@pytest.mark.asyncio
async def test_prepare_inbound_message_text_keeps_sender_prefix_before_timestamp():
    from gateway.run import GatewayRunner

    runner = GatewayRunner.__new__(GatewayRunner)
    runner.config = GatewayConfig(
        message_timestamp_prefix=True,
        thread_sessions_per_user=False,
    )
    source = SessionSource(
        platform=Platform.DISCORD,
        chat_id="123",
        chat_type="thread",
        thread_id="456",
        user_name="alice",
    )
    event = MessageEvent(
        text="can you check this later?",
        message_type=MessageType.TEXT,
        source=source,
    )

    frozen = datetime(2026, 4, 14, 23, 47, tzinfo=timezone.utc)
    with patch("gateway.run.datetime") as mock_datetime:
        mock_datetime.now.return_value = frozen
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
        result = await runner._prepare_inbound_message_text(
            event=event,
            source=source,
            history=[],
        )

    assert result == "[04-14 23:47] [alice] can you check this later?"
