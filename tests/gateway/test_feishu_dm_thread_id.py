"""
Test that Feishu DM (p2p) quoted replies do not create isolated sessions.

Regression test for #44028: quoted replies in DMs populate thread_id/root_id
from the Lark SDK, but Feishu DMs don't support real threads.  Without the
guard, these IDs flow into build_source() and produce isolated session keys.
"""
import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import asyncio


class TestFeishuDMQuotedReplyNoThread(unittest.TestCase):
    """Verify p2p quoted replies don't leak thread_id into session keys."""

    @patch.dict(os.environ, {}, clear=True)
    def test_p2p_quoted_reply_ignores_thread_id(self):
        """In DM (p2p) mode, thread_id from a quoted reply must be cleared."""
        from gateway.config import PlatformConfig
        from gateway.platforms.feishu import FeishuAdapter

        adapter = FeishuAdapter(PlatformConfig())
        adapter._dispatch_inbound_event = AsyncMock()
        adapter.get_chat_info = AsyncMock(
            return_value={"chat_id": "oc_dm", "name": "DM", "type": "dm"}
        )
        adapter._resolve_sender_profile = AsyncMock(
            return_value={"user_id": "ou_sender", "user_name": "Alice", "user_id_alt": None}
        )

        # Quoted reply in a DM: Lark SDK fills thread_id/root_id
        message = SimpleNamespace(
            chat_id="oc_dm",
            thread_id="om_parent_msg",  # <-- this should be ignored in p2p
            root_id="om_root_msg",
            parent_id="om_parent_msg",
            upper_message_id=None,
            message_type="text",
            content='{"text":"reply to you"}',
            message_id="om_new_msg",
        )

        asyncio.run(
            adapter._process_inbound_message(
                data=SimpleNamespace(event=SimpleNamespace(message=message)),
                message=message,
                sender_id=SimpleNamespace(open_id="ou_sender", user_id=None, union_id=None),
                is_bot=False,
                chat_type="p2p",
                message_id="om_new_msg",
            )
        )

        event = adapter._dispatch_inbound_event.await_args.args[0]
        # thread_id must be None for p2p — quoted reply must not isolate the session
        self.assertIsNone(event.source.thread_id)

    @patch.dict(os.environ, {}, clear=True)
    def test_group_quoted_reply_preserves_thread_id(self):
        """In group mode, thread_id from a quoted reply must be preserved."""
        from gateway.config import PlatformConfig
        from gateway.platforms.feishu import FeishuAdapter

        adapter = FeishuAdapter(PlatformConfig())
        adapter._dispatch_inbound_event = AsyncMock()
        adapter.get_chat_info = AsyncMock(
            return_value={"chat_id": "oc_group", "name": "Group", "type": "group"}
        )
        adapter._resolve_sender_profile = AsyncMock(
            return_value={"user_id": "ou_sender", "user_name": "Alice", "user_id_alt": None}
        )

        message = SimpleNamespace(
            chat_id="oc_group",
            thread_id="omt_thread_123",
            root_id=None,
            parent_id="om_parent_msg",
            upper_message_id=None,
            message_type="text",
            content='{"text":"threaded reply"}',
            message_id="om_thread_msg",
        )

        asyncio.run(
            adapter._process_inbound_message(
                data=SimpleNamespace(event=SimpleNamespace(message=message)),
                message=message,
                sender_id=SimpleNamespace(open_id="ou_sender", user_id=None, union_id=None),
                is_bot=False,
                chat_type="group",
                message_id="om_thread_msg",
            )
        )

        event = adapter._dispatch_inbound_event.await_args.args[0]
        # Group threads must preserve thread_id
        self.assertEqual(event.source.thread_id, "omt_thread_123")

    @patch.dict(os.environ, {}, clear=True)
    def test_p2p_no_thread_id_unchanged(self):
        """Normal DM (no quoted reply) must still work with thread_id=None."""
        from gateway.config import PlatformConfig
        from gateway.platforms.feishu import FeishuAdapter

        adapter = FeishuAdapter(PlatformConfig())
        adapter._dispatch_inbound_event = AsyncMock()
        adapter.get_chat_info = AsyncMock(
            return_value={"chat_id": "oc_dm", "name": "DM", "type": "dm"}
        )
        adapter._resolve_sender_profile = AsyncMock(
            return_value={"user_id": "ou_sender", "user_name": "Bob", "user_id_alt": None}
        )

        message = SimpleNamespace(
            chat_id="oc_dm",
            thread_id=None,
            root_id=None,
            parent_id=None,
            upper_message_id=None,
            message_type="text",
            content='{"text":"hello"}',
            message_id="om_normal",
        )

        asyncio.run(
            adapter._process_inbound_message(
                data=SimpleNamespace(event=SimpleNamespace(message=message)),
                message=message,
                sender_id=SimpleNamespace(open_id="ou_sender", user_id=None, union_id=None),
                is_bot=False,
                chat_type="p2p",
                message_id="om_normal",
            )
        )

        event = adapter._dispatch_inbound_event.await_args.args[0]
        self.assertIsNone(event.source.thread_id)
        self.assertIn("hello", event.text)


if __name__ == "__main__":
    unittest.main()
