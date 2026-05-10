from gateway.config import Platform
from gateway.run import _should_suppress_gateway_lifecycle_status


def test_messaging_platforms_suppress_compression_lifecycle_statuses():
    noisy_messages = [
        "📦 Preflight compression: ~191,447 tokens >= 136,000 threshold. This may take a moment.",
        "🗜️ Context reduced to 42,000 tokens",
        "🗜️ Context too large for provider window",
        "🗜️ Compressed conversation history",
        "⚠️  Request payload too large; compressing before retry",
    ]

    for platform in (Platform.TELEGRAM, Platform.DISCORD):
        for message in noisy_messages:
            assert _should_suppress_gateway_lifecycle_status(platform, "lifecycle", message)


def test_messaging_platforms_keep_non_compression_statuses():
    assert not _should_suppress_gateway_lifecycle_status(
        Platform.TELEGRAM,
        "lifecycle",
        "Starting gateway...",
    )
    assert not _should_suppress_gateway_lifecycle_status(
        Platform.DISCORD,
        "tool",
        "📦 Preflight compression: should only match lifecycle events",
    )


def test_non_chat_platforms_keep_compression_lifecycle_statuses():
    assert not _should_suppress_gateway_lifecycle_status(
        Platform.LOCAL,
        "lifecycle",
        "📦 Preflight compression: useful in CLI/TUI",
    )
