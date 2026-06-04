"""
Unit tests for Drumbeat approval handler.

Tests the Drumbeat callback handler in isolation with a temporary SQLite database,
covering all approval actions, edge cases, and error handling.
"""

import os
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

from gateway.drumbeat_handler import DrumbeatApprovalHandler, parse_drumbeat_callback_data


class TestDrumbeatCallbackParsing(unittest.TestCase):
    """Test callback data parsing."""

    def test_forward_compatible_format(self):
        """Test drumbeat:<action>:<draft_id> format."""
        result = parse_drumbeat_callback_data("drumbeat:approve:d_1234567890_1_abcd")
        self.assertIsNotNone(result)
        self.assertEqual(result["action"], "approve")
        self.assertEqual(result["draft_id"], "d_1234567890_1_abcd")

        result = parse_drumbeat_callback_data("drumbeat:reject:d_9999_2_xyz")
        self.assertIsNotNone(result)
        self.assertEqual(result["action"], "reject")
        self.assertEqual(result["draft_id"], "d_9999_2_xyz")

        result = parse_drumbeat_callback_data("drumbeat:skip:d_test")
        self.assertIsNotNone(result)
        self.assertEqual(result["action"], "skip")

        result = parse_drumbeat_callback_data("drumbeat:edit:d_edit_test")
        self.assertIsNotNone(result)
        self.assertEqual(result["action"], "edit")

    def test_backward_compatible_format(self):
        """Test <action>:<draft_id> format (only with d_ prefix)."""
        result = parse_drumbeat_callback_data("approve:d_1234567890_1_abcd")
        self.assertIsNotNone(result)
        self.assertEqual(result["action"], "approve")
        self.assertEqual(result["draft_id"], "d_1234567890_1_abcd")

        result = parse_drumbeat_callback_data("reject:d_test")
        self.assertIsNotNone(result)
        self.assertEqual(result["action"], "reject")

    def test_backward_compat_rejects_non_drumbeat_ids(self):
        """Backward-compatible format requires d_ prefix to avoid hijacking."""
        # Should NOT match - no d_ prefix
        result = parse_drumbeat_callback_data("approve:some_random_id")
        self.assertIsNone(result)

        result = parse_drumbeat_callback_data("reject:12345")
        self.assertIsNone(result)

    def test_invalid_action(self):
        """Invalid actions should not parse."""
        result = parse_drumbeat_callback_data("drumbeat:invalid:d_123")
        self.assertIsNone(result)

        result = parse_drumbeat_callback_data("delete:d_123")
        self.assertIsNone(result)

    def test_non_drumbeat_callbacks(self):
        """Non-Drumbeat callbacks should return None."""
        # Existing callback types
        self.assertIsNone(parse_drumbeat_callback_data("ea:approve:123"))
        self.assertIsNone(parse_drumbeat_callback_data("sc:once:confirm_123"))
        self.assertIsNone(parse_drumbeat_callback_data("mp:model_name"))
        self.assertIsNone(parse_drumbeat_callback_data("update_prompt:y"))
        self.assertIsNone(parse_drumbeat_callback_data("random_data"))
        self.assertIsNone(parse_drumbeat_callback_data(""))

    def test_malformed_data(self):
        """Malformed data should return None."""
        self.assertIsNone(parse_drumbeat_callback_data("drumbeat:"))
        self.assertIsNone(parse_drumbeat_callback_data("drumbeat:approve:"))
        self.assertIsNone(parse_drumbeat_callback_data("drumbeat::d_123"))
        self.assertIsNone(parse_drumbeat_callback_data(":d_123"))


class TestDrumbeatApprovalHandler(unittest.TestCase):
    """Test Drumbeat approval handler with real SQLite database."""

    def setUp(self):
        """Create a temporary database with Drumbeat schema."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_drumbeat.db")

        # Create the database with Drumbeat schema
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create candidates table (referenced by drafts)
        cursor.execute("""
            CREATE TABLE candidates (
                id INTEGER PRIMARY KEY
            )
        """)
        cursor.execute("INSERT INTO candidates (id) VALUES (1)")

        # Create drafts table
        cursor.execute("""
            CREATE TABLE drafts (
                id               TEXT PRIMARY KEY,
                candidate_id     INTEGER NOT NULL,
                post_text        TEXT NOT NULL,
                final_text       TEXT,
                prompt_version   TEXT NOT NULL,
                generated_at     INTEGER NOT NULL,
                status           TEXT NOT NULL DEFAULT 'pending',
                hafs_decision_at INTEGER,
                hafs_decision    TEXT,
                FOREIGN KEY (candidate_id) REFERENCES candidates(id)
            )
        """)

        conn.commit()
        conn.close()

        self.handler = DrumbeatApprovalHandler(db_path=self.db_path)

    def tearDown(self):
        """Clean up temporary database."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _insert_draft(self, draft_id: str, status: str = "pending", post_text: str = "Test post", final_text: str = None):
        """Helper to insert a test draft."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO drafts (id, candidate_id, post_text, final_text, prompt_version, generated_at, status)
            VALUES (?, 1, ?, ?, 'v1', ?, ?)
            """,
            (draft_id, post_text, final_text, int(time.time()), status)
        )
        conn.commit()
        conn.close()

    def _get_draft(self, draft_id: str):
        """Helper to get draft state."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def test_approve_pending_draft(self):
        """Test approving a pending draft."""
        draft_id = "d_test_approve"
        post_text = "This is a test post for approval."
        self._insert_draft(draft_id, post_text=post_text)

        success, message, paste_text = self.handler.handle_approval(draft_id, "approve")

        self.assertTrue(success)
        self.assertEqual(message, "✅ Approved")
        self.assertEqual(paste_text, post_text)

        # Check DB state
        draft = self._get_draft(draft_id)
        self.assertEqual(draft["status"], "approved")
        self.assertEqual(draft["hafs_decision"], "approved")
        self.assertIsNotNone(draft["hafs_decision_at"])
        self.assertGreater(draft["hafs_decision_at"], 0)

    def test_approve_with_final_text_prefers_final_text(self):
        """Test that approval returns final_text when present and non-empty."""
        draft_id = "d_test_final_text"
        post_text = "Original draft text"
        final_text = "This is the final, polished version ready to paste"
        self._insert_draft(draft_id, post_text=post_text, final_text=final_text)

        success, message, paste_text = self.handler.handle_approval(draft_id, "approve")

        self.assertTrue(success)
        self.assertEqual(message, "✅ Approved")
        # Should return final_text, not post_text
        self.assertEqual(paste_text, final_text)
        self.assertNotEqual(paste_text, post_text)

        # Check DB state
        draft = self._get_draft(draft_id)
        self.assertEqual(draft["status"], "approved")
        self.assertEqual(draft["hafs_decision"], "approved")

    def test_approve_with_empty_final_text_falls_back_to_post_text(self):
        """Test that approval falls back to post_text when final_text is empty or NULL."""
        # Test with empty string
        draft_id_empty = "d_test_empty_final"
        post_text_empty = "Original post text for empty final_text case"
        self._insert_draft(draft_id_empty, post_text=post_text_empty, final_text="")

        success, message, paste_text = self.handler.handle_approval(draft_id_empty, "approve")

        self.assertTrue(success)
        self.assertEqual(paste_text, post_text_empty)

        # Test with NULL (None)
        draft_id_null = "d_test_null_final"
        post_text_null = "Original post text for NULL final_text case"
        self._insert_draft(draft_id_null, post_text=post_text_null, final_text=None)

        success, message, paste_text = self.handler.handle_approval(draft_id_null, "approve")

        self.assertTrue(success)
        self.assertEqual(paste_text, post_text_null)

    def test_reject_pending_draft(self):
        """Test rejecting a pending draft."""
        draft_id = "d_test_reject"
        self._insert_draft(draft_id)

        success, message, paste_text = self.handler.handle_approval(draft_id, "reject")

        self.assertTrue(success)
        self.assertEqual(message, "❌ Rejected")
        self.assertIsNone(paste_text)

        draft = self._get_draft(draft_id)
        self.assertEqual(draft["status"], "rejected")
        self.assertEqual(draft["hafs_decision"], "rejected")
        self.assertIsNotNone(draft["hafs_decision_at"])

    def test_skip_pending_draft(self):
        """Test skipping a pending draft."""
        draft_id = "d_test_skip"
        self._insert_draft(draft_id)

        success, message, paste_text = self.handler.handle_approval(draft_id, "skip")

        self.assertTrue(success)
        self.assertEqual(message, "⏭️ Skipped")
        self.assertIsNone(paste_text)

        draft = self._get_draft(draft_id)
        self.assertEqual(draft["status"], "skipped")
        self.assertEqual(draft["hafs_decision"], "skipped")
        self.assertIsNotNone(draft["hafs_decision_at"])

    def test_edit_pending_draft(self):
        """Test edit request on pending draft (keeps status pending)."""
        draft_id = "d_test_edit"
        self._insert_draft(draft_id)

        success, message, paste_text = self.handler.handle_approval(draft_id, "edit")

        self.assertTrue(success)
        self.assertEqual(message, "✏️ Edit requested - please revise manually")
        self.assertIsNone(paste_text)

        draft = self._get_draft(draft_id)
        self.assertEqual(draft["status"], "pending")  # Stays pending!
        self.assertEqual(draft["hafs_decision"], "edit_requested")
        self.assertIsNotNone(draft["hafs_decision_at"])

    def test_draft_not_found(self):
        """Test handling of non-existent draft."""
        success, message, paste_text = self.handler.handle_approval("d_nonexistent", "approve")

        self.assertFalse(success)
        self.assertEqual(message, "Draft not found.")
        self.assertIsNone(paste_text)

    def test_draft_already_approved(self):
        """Test that already-approved drafts cannot be changed."""
        draft_id = "d_already_approved"
        self._insert_draft(draft_id, status="approved")

        success, message, paste_text = self.handler.handle_approval(draft_id, "reject")

        self.assertFalse(success)
        self.assertEqual(message, "Draft is already approved.")
        self.assertIsNone(paste_text)

        # Status should remain approved
        draft = self._get_draft(draft_id)
        self.assertEqual(draft["status"], "approved")

    def test_draft_already_rejected(self):
        """Test that already-rejected drafts cannot be changed."""
        draft_id = "d_already_rejected"
        self._insert_draft(draft_id, status="rejected")

        success, message, paste_text = self.handler.handle_approval(draft_id, "approve")

        self.assertFalse(success)
        self.assertEqual(message, "Draft is already rejected.")
        self.assertIsNone(paste_text)

    def test_invalid_action(self):
        """Test handling of invalid action."""
        draft_id = "d_invalid_action"
        self._insert_draft(draft_id)

        success, message, paste_text = self.handler.handle_approval(draft_id, "delete")

        self.assertFalse(success)
        self.assertIn("Unknown action", message)
        self.assertIsNone(paste_text)

        # Draft should remain unchanged
        draft = self._get_draft(draft_id)
        self.assertEqual(draft["status"], "pending")

    def test_db_not_found(self):
        """Test handling of missing database."""
        handler = DrumbeatApprovalHandler(db_path="/nonexistent/path/drumbeat.db")

        success, message, paste_text = handler.handle_approval("d_test", "approve")

        self.assertFalse(success)
        self.assertEqual(message, "Database not available.")
        self.assertIsNone(paste_text)

    def test_default_db_path(self):
        """Test that handler uses DRUMBEAT_DB env var."""
        os.environ["DRUMBEAT_DB"] = self.db_path
        try:
            handler = DrumbeatApprovalHandler()
            self.assertEqual(handler.db_path, self.db_path)
        finally:
            del os.environ["DRUMBEAT_DB"]

    def test_concurrent_modification_protection(self):
        """Test that WHERE status='pending' clause prevents race conditions."""
        draft_id = "d_concurrent"
        self._insert_draft(draft_id)

        # First approval should succeed
        success1, message1, paste_text1 = self.handler.handle_approval(draft_id, "approve")
        self.assertTrue(success1)

        # Second approval on the now-approved draft should fail
        success2, message2, paste_text2 = self.handler.handle_approval(draft_id, "reject")
        self.assertFalse(success2)
        self.assertIn("already approved", message2.lower())

        # Status should remain approved (not changed to rejected)
        draft = self._get_draft(draft_id)
        self.assertEqual(draft["status"], "approved")
        self.assertEqual(draft["hafs_decision"], "approved")


class TestDrumbeatCallbackIntegration(unittest.TestCase):
    """Integration tests simulating the full callback flow."""

    def setUp(self):
        """Create a temporary database."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_drumbeat.db")

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

        self.handler = DrumbeatApprovalHandler(db_path=self.db_path)

    def tearDown(self):
        """Clean up."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _insert_draft(self, draft_id: str, post_text: str = "Test post"):
        """Helper to insert a draft."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO drafts (id, candidate_id, post_text, prompt_version, generated_at, status) "
            "VALUES (?, 1, ?, 'v1', ?, 'pending')",
            (draft_id, post_text, int(time.time()))
        )
        conn.commit()
        conn.close()

    def test_full_approval_flow(self):
        """Simulate complete approval flow from callback data to DB update."""
        draft_id = "d_1779462821_36_7ece5f53b5"
        post_text = "Full integration test post content."
        self._insert_draft(draft_id, post_text)

        # Parse callback data
        callback_data = f"drumbeat:approve:{draft_id}"
        parsed = parse_drumbeat_callback_data(callback_data)
        self.assertIsNotNone(parsed)

        # Handle approval
        success, message, paste_text = self.handler.handle_approval(
            parsed["draft_id"],
            parsed["action"]
        )

        self.assertTrue(success)
        self.assertEqual(paste_text, post_text)

        # Verify DB state
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,))
        draft = cursor.fetchone()
        conn.close()

        self.assertEqual(draft["status"], "approved")
        self.assertEqual(draft["hafs_decision"], "approved")

    def test_backward_compatible_callback(self):
        """Test backward-compatible callback format."""
        draft_id = "d_old_format_test"
        self._insert_draft(draft_id)

        callback_data = f"approve:{draft_id}"
        parsed = parse_drumbeat_callback_data(callback_data)
        self.assertIsNotNone(parsed)

        success, message, paste_text = self.handler.handle_approval(
            parsed["draft_id"],
            parsed["action"]
        )

        self.assertTrue(success)


if __name__ == "__main__":
    unittest.main()
