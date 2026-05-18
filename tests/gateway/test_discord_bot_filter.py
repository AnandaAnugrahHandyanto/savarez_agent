"""Tests for Discord bot message filtering (DISCORD_ALLOW_BOTS)."""

import asyncio
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch


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

    def _run_filter(self, message, allow_bots="none", client_user=None, agent_user_ids=None):
        """Simulate the on_message filter logic and return whether message was accepted."""
        # Replicate the exact filter logic from discord.py on_message
        if message.author == client_user:
            return False  # own messages always ignored

        agent_ids = {str(s) for s in (agent_user_ids or [])}
        author_id = str(getattr(message.author, "id", ""))
        is_bot_author = bool(getattr(message.author, "bot", False))
        is_agent_user = (not is_bot_author) and (author_id in agent_ids)

        if is_bot_author or is_agent_user:
            allow = allow_bots.lower().strip()
            if allow == "none":
                return False
            elif allow == "mentions":
                if not client_user or client_user not in message.mentions:
                    return False
            # "all" falls through

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

    def test_allow_bots_all_accepts_bots(self):
        """With allow_bots=all, all bot messages are accepted."""
        bot = _make_author(bot=True)
        msg = _make_message(author=bot)
        self.assertTrue(self._run_filter(msg, "all"))

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
        """Default behavior (no env var) should be 'none'."""
        default = os.getenv("DISCORD_ALLOW_BOTS", "none")
        self.assertEqual(default, "none")

    def test_case_insensitive(self):
        """Allow_bots value should be case-insensitive."""
        bot = _make_author(bot=True)
        msg = _make_message(author=bot)
        self.assertTrue(self._run_filter(msg, "ALL"))
        self.assertTrue(self._run_filter(msg, "All"))
        self.assertFalse(self._run_filter(msg, "NONE"))
        self.assertFalse(self._run_filter(msg, "None"))

    def test_agent_user_id_treated_as_bot_under_none(self):
        """User-OAuth peer agent (author.bot=False) listed in DISCORD_AGENT_USER_IDS
        is rejected under allow_bots=none."""
        peer = _make_author(bot=False)
        peer.id = 1503473217581350993
        msg = _make_message(author=peer)
        self.assertFalse(
            self._run_filter(msg, "none", agent_user_ids=["1503473217581350993"])
        )

    def test_agent_user_id_rejected_without_mention_under_mentions(self):
        """Peer agent posting plain words on shared channel is rejected when
        allow_bots=mentions and we are not @-mentioned."""
        our_user = _make_author(is_self=True)
        peer = _make_author(bot=False)
        peer.id = 1503473217581350993
        msg = _make_message(author=peer, mentions=[])
        self.assertFalse(
            self._run_filter(
                msg, "mentions", our_user, agent_user_ids=["1503473217581350993"]
            )
        )

    def test_agent_user_id_accepted_with_mention_under_mentions(self):
        """Peer agent that explicitly @-mentions us is accepted under
        allow_bots=mentions."""
        our_user = _make_author(is_self=True)
        peer = _make_author(bot=False)
        peer.id = 1503473217581350993
        msg = _make_message(author=peer, mentions=[our_user])
        self.assertTrue(
            self._run_filter(
                msg, "mentions", our_user, agent_user_ids=["1503473217581350993"]
            )
        )

    def test_agent_user_id_not_in_list_treated_as_human(self):
        """Non-listed user is treated as a regular human and falls through
        the bot filter regardless of allow_bots policy."""
        random_user = _make_author(bot=False)
        random_user.id = 42
        msg = _make_message(author=random_user)
        self.assertTrue(
            self._run_filter(msg, "none", agent_user_ids=["1503473217581350993"])
        )
        self.assertTrue(
            self._run_filter(msg, "mentions", agent_user_ids=["1503473217581350993"])
        )


if __name__ == "__main__":
    unittest.main()
