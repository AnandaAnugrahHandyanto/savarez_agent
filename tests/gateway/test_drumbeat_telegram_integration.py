"""
Integration tests for Drumbeat approval callbacks in Telegram adapter.

Tests that Drumbeat callbacks work correctly in the Telegram gateway and
don't interfere with existing callback types.
"""

import os
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Minimal Telegram mock — must run BEFORE importing TelegramAdapter so that
# sys.modules["telegram"] is a MagicMock, not the real package.  Without this
# guard, pytest collection of this file imports real python-telegram-bot and
# prevents the mock in sibling test files (test_telegram_approval_buttons, etc.)
# from activating, which breaks their `"MARKDOWN_V2" in repr(parse_mode)`
# assertions (real ParseMode is a StrEnum in ptb 22.6 whose repr is just the
# string value, not the enum member name).
# ---------------------------------------------------------------------------
_repo = str(Path(__file__).resolve().parents[2])
if _repo not in sys.path:
    sys.path.insert(0, _repo)


def _ensure_telegram_mock():
    if "telegram" in sys.modules and hasattr(sys.modules["telegram"], "__file__"):
        return
    mod = MagicMock()
    mod.ext.ContextTypes.DEFAULT_TYPE = type(None)
    mod.ParseMode.MARKDOWN = "Markdown"
    mod.ParseMode.MARKDOWN_V2 = "MarkdownV2"
    mod.ParseMode.HTML = "HTML"
    mod.ChatType.PRIVATE = "private"
    mod.ChatType.GROUP = "group"
    mod.ChatType.SUPERGROUP = "supergroup"
    mod.ChatType.CHANNEL = "channel"
    mod.error.NetworkError = type("NetworkError", (OSError,), {})
    mod.error.TimedOut = type("TimedOut", (OSError,), {})
    mod.error.BadRequest = type("BadRequest", (Exception,), {})
    for name in ("telegram", "telegram.ext", "telegram.constants", "telegram.request"):
        sys.modules.setdefault(name, mod)
    sys.modules.setdefault("telegram.error", mod.error)


_ensure_telegram_mock()

from gateway.config import PlatformConfig
from gateway.platforms.telegram import TelegramAdapter


class TestTelegramDrumbeatCallbacks(unittest.IsolatedAsyncioTestCase):
    """Test Drumbeat callbacks in Telegram adapter."""

    def setUp(self):
        """Set up test environment with temporary database."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_drumbeat.db")

        # Create Drumbeat database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE candidates (id INTEGER PRIMARY KEY)")
        cursor.execute("INSERT INTO candidates (id) VALUES (1)")
        cursor.execute("""
            CREATE TABLE drafts (
                id TEXT PRIMARY KEY,
                candidate_id INTEGER NOT NULL,
                post_text TEXT NOT NULL,
                final_text TEXT,
                prompt_version TEXT NOT NULL,
                generated_at INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                hafs_decision_at INTEGER,
                hafs_decision TEXT,
                FOREIGN KEY (candidate_id) REFERENCES candidates(id)
            )
        """)
        conn.commit()
        conn.close()

        # Set environment variable for handler
        os.environ["DRUMBEAT_DB"] = self.db_path

        # Create adapter (minimal setup)
        config = PlatformConfig(enabled=True, token="fake-token")
        self.adapter = TelegramAdapter(config=config)
        self.adapter._bot = MagicMock()

        # Mock authorization to always return True for tests
        self.adapter._is_callback_user_authorized = lambda *args, **kwargs: True

    def tearDown(self):
        """Clean up temporary database."""
        import shutil
        if "DRUMBEAT_DB" in os.environ:
            del os.environ["DRUMBEAT_DB"]
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _insert_draft(self, draft_id: str, post_text: str = "Test post", final_text: str = None, status: str = "pending"):
        """Helper to insert a test draft."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO drafts (id, candidate_id, post_text, final_text, prompt_version, generated_at, status) "
            "VALUES (?, 1, ?, ?, 'v1', ?, ?)",
            (draft_id, post_text, final_text, int(time.time()), status)
        )
        conn.commit()
        conn.close()

    def _get_draft_status(self, draft_id: str):
        """Helper to get draft status."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT status, hafs_decision FROM drafts WHERE id = ?", (draft_id,))
        row = cursor.fetchone()
        conn.close()
        return row if row else None

    def _create_callback_query(self, callback_data: str, user_id: int = 123456):
        """Create a mock callback query."""
        update = MagicMock()
        query = MagicMock()
        query.data = callback_data
        query.from_user = MagicMock()
        query.from_user.id = user_id
        query.from_user.first_name = "TestUser"

        message = MagicMock()
        message.chat_id = 123456
        chat = MagicMock()
        chat.type = "private"
        message.chat = chat
        message.message_thread_id = None
        query.message = message

        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()

        update.callback_query = query
        return update, query

    async def test_drumbeat_approve_callback(self):
        """Test approving a draft via Telegram callback."""
        draft_id = "d_test_approve_integration"
        post_text = "This is the approved post content."
        self._insert_draft(draft_id, post_text=post_text)

        update, query = self._create_callback_query(f"drumbeat:approve:{draft_id}")
        context = MagicMock()

        await self.adapter._handle_callback_query(update, context)

        # Verify callback was answered
        query.answer.assert_called_once()
        call_args = query.answer.call_args
        self.assertIn("Approved", call_args.kwargs["text"])

        # Verify message was edited
        query.edit_message_text.assert_called_once()
        edit_args = query.edit_message_text.call_args
        self.assertIn("TestUser", edit_args.kwargs["text"])
        self.assertIn(post_text, edit_args.kwargs["text"])

        # Verify database state
        status, decision = self._get_draft_status(draft_id)
        self.assertEqual(status, "approved")
        self.assertEqual(decision, "approved")

    async def test_drumbeat_reject_callback(self):
        """Test rejecting a draft via Telegram callback."""
        draft_id = "d_test_reject_integration"
        self._insert_draft(draft_id)

        update, query = self._create_callback_query(f"drumbeat:reject:{draft_id}")
        context = MagicMock()

        await self.adapter._handle_callback_query(update, context)

        query.answer.assert_called_once()
        self.assertIn("Rejected", query.answer.call_args.kwargs["text"])

        status, decision = self._get_draft_status(draft_id)
        self.assertEqual(status, "rejected")
        self.assertEqual(decision, "rejected")

    async def test_drumbeat_skip_callback(self):
        """Test skipping a draft via Telegram callback."""
        draft_id = "d_test_skip_integration"
        self._insert_draft(draft_id)

        update, query = self._create_callback_query(f"drumbeat:skip:{draft_id}")
        context = MagicMock()

        await self.adapter._handle_callback_query(update, context)

        query.answer.assert_called_once()
        self.assertIn("Skipped", query.answer.call_args.kwargs["text"])

        status, decision = self._get_draft_status(draft_id)
        self.assertEqual(status, "skipped")
        self.assertEqual(decision, "skipped")

    async def test_drumbeat_edit_callback(self):
        """Test edit request via Telegram callback."""
        draft_id = "d_test_edit_integration"
        self._insert_draft(draft_id)

        update, query = self._create_callback_query(f"drumbeat:edit:{draft_id}")
        context = MagicMock()

        await self.adapter._handle_callback_query(update, context)

        query.answer.assert_called_once()
        self.assertIn("Edit requested", query.answer.call_args.kwargs["text"])

        status, decision = self._get_draft_status(draft_id)
        self.assertEqual(status, "pending")  # Stays pending
        self.assertEqual(decision, "edit_requested")

    async def test_backward_compatible_callback(self):
        """Test backward-compatible callback format (action:draft_id)."""
        draft_id = "d_backward_compat"
        self._insert_draft(draft_id)

        update, query = self._create_callback_query(f"approve:{draft_id}")
        context = MagicMock()

        await self.adapter._handle_callback_query(update, context)

        query.answer.assert_called_once()
        status, decision = self._get_draft_status(draft_id)
        self.assertEqual(status, "approved")

    async def test_unauthorized_callback(self):
        """Test that unauthorized users cannot approve."""
        draft_id = "d_unauthorized"
        self._insert_draft(draft_id)

        # Mock authorization to return False
        self.adapter._is_callback_user_authorized = lambda *args, **kwargs: False

        update, query = self._create_callback_query(f"drumbeat:approve:{draft_id}")
        context = MagicMock()

        await self.adapter._handle_callback_query(update, context)

        # Should answer with unauthorized message
        query.answer.assert_called_once()
        self.assertIn("not authorized", query.answer.call_args.kwargs["text"].lower())

        # Should NOT edit message
        query.edit_message_text.assert_not_called()

        # Draft should remain pending
        status, decision = self._get_draft_status(draft_id)
        self.assertEqual(status, "pending")
        self.assertIsNone(decision)

    async def test_nonexistent_draft(self):
        """Test handling of callback for non-existent draft."""
        update, query = self._create_callback_query("drumbeat:approve:d_nonexistent")
        context = MagicMock()

        await self.adapter._handle_callback_query(update, context)

        query.answer.assert_called_once()
        self.assertIn("not found", query.answer.call_args.kwargs["text"].lower())

    async def test_already_approved_draft(self):
        """Test that already-approved drafts show appropriate message."""
        draft_id = "d_already_approved"
        self._insert_draft(draft_id, status="approved")

        update, query = self._create_callback_query(f"drumbeat:reject:{draft_id}")
        context = MagicMock()

        await self.adapter._handle_callback_query(update, context)

        query.answer.assert_called_once()
        self.assertIn("already approved", query.answer.call_args.kwargs["text"].lower())

        # Status should remain approved
        status, decision = self._get_draft_status(draft_id)
        self.assertEqual(status, "approved")

    async def test_non_drumbeat_callbacks_still_work(self):
        """Test that non-Drumbeat callbacks are not affected."""
        # Test update_prompt callback (existing callback type)
        update, query = self._create_callback_query("update_prompt:y")
        context = MagicMock()

        # Should not crash or be processed as Drumbeat callback
        await self.adapter._handle_callback_query(update, context)

        # The update_prompt handler should have been called
        # (We're just verifying no crash here - full update_prompt test is elsewhere)
        query.answer.assert_called()

    async def test_malformed_drumbeat_callback(self):
        """Test that malformed Drumbeat callbacks don't crash the gateway."""
        test_cases = [
            "drumbeat:",
            "drumbeat:approve:",
            "drumbeat::d_123",
            "drumbeat:invalid_action:d_123",
        ]

        for callback_data in test_cases:
            with self.subTest(callback_data=callback_data):
                update, query = self._create_callback_query(callback_data)
                context = MagicMock()

                # Should not crash
                await self.adapter._handle_callback_query(update, context)

                # Might answer or might not, but should not crash
                # (malformed data won't match parse_drumbeat_callback_data)


class TestTelegramDrumbeatFallthrough(unittest.IsolatedAsyncioTestCase):
    """Test that Drumbeat callbacks don't interfere with other callback types."""

    async def test_exec_approval_callback_not_hijacked(self):
        """Test that ea: callbacks are not affected."""
        config = PlatformConfig(enabled=True, token="fake-token")
        adapter = TelegramAdapter(config=config)
        adapter._approval_state = {123: "test_session"}
        adapter._is_callback_user_authorized = lambda *args, **kwargs: True

        update = MagicMock()
        query = MagicMock()
        query.data = "ea:once:123"
        query.from_user = MagicMock()
        query.from_user.id = 123456
        query.from_user.first_name = "TestUser"

        message = MagicMock()
        message.chat_id = 123456
        chat = MagicMock()
        chat.type = "private"
        message.chat = chat
        message.message_thread_id = None
        query.message = message

        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()

        update.callback_query = query
        context = MagicMock()

        # Mock the approval resolver
        with patch("tools.approval.resolve_gateway_approval") as mock_resolve:
            mock_resolve.return_value = 1

            await adapter._handle_callback_query(update, context)

            # Should have called the exec approval handler, not Drumbeat
            mock_resolve.assert_called_once()

    async def test_slash_confirm_callback_not_hijacked(self):
        """Test that sc: callbacks are not affected."""
        config = PlatformConfig(enabled=True, token="fake-token")
        adapter = TelegramAdapter(config=config)
        adapter._slash_confirm_state = {"confirm_123": "test_session"}
        adapter._is_callback_user_authorized = lambda *args, **kwargs: True

        update = MagicMock()
        query = MagicMock()
        query.data = "sc:once:confirm_123"
        query.from_user = MagicMock()
        query.from_user.id = 123456
        query.from_user.first_name = "TestUser"

        message = MagicMock()
        message.chat_id = 123456
        chat = MagicMock()
        chat.type = "private"
        message.chat = chat
        message.message_thread_id = None
        query.message = message

        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()

        update.callback_query = query
        context = MagicMock()

        # Mock the slash confirm resolver
        with patch("tools.slash_confirm.resolve") as mock_resolve:
            mock_resolve.return_value = None

            await adapter._handle_callback_query(update, context)

            # Should have called slash confirm handler, not Drumbeat
            mock_resolve.assert_called_once()


if __name__ == "__main__":
    unittest.main()
