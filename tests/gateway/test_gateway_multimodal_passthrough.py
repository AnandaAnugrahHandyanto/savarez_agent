from unittest.mock import AsyncMock, patch

import pytest

from gateway.config import Platform
from gateway.run import GatewayRunner
from gateway.session import SessionSource


def _make_runner():
    runner = object.__new__(GatewayRunner)
    runner._resolve_session_agent_runtime = lambda **kwargs: (
        "openai/gpt-5.4",
        {
            "provider": "openrouter",
            "base_url": "https://openrouter.ai/api/v1",
            "api_mode": "chat_completions",
        },
    )
    runner._resolve_turn_agent_config = lambda user_message, model, runtime_kwargs: {
        "model": model,
        "runtime": runtime_kwargs,
    }
    runner._enrich_message_with_vision = AsyncMock(return_value="ENRICHED")
    return runner


def _make_source() -> SessionSource:
    return SessionSource(platform=Platform.TELEGRAM, chat_id="12345", chat_type="dm")


@pytest.mark.asyncio
async def test_resolve_gateway_image_message_auto_returns_native_multimodal(tmp_path):
    runner = _make_runner()
    image_path = tmp_path / "cat.png"
    image_path.write_bytes(b"fake-png")

    with (
        patch("gateway.run._load_gateway_config", return_value={"multimodal": {"image_input_policy": "auto"}}),
        patch("gateway.run.runtime_supports_native_image_input", return_value=True),
    ):
        agent_message, persist_user_message, image_error = await runner._resolve_gateway_image_message(
            user_text="What is in this image?",
            image_paths=[str(image_path)],
            source=_make_source(),
            session_key="session-1",
        )

    assert image_error is None
    assert isinstance(agent_message, list)
    assert agent_message[0] == {"type": "text", "text": "What is in this image?"}
    assert agent_message[1]["type"] == "image_url"
    assert agent_message[1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert "Attached image: cat.png" in persist_user_message
    runner._enrich_message_with_vision.assert_not_awaited()


@pytest.mark.asyncio
async def test_resolve_gateway_image_message_fallback_uses_vision_enrichment(tmp_path):
    runner = _make_runner()
    image_path = tmp_path / "cat.png"
    image_path.write_bytes(b"fake-png")

    with patch("gateway.run._load_gateway_config", return_value={"multimodal": {"image_input_policy": "fallback"}}):
        agent_message, persist_user_message, image_error = await runner._resolve_gateway_image_message(
            user_text="Describe it",
            image_paths=[str(image_path)],
            source=_make_source(),
            session_key="session-1",
        )

    assert agent_message == "ENRICHED"
    assert persist_user_message is None
    assert image_error is None
    runner._enrich_message_with_vision.assert_awaited_once()


@pytest.mark.asyncio
async def test_resolve_gateway_image_message_strict_returns_error_for_unsupported_runtime(tmp_path):
    runner = _make_runner()
    image_path = tmp_path / "cat.png"
    image_path.write_bytes(b"fake-png")

    with (
        patch("gateway.run._load_gateway_config", return_value={"multimodal": {"image_input_policy": "strict"}}),
        patch("gateway.run.runtime_supports_native_image_input", return_value=None),
    ):
        agent_message, persist_user_message, image_error = await runner._resolve_gateway_image_message(
            user_text="Describe it",
            image_paths=[str(image_path)],
            source=_make_source(),
            session_key="session-1",
        )

    assert agent_message == "Describe it"
    assert persist_user_message is None
    assert image_error == "❌ Native image passthrough is unavailable for the active runtime in strict multimodal mode."
    runner._enrich_message_with_vision.assert_not_awaited()
