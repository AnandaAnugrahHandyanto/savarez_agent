"""Unit tests for agent/shared_state.py — SharedStateStore sub-agent state sharing."""

import unittest
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from agent.shared_state import SharedStateStore, StateChangeRecord
from agent.hermes.analytics import EventBus


class TestSharedStateStoreBasics(unittest.TestCase):
    """Basic read/write/clear operations."""

    def test_empty_store(self):
        store = SharedStateStore(session_id="test-empty")
        self.assertEqual(len(store), 0)
        self.assertEqual(store.keys(), [])
        self.assertIsNone(store.read("nonexistent"))
        self.assertEqual(store.read("nonexistent", "default"), "default")

    def test_write_and_read(self):
        store = SharedStateStore(session_id="test-write-read")
        store.write("key1", "value1", writer_id="test")
        self.assertEqual(store.read("key1"), "value1")
        self.assertEqual(len(store), 1)
        self.assertIn("key1", store.keys())

    def test_overwrite(self):
        store = SharedStateStore(session_id="test-overwrite")
        store.write("key1", "old", writer_id="w1")
        store.write("key1", "new", writer_id="w2")
        self.assertEqual(store.read("key1"), "new")

    def test_clear_key(self):
        store = SharedStateStore(session_id="test-clear-key")
        store.write("k1", "v1", writer_id="test")
        store.write("k2", "v2", writer_id="test")
        store.clear(key="k1")
        self.assertNotIn("k1", store.keys())
        self.assertIn("k2", store.keys())
        self.assertEqual(len(store), 1)

    def test_clear_all(self):
        store = SharedStateStore(session_id="test-clear-all")
        store.write("k1", "v1", writer_id="test")
        store.write("k2", "v2", writer_id="test")
        store.clear()
        self.assertEqual(len(store), 0)
        self.assertEqual(store.keys(), [])

    def test_get_all(self):
        store = SharedStateStore(session_id="test-get-all")
        store.write("k1", {"a": 1}, writer_id="test")
        store.write("k2", [1, 2, 3], writer_id="test")
        all_data = store.get_all()
        self.assertEqual(all_data["k1"], {"a": 1})
        self.assertEqual(all_data["k2"], [1, 2, 3])

    def test_seq_increment(self):
        store = SharedStateStore(session_id="test-seq")
        self.assertEqual(store.seq, 0)
        store.write("k1", "v1", writer_id="test")
        self.assertEqual(store.seq, 1)
        store.write("k2", "v2", writer_id="test")
        self.assertEqual(store.seq, 2)

    def test_repr(self):
        store = SharedStateStore(session_id="sid123")
        store.write("k1", "v1", writer_id="test")
        r = repr(store)
        self.assertIn("sid123", r)
        self.assertIn("k1", r)


class TestSharedStateStoreEventBus(unittest.TestCase):
    """EventBus integration tests."""

    def test_attach_detach(self):
        bus = EventBus()
        store = SharedStateStore(session_id="test-attach")
        self.assertIsNone(store._event_bus)

        store.attach_to_event_bus(bus)
        self.assertIs(store._event_bus, bus)

        # Idempotent: attaching again doesn't duplicate subscriptions
        store.attach_to_event_bus(bus)

        store.detach_from_event_bus()
        self.assertIsNone(store._event_bus)

    def test_attach_idempotent(self):
        bus = EventBus()
        store = SharedStateStore(session_id="test-idempotent")
        store.attach_to_event_bus(bus)
        store.attach_to_event_bus(bus)
        # Should still only have one subscription per event type
        self.assertEqual(bus.get_handler_count("shared_state.write"), 1)
        self.assertEqual(bus.get_handler_count("shared_state.read"), 1)

    def test_write_event_emits_changed(self):
        bus = EventBus()
        store = SharedStateStore(session_id="test-write-emit")
        store.attach_to_event_bus(bus)

        received = []

        def handler(event):
            received.append(event.payload)

        bus.subscribe("shared_state.changed", handler)

        store.write("key1", {"data": 123}, writer_id="writer-1")

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["key"], "key1")
        self.assertEqual(received[0]["value"], {"data": 123})
        self.assertEqual(received[0]["writer_id"], "writer-1")
        self.assertEqual(received[0]["old_value"], None)  # First write
        self.assertIn("timestamp", received[0])
        self.assertIn("seq", received[0])

    def test_write_event_overwrite_emits_old_value(self):
        bus = EventBus()
        store = SharedStateStore(session_id="test-old-value")
        store.attach_to_event_bus(bus)

        received = []

        def handler(event):
            received.append(event.payload)

        bus.subscribe("shared_state.changed", handler)

        store.write("key1", "first", writer_id="w1")
        store.write("key1", "second", writer_id="w2")

        self.assertEqual(len(received), 2)
        self.assertEqual(received[1]["old_value"], "first")
        self.assertEqual(received[1]["value"], "second")

    def test_read_event_emits_changed(self):
        bus = EventBus()
        store = SharedStateStore(session_id="test-read-emit")
        store.attach_to_event_bus(bus)

        received = []

        def handler(event):
            received.append(event.payload)

        bus.subscribe("shared_state.changed", handler)

        store.write("key1", "value1", writer_id="writer")
        received.clear()  # Clear write notification

        # Simulate a read event (as if emitted by a sub-agent)
        bus.emit_event("shared_state.read", {"key": "key1", "reader_id": "reader-1"})

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["key"], "key1")
        self.assertEqual(received[0]["value"], "value1")
        self.assertTrue(received[0]["is_read"])

    def test_sub_agent_write_via_event(self):
        """Simulate a sub-agent emitting a write event."""
        bus = EventBus()
        store = SharedStateStore(session_id="test-subagent-write")
        store.attach_to_event_bus(bus)

        # Sub-agent emits a write event (no direct store access)
        bus.emit_event("shared_state.write", {
            "key": "findings",
            "value": {"step": 1, "result": "partial"},
            "writer_id": "subagent-0",
        })

        # Store should have the value
        self.assertEqual(store.read("findings"), {"step": 1, "result": "partial"})

        # Changed event should have been emitted
        changed_events = []
        def changed_handler(event):
            changed_events.append(event.payload)
        bus.subscribe("shared_state.changed", changed_handler)

        bus.emit_event("shared_state.write", {
            "key": "findings",
            "value": {"step": 2, "result": "final"},
            "writer_id": "subagent-0",
        })

        self.assertEqual(len(changed_events), 1)
        self.assertEqual(changed_events[0]["value"], {"step": 2, "result": "final"})
        self.assertEqual(changed_events[0]["old_value"], {"step": 1, "result": "partial"})

    def test_cleared_event(self):
        bus = EventBus()
        store = SharedStateStore(session_id="test-cleared")
        store.attach_to_event_bus(bus)

        received = []

        def handler(event):
            received.append(event.payload)

        bus.subscribe("shared_state.cleared", handler)

        store.write("k1", "v1", writer_id="test")
        store.clear(key="k1")

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["key"], "k1")


class TestSharedStateStoreSubscribers(unittest.TestCase):
    """Subscriber API tests."""

    def test_key_subscriber(self):
        store = SharedStateStore(session_id="test-key-sub")
        bus = EventBus()
        store.attach_to_event_bus(bus)

        received = []

        def handler(record):
            received.append(record)

        store.subscribe("target_key", handler)
        store.write("target_key", "value1", writer_id="w1")

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].key, "target_key")
        self.assertEqual(received[0].value, "value1")

        # Other keys don't trigger handler
        store.write("other_key", "other", writer_id="w2")
        self.assertEqual(len(received), 1)  # Still 1

    def test_global_subscriber(self):
        store = SharedStateStore(session_id="test-global-sub")
        bus = EventBus()
        store.attach_to_event_bus(bus)

        received = []

        def handler(record):
            received.append(record)

        store.subscribe("*", handler)
        store.write("k1", "v1", writer_id="w1")
        store.write("k2", "v2", writer_id="w2")

        self.assertEqual(len(received), 2)
        self.assertEqual(received[0].key, "k1")
        self.assertEqual(received[1].key, "k2")

    def test_unsubscribe(self):
        store = SharedStateStore(session_id="test-unsub")
        bus = EventBus()
        store.attach_to_event_bus(bus)

        received = []

        def handler(record):
            received.append(record)

        store.subscribe("key1", handler)
        store.write("key1", "v1", writer_id="w1")
        self.assertEqual(len(received), 1)

        store.unsubscribe("key1", handler)
        store.write("key1", "v2", writer_id="w2")
        self.assertEqual(len(received), 1)  # No new events


class TestSharedStateStoreThreadSafety(unittest.TestCase):
    """Thread-safety tests for concurrent writes."""

    def test_concurrent_writes(self):
        store = SharedStateStore(session_id="test-concurrent")
        bus = EventBus()
        store.attach_to_event_bus(bus)

        def writer(thread_id):
            for i in range(50):
                store.write(f"key_{thread_id}_{i}", f"value_{thread_id}_{i}", writer_id=f"writer-{thread_id}")

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(writer, i) for i in range(4)]
            for f in as_completed(futures):
                f.result()

        self.assertEqual(len(store), 200)
        self.assertEqual(store.seq, 200)

    def test_concurrent_read_write(self):
        store = SharedStateStore(session_id="test-read-write")
        bus = EventBus()
        store.attach_to_event_bus(bus)

        results = []
        lock = threading.Lock()

        def writer(thread_id):
            for i in range(20):
                store.write("shared_key", {"thread": thread_id, "i": i}, writer_id=f"w{thread_id}")

        def reader(thread_id):
            for i in range(20):
                val = store.read("shared_key")
                with lock:
                    results.append((thread_id, val))

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            futures.append(executor.submit(writer, 0))
            futures.append(executor.submit(writer, 1))
            futures.append(executor.submit(reader, 2))
            futures.append(executor.submit(reader, 3))
            for f in as_completed(futures):
                f.result()

        # All reads should have gotten some valid value
        for thread_id, val in results:
            self.assertIsInstance(val, dict)
            self.assertIn("thread", val)
            self.assertIn("i", val)


class TestStateChangeRecord(unittest.TestCase):
    """StateChangeRecord dataclass tests."""

    def test_record_fields(self):
        record = StateChangeRecord(
            key="test_key",
            value="test_value",
            writer_id="writer-1",
            session_id="session-abc",
            timestamp=1234567890.0,
            seq=42,
        )
        self.assertEqual(record.key, "test_key")
        self.assertEqual(record.value, "test_value")
        self.assertEqual(record.writer_id, "writer-1")
        self.assertEqual(record.session_id, "session-abc")
        self.assertEqual(record.timestamp, 1234567890.0)
        self.assertEqual(record.seq, 42)


class TestSharedStateStoreIntegration(unittest.TestCase):
    """End-to-end integration: sub-agent lifecycle events."""

    def test_subagent_lifecycle_events(self):
        """
        Simulate the full sub-agent lifecycle:
        1. Parent creates SharedStateStore
        2. Sub-agent starts → emits "started"
        3. Sub-agent writes findings → emits "write"
        4. Sub-agent completes → emits "completed"
        5. Parent observes all events
        """
        bus = EventBus()
        store = SharedStateStore(session_id="test-lifecycle")
        store.attach_to_event_bus(bus)

        events = []

        def handler(event):
            events.append((event.type, event.payload))

        bus.subscribe("shared_state.changed", handler)

        # Simulate sub-agent lifecycle (as _emit_shared_state_lifecycle would)
        subagent_id = "subagent-0"

        # Started
        bus.emit_event("shared_state.write", {
            "key": f"_lifecycle/{subagent_id}",
            "value": {"status": "started", "session_id": "child-sess", "timestamp": time.time()},
            "writer_id": subagent_id,
            "timestamp": time.time(),
        })

        # Writes intermediate findings
        bus.emit_event("shared_state.write", {
            "key": "research_results",
            "value": {"phase": 1, "findings": ["a", "b"]},
            "writer_id": subagent_id,
            "timestamp": time.time(),
        })

        # Updates findings
        bus.emit_event("shared_state.write", {
            "key": "research_results",
            "value": {"phase": 2, "findings": ["a", "b", "c"]},
            "writer_id": subagent_id,
            "timestamp": time.time(),
        })

        # Completed
        bus.emit_event("shared_state.write", {
            "key": f"_lifecycle/{subagent_id}",
            "value": {"status": "completed", "session_id": "child-sess", "timestamp": time.time()},
            "writer_id": subagent_id,
            "timestamp": time.time(),
        })

        self.assertEqual(len(events), 4)

        # Check lifecycle states
        lifecycle_events = [(t, p) for t, p in events if p.get("key", "").startswith("_lifecycle/")]
        self.assertEqual(len(lifecycle_events), 2)
        self.assertEqual(lifecycle_events[0][1]["value"]["status"], "started")
        self.assertEqual(lifecycle_events[1][1]["value"]["status"], "completed")

        # Check research results (overwrite pattern)
        research_events = [(t, p) for t, p in events if p.get("key") == "research_results"]
        self.assertEqual(len(research_events), 2)
        self.assertEqual(research_events[0][1]["value"]["phase"], 1)
        self.assertEqual(research_events[0][1]["old_value"], None)
        self.assertEqual(research_events[1][1]["old_value"]["phase"], 1)  # Overwrite
        self.assertEqual(research_events[1][1]["value"]["phase"], 2)

    def test_sibling_subagent_observation(self):
        """
        Two sibling sub-agents run in parallel. Sub-agent 1 finishes first
        and writes a result. Sub-agent 2 can observe this via shared state.
        """
        bus = EventBus()
        store = SharedStateStore(session_id="test-siblings")
        store.attach_to_event_bus(bus)

        # Sub-agent 0 finishes first
        bus.emit_event("shared_state.write", {
            "key": "_lifecycle/subagent-0",
            "value": {"status": "completed", "summary": "Done first"},
            "writer_id": "subagent-0",
            "timestamp": time.time(),
        })

        # Sub-agent 1 observes sub-agent 0's result by reading
        bus.emit_event("shared_state.read", {
            "key": "_lifecycle/subagent-0",
            "reader_id": "subagent-1",
        })

        # Sub-agent 1 writes its own result
        bus.emit_event("shared_state.write", {
            "key": "_lifecycle/subagent-1",
            "value": {"status": "completed", "summary": "Done second"},
            "writer_id": "subagent-1",
            "timestamp": time.time(),
        })

        # Check final store state
        self.assertEqual(store.read("_lifecycle/subagent-0")["status"], "completed")
        self.assertEqual(store.read("_lifecycle/subagent-1")["status"], "completed")


if __name__ == "__main__":
    unittest.main()
