"""Tests for Discord bot message filtering (DISCORD_ALLOW_BOTS)."""

import asyncio
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from gateway.platforms.discord import _is_discord_bot_loop_fuel


def _make_author(*, bot: bool = False, is_self: bool = False):
    """Create a mock Discord author."""
    author = MagicMock()
    author.bot = bot
    author.id = 99999 if is_self else 12345
    author.name = "TestBot" if bot else "TestUser"
    author.display_name = author.name
    return author


def _make_message(*, author=None, content="hello", mentions=None, is_dm=False):
    """Create a mock Discord message."""
    msg = MagicMock()
    msg.author = author or _make_author()
    msg.content = content
    msg.attachments = []
    msg.mentions = mentions or []
    if is_dm:
        import discord
        msg.channel = MagicMock(spec=discord.DMChannel)
        msg.channel.id = 111
    else:
        msg.channel = MagicMock()
        msg.channel.id = 222
        msg.channel.name = "test-channel"
        msg.channel.guild = MagicMock()
        msg.channel.guild.name = "TestServer"
        # Make isinstance checks fail for DMChannel and Thread
        type(msg.channel).__name__ = "TextChannel"
    return msg


class TestDiscordBotFilter(unittest.TestCase):
    """Test the DISCORD_ALLOW_BOTS filtering logic."""

    def _run_filter(self, message, allow_bots="none", client_user=None):
        """Simulate the on_message filter logic and return whether message was accepted."""
        # Replicate the exact filter logic from discord.py on_message
        if message.author == client_user:
            return False  # own messages always ignored

        if getattr(message.author, "bot", False):
            if _is_discord_bot_loop_fuel(getattr(message, "content", "")):
                return False
            if not client_user or client_user not in message.mentions:
                return False
            allow = allow_bots.lower().strip()
            if allow == "none":
                return False
            # "mentions" and "all" both fall through after explicit self mention.
        
        return True  # message accepted

    def test_own_messages_always_ignored(self):
        """Bot's own messages are always ignored regardless of allow_bots."""
        bot_user = _make_author(is_self=True)
        msg = _make_message(author=bot_user)
        self.assertFalse(self._run_filter(msg, "all", bot_user))

    def test_human_messages_always_accepted(self):
        """Human messages are always accepted regardless of allow_bots."""
        human = _make_author(bot=False)
        msg = _make_message(author=human)
        self.assertTrue(self._run_filter(msg, "none"))
        self.assertTrue(self._run_filter(msg, "mentions"))
        self.assertTrue(self._run_filter(msg, "all"))

    def test_allow_bots_none_rejects_bots(self):
        """With allow_bots=none, all other bot messages are rejected."""
        bot = _make_author(bot=True)
        msg = _make_message(author=bot)
        self.assertFalse(self._run_filter(msg, "none"))

    def test_allow_bots_all_rejects_without_self_mention(self):
        """Bot messages still require explicit self mention with allow_bots=all."""
        our_user = _make_author(is_self=True)
        bot = _make_author(bot=True)
        msg = _make_message(author=bot, mentions=[])
        self.assertFalse(self._run_filter(msg, "all", our_user))

    def test_allow_bots_all_accepts_with_self_mention(self):
        """With allow_bots=all, substantive bot messages with @mention are accepted."""
        our_user = _make_author(is_self=True)
        bot = _make_author(bot=True)
        msg = _make_message(author=bot, content="Please review PR #123", mentions=[our_user])
        self.assertTrue(self._run_filter(msg, "all", our_user))

    def test_allow_bots_mentions_rejects_without_mention(self):
        """With allow_bots=mentions, bot messages without @mention are rejected."""
        our_user = _make_author(is_self=True)
        bot = _make_author(bot=True)
        msg = _make_message(author=bot, mentions=[])
        self.assertFalse(self._run_filter(msg, "mentions", our_user))

    def test_allow_bots_mentions_accepts_with_mention(self):
        """With allow_bots=mentions, bot messages with @mention are accepted."""
        our_user = _make_author(is_self=True)
        bot = _make_author(bot=True)
        msg = _make_message(author=bot, mentions=[our_user])
        self.assertTrue(self._run_filter(msg, "mentions", our_user))

    def test_default_is_none(self):
        """Document the adapter's code default when no env override is set."""
        with patch.dict(os.environ, {}, clear=True):
            default = os.getenv("DISCORD_ALLOW_BOTS", "none")
        self.assertEqual(default, "none")

    def test_case_insensitive(self):
        """Allow_bots value should be case-insensitive."""
        our_user = _make_author(is_self=True)
        bot = _make_author(bot=True)
        msg = _make_message(author=bot, content="Please review this", mentions=[our_user])
        self.assertTrue(self._run_filter(msg, "ALL", our_user))
        self.assertTrue(self._run_filter(msg, "All", our_user))
        self.assertFalse(self._run_filter(msg, "NONE", our_user))
        self.assertFalse(self._run_filter(msg, "None", our_user))

    def test_bot_wait_ack_messages_are_loop_fuel(self):
        """Bot wait/ack/stop chatter is ignored even when it mentions this bot."""
        our_user = _make_author(is_self=True)
        bot = _make_author(bot=True)
        for content in [
            "收到",
            "等老大",
            "（静默等待）",
            "不发任何消息",
            "⚠️ The model returned no response after processing tool results.",
            "⚠️ Codex response remained incomplete after 3 continuation attempts",
            "⚡ Interrupting current task (iteration 1/90). I'll respond to your message shortly.",
        ]:
            with self.subTest(content=content):
                msg = _make_message(author=bot, content=content, mentions=[our_user])
                self.assertFalse(self._run_filter(msg, "all", our_user))

    def test_human_wait_text_is_not_bot_filtered(self):
        """Humans can still send short wait/ack text; this gate only filters bots."""
        human = _make_author(bot=False)
        msg = _make_message(author=human, content="等老大")
        self.assertTrue(self._run_filter(msg, "none"))

    def test_substantive_bot_mention_is_not_loop_fuel(self):
        """Substantive bot messages with self mention still support bot-to-bot review."""
        our_user = _make_author(is_self=True)
        bot = _make_author(bot=True)
        msg = _make_message(
            author=bot,
            content="PR #123 is ready. Please review the diff and test plan.",
            mentions=[our_user],
        )
        self.assertTrue(self._run_filter(msg, "all", our_user))


if __name__ == "__main__":
    unittest.main()
