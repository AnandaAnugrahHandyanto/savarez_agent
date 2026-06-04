"""
Drumbeat approval handler for Telegram gateway callbacks.

This module handles the minimal DB transitions for Drumbeat draft approvals
triggered from Telegram inline buttons. It is intentionally isolated from
cfo-vm-specific code to remain testable and reusable.

Design principles:
- No platform posting (LinkedIn/X API calls)
- DB operations only (SQLite)
- Safe defaults (non-secret error messages, no crashes on malformed data)
- Unit-testable with temp DBs
"""

import logging
import os
import sqlite3
import time
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class DrumbeatApprovalHandler:
    """
    Handle Telegram callback approval actions for Drumbeat drafts.

    This class is stateless and thread-safe. All operations are atomic
    DB transactions.
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize handler with database path.

        Args:
            db_path: Path to drumbeat.db. If None, uses DRUMBEAT_DB env var
                     or defaults to ~/.hermes/drumbeat/drumbeat.db
        """
        if db_path is None:
            db_path = os.getenv(
                "DRUMBEAT_DB",
                os.path.expanduser("~/.hermes/drumbeat/drumbeat.db")
            )
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection with timeout and row factory."""
        if not os.path.exists(self.db_path):
            logger.warning("Drumbeat DB does not exist: %s", self.db_path)
            raise FileNotFoundError(f"Database not found: {self.db_path}")

        conn = sqlite3.connect(self.db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        return conn

    def handle_approval(
        self,
        draft_id: str,
        action: str,
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Handle a Drumbeat approval action.

        Args:
            draft_id: Draft ID from the callback data
            action: One of 'approve', 'reject', 'skip', 'edit'

        Returns:
            Tuple of (success: bool, message: str, paste_text: Optional[str])
            - success: True if the action was applied successfully
            - message: Human-readable result message (non-secret, suitable for Telegram answer)
            - paste_text: For 'approve' only, the final paste-ready text to edit the message to
        """
        # Validate action
        valid_actions = {"approve", "reject", "skip", "edit"}
        if action not in valid_actions:
            return False, f"Unknown action: {action}", None

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Fetch the draft
            cursor.execute(
                "SELECT id, status, post_text, final_text FROM drafts WHERE id = ?",
                (draft_id,)
            )
            row = cursor.fetchone()

            if not row:
                return False, "Draft not found.", None

            current_status = row["status"]
            post_text = row["post_text"]
            final_text = row["final_text"] if row["final_text"] else ""

            # Check if draft is in pending state
            if current_status != "pending":
                return False, f"Draft is already {current_status}.", None

            # Apply the action
            now = int(time.time())

            if action == "approve":
                new_status = "approved"
                decision = "approved"
                cursor.execute(
                    """
                    UPDATE drafts
                    SET status = ?, hafs_decision = ?, hafs_decision_at = ?
                    WHERE id = ? AND status = 'pending'
                    """,
                    (new_status, decision, now, draft_id)
                )

                if cursor.rowcount == 0:
                    conn.close()
                    return False, "Draft was modified by another process.", None

                conn.commit()
                conn.close()

                # Return paste-ready text (prefer final_text when non-empty, else post_text)
                paste_ready_text = final_text if final_text else post_text
                return True, "✅ Approved", paste_ready_text

            elif action == "reject":
                new_status = "rejected"
                decision = "rejected"
                cursor.execute(
                    """
                    UPDATE drafts
                    SET status = ?, hafs_decision = ?, hafs_decision_at = ?
                    WHERE id = ? AND status = 'pending'
                    """,
                    (new_status, decision, now, draft_id)
                )

                if cursor.rowcount == 0:
                    conn.close()
                    return False, "Draft was modified by another process.", None

                conn.commit()
                conn.close()
                return True, "❌ Rejected", None

            elif action == "skip":
                new_status = "skipped"
                decision = "skipped"
                cursor.execute(
                    """
                    UPDATE drafts
                    SET status = ?, hafs_decision = ?, hafs_decision_at = ?
                    WHERE id = ? AND status = 'pending'
                    """,
                    (new_status, decision, now, draft_id)
                )

                if cursor.rowcount == 0:
                    conn.close()
                    return False, "Draft was modified by another process.", None

                conn.commit()
                conn.close()
                return True, "⏭️ Skipped", None

            elif action == "edit":
                # Edit requested - keep pending, set decision field
                decision = "edit_requested"
                cursor.execute(
                    """
                    UPDATE drafts
                    SET hafs_decision = ?, hafs_decision_at = ?
                    WHERE id = ? AND status = 'pending'
                    """,
                    (decision, now, draft_id)
                )

                if cursor.rowcount == 0:
                    conn.close()
                    return False, "Draft was modified by another process.", None

                conn.commit()
                conn.close()
                return True, "✏️ Edit requested - please revise manually", None

        except FileNotFoundError as e:
            logger.error("Drumbeat DB not found: %s", e)
            return False, "Database not available.", None
        except sqlite3.Error as e:
            logger.error("Database error handling Drumbeat approval: %s", e)
            return False, "Database error occurred.", None
        except Exception as e:
            logger.error("Unexpected error handling Drumbeat approval: %s", e, exc_info=True)
            return False, "An error occurred.", None


def parse_drumbeat_callback_data(data: str) -> Optional[Dict[str, str]]:
    """
    Parse Drumbeat callback data from Telegram inline button.

    Supports two formats:
    1. Forward-compatible: "drumbeat:<action>:<draft_id>"
    2. Backward-compatible: "<action>:<draft_id>" where action is in {approve, reject, skip, edit}

    Args:
        data: Callback data string

    Returns:
        Dict with 'action' and 'draft_id' keys, or None if not a Drumbeat callback
    """
    if data.startswith("drumbeat:"):
        # Forward-compatible format
        parts = data.split(":", 2)
        if len(parts) == 3:
            action = parts[1]
            draft_id = parts[2]
            if action in {"approve", "reject", "skip", "edit"} and draft_id:
                return {"action": action, "draft_id": draft_id}

    # Backward-compatible format (only if it looks like a Drumbeat callback)
    parts = data.split(":", 1)
    if len(parts) == 2:
        action, draft_id = parts
        # Only recognize as Drumbeat if action matches and draft_id has Drumbeat shape
        if action in {"approve", "reject", "skip", "edit"} and draft_id.startswith("d_"):
            return {"action": action, "draft_id": draft_id}

    return None
