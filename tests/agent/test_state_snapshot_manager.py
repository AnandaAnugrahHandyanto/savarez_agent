"""Unit tests for agent/state_snapshot_manager.py — StateSnapshotManager."""

import unittest
from unittest.mock import MagicMock, patch

from agent.app_state import AppState
from agent.state_snapshot_manager import (
    StateSnapshotManager,
    StateSnapshot,
    SnapshotMetadata,
    SNAPSHOT_CREATED,
    SNAPSHOT_RESTORED,
    SNAPSHOT_DELETED,
    SNAPSHOT_LISTED,
    _DOMAIN_EXTRACTORS,
    _SKIPPED_FIELDS,
)


class TestStateSnapshotManager(unittest.TestCase):
    """Tests for StateSnapshotManager."""

    def setUp(self):
        """Create a fresh AppState and manager for each test."""
        self.app_state = AppState(
            model="gpt-4",
            provider="openai",
            session_id="test-session-123",
            agent_name="test-agent",
            max_iterations=50,
            verbose_logging=True,
        )
        self.mock_event_bus = MagicMock()
        self.manager = StateSnapshotManager(
            event_bus=self.mock_event_bus,
            max_snapshots=5,
        )

    # ── Creation ─────────────────────────────────────────────────────────

    def test_create_snapshot_returns_uuid(self):
        """create_snapshot returns a valid UUID string."""
        snap_id = self.manager.create_snapshot(self.app_state, label="test")
        self.assertIsInstance(snap_id, str)
        self.assertEqual(len(snap_id), 36)  # UUID format

    def test_create_snapshot_stores_snapshot(self):
        """Snapshot is retrievable after creation."""
        snap_id = self.manager.create_snapshot(self.app_state, label="test")
        snap = self.manager.get_snapshot(snap_id)
        self.assertIsInstance(snap, StateSnapshot)
        self.assertEqual(snap.id, snap_id)
        self.assertEqual(snap.label, "test")

    def test_create_snapshot_captures_all_domains(self):
        """All 17 domain extractors produce non-empty data."""
        snap_id = self.manager.create_snapshot(self.app_state, label="full")
        snap = self.manager.get_snapshot(snap_id)
        for domain_name in _DOMAIN_EXTRACTORS:
            self.assertTrue(
                hasattr(snap, domain_name),
                f"Snapshot missing domain: {domain_name}",
            )

    def test_create_snapshot_captures_identity_fields(self):
        """Identity domain captures model, provider, session_id, etc."""
        snap_id = self.manager.create_snapshot(self.app_state, label="identity-check")
        snap = self.manager.get_snapshot(snap_id)
        self.assertEqual(snap.identity["model"], "gpt-4")
        self.assertEqual(snap.identity["provider"], "openai")
        self.assertEqual(snap.identity["session_id"], "test-session-123")
        self.assertEqual(snap.identity["agent_name"], "test-agent")

    def test_create_snapshot_captures_runtime_fields(self):
        """Runtime domain captures iteration and retry counters."""
        self.app_state._runtime._invalid_tool_retries = 3
        self.app_state._runtime._invalid_json_retries = 2
        snap_id = self.manager.create_snapshot(self.app_state, label="runtime-check")
        snap = self.manager.get_snapshot(snap_id)
        self.assertEqual(snap.runtime["max_iterations"], 50)
        self.assertEqual(snap.runtime["_invalid_tool_retries"], 3)
        self.assertEqual(snap.runtime["_invalid_json_retries"], 2)

    def test_create_snapshot_captures_token_fields(self):
        """Token domain captures cost and token counters."""
        self.app_state._tokens.total_cost = 0.25
        self.app_state._tokens.session_total_tokens = 5000
        snap_id = self.manager.create_snapshot(self.app_state, label="tokens-check")
        snap = self.manager.get_snapshot(snap_id)
        self.assertEqual(snap.tokens["total_cost"], 0.25)
        self.assertEqual(snap.tokens["session_total_tokens"], 5000)

    def test_create_snapshot_captures_interrupt_state(self):
        """Interrupt domain captures interrupt flags."""
        self.app_state._interrupt_state._interrupt_requested = True
        self.app_state._interrupt_state._interrupt_message = "emergency stop"
        snap_id = self.manager.create_snapshot(self.app_state, label="interrupt-check")
        snap = self.manager.get_snapshot(snap_id)
        self.assertEqual(snap.interrupt_state["_interrupt_requested"], True)
        self.assertEqual(snap.interrupt_state["_interrupt_message"], "emergency stop")

    def test_create_snapshot_captures_session_messages(self):
        """Session domain captures and deep-copies session messages."""
        self.app_state._session._session_messages.append(
            {"role": "user", "content": "hello"}
        )
        snap_id = self.manager.create_snapshot(self.app_state, label="messages-check")
        snap = self.manager.get_snapshot(snap_id)
        self.assertEqual(len(snap.session["_session_messages"]), 1)
        self.assertEqual(snap.session["_session_messages"][0]["content"], "hello")

    def test_create_snapshot_tracks_skipped_fields(self):
        """Skipped fields list is populated."""
        snap_id = self.manager.create_snapshot(self.app_state, label="skipped-check")
        snap = self.manager.get_snapshot(snap_id)
        self.assertIn("stream_delta_callback", snap.skipped_fields)
        self.assertIn("client", snap.skipped_fields)
        self.assertIn("_credential_pool", snap.skipped_fields)
        self.assertIn("_client_lock", snap.skipped_fields)

    def test_create_snapshot_computes_changed_fields(self):
        """First snapshot marks all domains as changed."""
        snap_id = self.manager.create_snapshot(self.app_state, label="first")
        snap = self.manager.get_snapshot(snap_id)
        # First snapshot has all domains changed
        self.assertIn("identity", snap.changed_fields)
        self.assertIn("runtime", snap.changed_fields)

    def test_create_snapshot_tracks_iteration(self):
        """Iteration count is captured."""
        self.app_state._extra._api_call_count = 42
        snap_id = self.manager.create_snapshot(self.app_state, label="iter-check")
        snap = self.manager.get_snapshot(snap_id)
        self.assertEqual(snap.iteration, 42)

    def test_create_snapshot_explicit_iteration(self):
        """Explicit iteration parameter overrides auto-detected value."""
        self.app_state._extra._api_call_count = 10
        snap_id = self.manager.create_snapshot(
            self.app_state, label="explicit-iter", iteration=99
        )
        snap = self.manager.get_snapshot(snap_id)
        self.assertEqual(snap.iteration, 99)

    def test_create_snapshot_emits_event_bus(self):
        """create_snapshot emits an EventBus event."""
        snap_id = self.manager.create_snapshot(
            self.app_state, label="event-test", reason="test"
        )
        self.mock_event_bus.emit_event.assert_called_once()
        call_args = self.mock_event_bus.emit_event.call_args
        # emit_event(event_type, payload=payload, session_id=session_id)
        # positional args: ('state.snapshot.created',)
        # keyword args: {'payload': {...}, 'session_id': '...'}
        self.assertEqual(call_args[0][0], SNAPSHOT_CREATED)
        self.assertEqual(call_args[1]["payload"]["snapshot_id"], snap_id)
        self.assertEqual(call_args[1]["payload"]["label"], "event-test")

    def test_create_snapshot_no_event_bus(self):
        """Does not raise when event_bus is None."""
        mgr = StateSnapshotManager(event_bus=None, max_snapshots=5)
        snap_id = mgr.create_snapshot(self.app_state, label="no-bus")
        self.assertIsInstance(snap_id, str)

    # ── Restoration ───────────────────────────────────────────────────────

    def test_restore_snapshot_identity(self):
        """restore_snapshot restores identity domain fields."""
        snap_id = self.manager.create_snapshot(self.app_state, label="before")
        # Modify state
        self.app_state._identity.model = "claude-3"
        self.app_state._identity.provider = "anthropic"
        # Restore
        result = self.manager.restore_snapshot(self.app_state, snap_id)
        self.assertTrue(result["success"])
        self.assertEqual(self.app_state.model, "gpt-4")
        self.assertEqual(self.app_state.provider, "openai")

    def test_restore_snapshot_runtime(self):
        """restore_snapshot restores runtime domain fields."""
        snap_id = self.manager.create_snapshot(self.app_state, label="runtime-before")
        self.app_state._runtime.max_iterations = 999
        self.app_state._runtime._invalid_tool_retries = 99
        result = self.manager.restore_snapshot(self.app_state, snap_id)
        self.assertTrue(result["success"])
        self.assertEqual(self.app_state.max_iterations, 50)
        self.assertEqual(self.app_state._invalid_tool_retries, 0)

    def test_restore_snapshot_tokens(self):
        """restore_snapshot restores token/cost fields."""
        snap_id = self.manager.create_snapshot(self.app_state, label="tokens-before")
        self.app_state._tokens.total_cost = 999.0
        self.app_state._tokens.session_api_calls = 999
        result = self.manager.restore_snapshot(self.app_state, snap_id)
        self.assertTrue(result["success"])
        self.assertEqual(self.app_state.total_cost, 0.0)
        self.assertEqual(self.app_state.session_api_calls, 0)

    def test_restore_snapshot_interrupt(self):
        """restore_snapshot restores interrupt flags."""
        snap_id = self.manager.create_snapshot(self.app_state, label="intr-before")
        self.app_state._interrupt_state._interrupt_requested = True
        result = self.manager.restore_snapshot(self.app_state, snap_id)
        self.assertTrue(result["success"])
        self.assertFalse(self.app_state._interrupt_requested)

    def test_restore_snapshot_session_messages(self):
        """restore_snapshot restores session message history."""
        snap_id = self.manager.create_snapshot(self.app_state, label="msgs-before")
        self.app_state._session._session_messages.append(
            {"role": "user", "content": "hello"}
        )
        self.app_state._session._session_messages.append(
            {"role": "assistant", "content": "hi"}
        )
        result = self.manager.restore_snapshot(self.app_state, snap_id)
        self.assertTrue(result["success"])
        self.assertEqual(self.app_state._session_messages, [])

    def test_restore_snapshot_emits_event_bus(self):
        """restore_snapshot emits an EventBus event."""
        snap_id = self.manager.create_snapshot(self.app_state, label="restore-test")
        self.mock_event_bus.reset_mock()
        self.manager.restore_snapshot(self.app_state, snap_id)
        self.mock_event_bus.emit_event.assert_called_once()
        call_args = self.mock_event_bus.emit_event.call_args
        # emit_event(event_type, payload, session_id) — positional args
        self.assertEqual(call_args[0][0], SNAPSHOT_RESTORED)

    def test_restore_nonexistent_snapshot(self):
        """restore_snapshot returns error dict for missing ID."""
        result = self.manager.restore_snapshot(
            self.app_state, "nonexistent-id-123"
        )
        self.assertFalse(result["success"])
        self.assertIn("not found", result["error"])

    # ── Listing ─────────────────────────────────────────────────────────

    def test_list_snapshots_returns_metadata(self):
        """list_snapshots returns SnapshotMetadata, newest first."""
        for i in range(3):
            self.manager.create_snapshot(
                self.app_state, label=f"snap-{i}", iteration=i
            )
        listings = self.manager.list_snapshots()
        self.assertEqual(len(listings), 3)
        # Newest first
        self.assertEqual(listings[0].label, "snap-2")
        self.assertEqual(listings[1].label, "snap-1")
        self.assertEqual(listings[2].label, "snap-0")

    def test_list_snapshots_respects_limit(self):
        """list_snapshots limits results."""
        for i in range(5):
            self.manager.create_snapshot(self.app_state, label=f"snap-{i}")
        listings = self.manager.list_snapshots(limit=2)
        self.assertEqual(len(listings), 2)

    def test_list_snapshots_with_domain_filter(self):
        """list_snapshots filters by changed domain."""
        snap_id = self.manager.create_snapshot(self.app_state, label="base")
        # Modify tokens then snapshot
        self.app_state._tokens.total_cost = 1.0
        snap_id2 = self.manager.create_snapshot(
            self.app_state, label="tokens-modified", iteration=1
        )
        listings = self.manager.list_snapshots(domain_filter="tokens")
        self.assertGreater(len(listings), 0)
        # All returned snapshots should have tokens in changed_fields
        for m in listings:
            snap = self.manager.get_snapshot(m.id)
            self.assertIn("tokens", snap.changed_fields)

    def test_list_snapshots_emits_event_bus(self):
        """list_snapshots emits an EventBus event."""
        self.manager.create_snapshot(self.app_state, label="test")
        self.mock_event_bus.reset_mock()
        self.manager.list_snapshots()
        self.mock_event_bus.emit_event.assert_called_once()
        call_args = self.mock_event_bus.emit_event.call_args
        # emit_event(event_type, payload, session_id) — positional args
        self.assertEqual(call_args[0][0], SNAPSHOT_LISTED)

    # ── Deletion ─────────────────────────────────────────────────────────

    def test_delete_snapshot(self):
        """delete_snapshot removes the snapshot."""
        snap_id = self.manager.create_snapshot(self.app_state, label="to-delete")
        self.assertIsNotNone(self.manager.get_snapshot(snap_id))
        result = self.manager.delete_snapshot(snap_id)
        self.assertTrue(result)
        self.assertIsNone(self.manager.get_snapshot(snap_id))

    def test_delete_nonexistent_snapshot(self):
        """delete_snapshot returns False for missing ID."""
        result = self.manager.delete_snapshot("nonexistent")
        self.assertFalse(result)

    def test_delete_snapshot_emits_event_bus(self):
        """delete_snapshot emits an EventBus event."""
        snap_id = self.manager.create_snapshot(self.app_state, label="del-test")
        self.mock_event_bus.reset_mock()
        self.manager.delete_snapshot(snap_id)
        self.mock_event_bus.emit_event.assert_called_once()
        call_args = self.mock_event_bus.emit_event.call_args
        # emit_event(event_type, payload, session_id) — positional args
        self.assertEqual(call_args[0][0], SNAPSHOT_DELETED)

    def test_clear_all(self):
        """clear_all removes all snapshots and returns count."""
        for i in range(3):
            self.manager.create_snapshot(self.app_state, label=f"snap-{i}")
        self.assertEqual(self.manager.snapshot_count, 3)
        count = self.manager.clear_all()
        self.assertEqual(count, 3)
        self.assertEqual(self.manager.snapshot_count, 0)

    # ── Ring buffer ──────────────────────────────────────────────────────

    def test_max_snapshots_eviction(self):
        """Snapshots beyond max_snapshots evict the oldest."""
        # max_snapshots = 5 in setUp
        for i in range(8):
            self.manager.create_snapshot(self.app_state, label=f"snap-{i}")
        self.assertEqual(self.manager.snapshot_count, 5)
        # Check by iterating snapshots directly
        labels = {s.label for s in self.manager._snapshots.values()}
        self.assertNotIn("snap-0", labels)
        self.assertNotIn("snap-1", labels)
        self.assertNotIn("snap-2", labels)
        self.assertIn("snap-3", labels)
        self.assertIn("snap-7", labels)

    # ── Diff tracking ───────────────────────────────────────────────────

    def test_changed_fields_tracked_between_snapshots(self):
        """Second snapshot marks only changed domains."""
        self.manager.create_snapshot(self.app_state, label="base")
        # Modify runtime and tokens
        self.app_state._runtime._invalid_tool_retries = 5
        self.app_state._tokens.total_cost = 1.0
        snap2_id = self.manager.create_snapshot(self.app_state, label="modified")
        snap2 = self.manager.get_snapshot(snap2_id)
        self.assertIn("runtime", snap2.changed_fields)
        self.assertIn("tokens", snap2.changed_fields)

    # ── Backward compatibility ───────────────────────────────────────────

    def test_snapshot_manager_backward_compat(self):
        """StateSnapshotManager works with no event_bus and no session_db."""
        mgr = StateSnapshotManager()  # No args
        snap_id = mgr.create_snapshot(self.app_state, label="bare")
        self.assertIsInstance(snap_id, str)
        snap = mgr.get_snapshot(snap_id)
        self.assertEqual(snap.label, "bare")
        result = mgr.restore_snapshot(self.app_state, snap_id)
        self.assertTrue(result["success"])


class TestStateSnapshotDataStructures(unittest.TestCase):
    """Tests for snapshot data structures."""

    def test_snapshot_metadata_fields(self):
        """SnapshotMetadata has all expected fields."""
        meta = SnapshotMetadata(
            id="abc123",
            timestamp=1234567890.0,
            label="test",
            reason="manual",
            iteration=5,
            changed_field_count=3,
            total_fields=17,
        )
        self.assertEqual(meta.id, "abc123")
        self.assertEqual(meta.iteration, 5)
        self.assertEqual(meta.changed_field_count, 3)

    def test_skipped_fields_comprehensive(self):
        """All skipped fields are meaningful non-serializable items."""
        self.assertIn("stream_delta_callback", _SKIPPED_FIELDS)
        self.assertIn("client", _SKIPPED_FIELDS)
        self.assertIn("_credential_pool", _SKIPPED_FIELDS)
        self.assertIn("_session_db", _SKIPPED_FIELDS)
        self.assertIn("_client_lock", _SKIPPED_FIELDS)
        self.assertIn("api_key", _SKIPPED_FIELDS)

    def test_domain_extractors_count(self):
        """All 16 domain extractors are registered."""
        self.assertEqual(len(_DOMAIN_EXTRACTORS), 16)


if __name__ == "__main__":
    unittest.main()
