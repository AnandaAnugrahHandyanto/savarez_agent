"""Tests for opportunistic post-response compression."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

from agent.context_compressor import ContextCompressor
from agent.conversation_compression import maybe_compress_post_response


def test_post_response_threshold_uses_normal_threshold_minus_buffer():
    compressor = ContextCompressor(
        model="test/model",
        threshold_percent=0.50,
        preflight_threshold_percent=0.90,
        post_response_buffer_tokens=100,
        config_context_length=200_000,
        quiet_mode=True,
    )

    assert compressor.threshold_tokens == 100_000
    assert compressor.preflight_threshold_tokens == 180_000
    assert compressor.should_compress_post_response(99_899) is False
    assert compressor.should_compress_post_response(99_900) is True
    assert compressor.should_compress_emergency(179_999) is False
    assert compressor.should_compress_emergency(180_000) is True


def test_maybe_compress_post_response_skips_below_buffered_threshold():
    compressor = Mock()
    compressor.protect_first_n = 1
    compressor.protect_last_n = 1
    compressor.threshold_tokens = 1_000
    compressor.post_response_buffer_tokens = 100
    compressor.should_compress_post_response.return_value = False

    agent = SimpleNamespace(
        compression_enabled=True,
        context_compressor=compressor,
        tools=[],
        session_id="s1",
        _cached_system_prompt="system",
        _build_system_prompt=lambda system_message: "system",
    )
    messages = [
        {"role": "user", "content": "u1"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "u2"},
        {"role": "assistant", "content": "final delivered"},
    ]

    with (
        patch("agent.conversation_compression.estimate_request_tokens_rough", return_value=899),
        patch("agent.conversation_compression.compress_context") as mock_compress,
    ):
        returned_messages, _system_prompt, ran = maybe_compress_post_response(
            agent,
            messages,
            "system",
            task_id="s1",
        )

    assert returned_messages is messages
    assert ran is False
    compressor.should_compress_post_response.assert_called_once_with(899)
    mock_compress.assert_not_called()


def test_maybe_compress_post_response_preserves_final_message_until_compression_starts():
    compressor = Mock()
    compressor.protect_first_n = 1
    compressor.protect_last_n = 1
    compressor.threshold_tokens = 1_000
    compressor.post_response_buffer_tokens = 100
    compressor.should_compress_post_response.return_value = True

    agent = SimpleNamespace(
        compression_enabled=True,
        context_compressor=compressor,
        tools=[],
        session_id="s1",
        _cached_system_prompt="system",
        _build_system_prompt=lambda system_message: "system",
    )
    messages = [
        {"role": "user", "content": "u1"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "u2"},
        {"role": "assistant", "content": "final delivered"},
    ]

    def fake_compress(agent_arg, messages_arg, system_message, **kwargs):
        assert messages_arg[-1] == {"role": "assistant", "content": "final delivered"}
        return [messages_arg[0], {"role": "assistant", "content": "summary"}, messages_arg[-1]], "new system"

    with (
        patch("agent.conversation_compression.estimate_request_tokens_rough", return_value=900),
        patch("agent.conversation_compression.compress_context", side_effect=fake_compress) as mock_compress,
    ):
        returned_messages, system_prompt, ran = maybe_compress_post_response(
            agent,
            messages,
            "system",
            task_id="s1",
        )

    assert ran is True
    assert system_prompt == "new system"
    assert returned_messages[-1] == {"role": "assistant", "content": "final delivered"}
    mock_compress.assert_called_once()
