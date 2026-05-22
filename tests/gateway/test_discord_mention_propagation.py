"""Tests for Discord continuation-chunk mention propagation (issue #27265).

When a Hermes bot sends a long message addressed to another (mention-gated)
bot, Discord's 2000-char split causes only the first chunk to carry the
target mention. A receiving bot with ``DISCORD_ALLOW_BOTS=mentions`` would
then ingest part 1 and silently drop parts 2..N. The fix prepends the
leading mention prefix from the first chunk onto every continuation chunk.
"""
from __future__ import annotations

from tests.gateway.test_discord_send import _ensure_discord_mock

_ensure_discord_mock()

from gateway.platforms.discord import DiscordAdapter  # noqa: E402


class TestExtractLeadingMentionPrefix:
    def test_single_user_mention(self) -> None:
        assert (
            DiscordAdapter._extract_leading_mention_prefix("<@123> hello world")
            == "<@123>"
        )

    def test_user_mention_with_bang(self) -> None:
        assert (
            DiscordAdapter._extract_leading_mention_prefix("<@!456> ping")
            == "<@!456>"
        )

    def test_role_mention(self) -> None:
        assert (
            DiscordAdapter._extract_leading_mention_prefix("<@&789> roll call")
            == "<@&789>"
        )

    def test_multiple_mentions(self) -> None:
        assert (
            DiscordAdapter._extract_leading_mention_prefix(
                "<@1> <@!2> <@&3> message"
            )
            == "<@1> <@!2> <@&3>"
        )

    def test_no_mention_returns_empty(self) -> None:
        assert DiscordAdapter._extract_leading_mention_prefix("hello world") == ""

    def test_everyone_not_treated_as_mention(self) -> None:
        # We deliberately don't propagate @everyone / @here — replaying it on
        # every chunk would spam the whole server.
        assert (
            DiscordAdapter._extract_leading_mention_prefix("@everyone hi") == ""
        )
        assert DiscordAdapter._extract_leading_mention_prefix("@here hi") == ""

    def test_empty_string(self) -> None:
        assert DiscordAdapter._extract_leading_mention_prefix("") == ""

    def test_inline_mention_not_extracted(self) -> None:
        # Only the very first token counts as a leading prefix.
        assert (
            DiscordAdapter._extract_leading_mention_prefix("hi <@123>") == ""
        )


class TestPropagateLeadingMentions:
    def test_propagates_to_continuation_chunks(self) -> None:
        chunks = [
            "<@111> intro line (1/3)",
            "middle chunk (2/3)",
            "final chunk (3/3)",
        ]
        out = DiscordAdapter._propagate_leading_mentions(chunks)
        assert out[0] == "<@111> intro line (1/3)"
        assert out[1] == "<@111> middle chunk (2/3)"
        assert out[2] == "<@111> final chunk (3/3)"

    def test_single_chunk_unchanged(self) -> None:
        chunks = ["<@111> short message"]
        assert DiscordAdapter._propagate_leading_mentions(chunks) == chunks

    def test_no_mention_unchanged(self) -> None:
        chunks = ["intro (1/2)", "tail (2/2)"]
        assert DiscordAdapter._propagate_leading_mentions(chunks) == chunks

    def test_idempotent(self) -> None:
        chunks = [
            "<@111> first (1/2)",
            "<@111> already prefixed (2/2)",
        ]
        out = DiscordAdapter._propagate_leading_mentions(chunks)
        assert out == chunks  # no double-prefix

    def test_skips_when_oversize(self) -> None:
        # Force a small max_length so the prefixed continuation would exceed it.
        chunks = ["<@1> aaa", "bbbbbbbbbbb"]
        out = DiscordAdapter._propagate_leading_mentions(chunks, max_length=10)
        assert out[0] == "<@1> aaa"
        # Prefixed form "<@1> bbbbbbbbbbb" is 16 chars > 10 → keep original
        assert out[1] == "bbbbbbbbbbb"

    def test_empty_input(self) -> None:
        assert DiscordAdapter._propagate_leading_mentions([]) == []

    def test_role_mention_propagation(self) -> None:
        chunks = ["<@&42> announcement (1/2)", "details (2/2)"]
        out = DiscordAdapter._propagate_leading_mentions(chunks)
        assert out[1] == "<@&42> details (2/2)"

    def test_multi_mention_propagation(self) -> None:
        chunks = ["<@1> <@2> hello (1/2)", "world (2/2)"]
        out = DiscordAdapter._propagate_leading_mentions(chunks)
        assert out[1] == "<@1> <@2> world (2/2)"


class TestRealTruncate:
    """End-to-end through ``truncate_message`` + propagation."""

    def test_long_handoff_keeps_mention_on_every_chunk(self) -> None:
        body = "x" * 5000
        full = f"<@999> {body}"
        chunks = DiscordAdapter.truncate_message(
            full, DiscordAdapter.MAX_MESSAGE_LENGTH
        )
        assert len(chunks) > 1, "test setup should produce multiple chunks"
        out = DiscordAdapter._propagate_leading_mentions(chunks)
        # Every chunk must mention the target bot
        for chunk in out:
            assert chunk.startswith("<@999>"), (
                f"continuation chunk missing target mention: {chunk[:80]!r}"
            )
