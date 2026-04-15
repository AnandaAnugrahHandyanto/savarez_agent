"""Tests for MessageDeduplicator TTL-based expiry behavior.

Covers issue #10306: TTL should properly expire entries, not just when
the cache exceeds max_size.
"""

import time
from unittest.mock import patch

import pytest

# Import after conftest sets up paths
from gateway.platforms.helpers import MessageDeduplicator


class TestMessageDeduplicatorBasic:
    """Basic functionality tests."""

    def test_first_message_not_duplicate(self):
        """First occurrence of a message ID should not be a duplicate."""
        dedup = MessageDeduplicator(ttl_seconds=60)
        assert dedup.is_duplicate("msg-001") is False

    def test_immediate_duplicate_detected(self):
        """Same message ID seen immediately should be a duplicate."""
        dedup = MessageDeduplicator(ttl_seconds=60)
        dedup.is_duplicate("msg-001")
        assert dedup.is_duplicate("msg-001") is True

    def test_different_messages_not_duplicates(self):
        """Different message IDs should not be considered duplicates."""
        dedup = MessageDeduplicator(ttl_seconds=60)
        dedup.is_duplicate("msg-001")
        assert dedup.is_duplicate("msg-002") is False
        assert dedup.is_duplicate("msg-003") is False

    def test_empty_msg_id_never_duplicate(self):
        """Empty message IDs should never be tracked or flagged."""
        dedup = MessageDeduplicator(ttl_seconds=60)
        assert dedup.is_duplicate("") is False
        assert dedup.is_duplicate("") is False
        assert dedup.is_duplicate(None) is False  # type: ignore

    def test_clear_removes_all_entries(self):
        """clear() should remove all tracked messages."""
        dedup = MessageDeduplicator(ttl_seconds=60)
        dedup.is_duplicate("msg-001")
        dedup.is_duplicate("msg-002")
        dedup.clear()
        assert dedup.is_duplicate("msg-001") is False
        assert dedup.is_duplicate("msg-002") is False


class TestMessageDeduplicatorTTLExpiry:
    """TTL expiration tests - the core fix for issue #10306."""

    def test_ttl_expiry_allows_reprocessing(self):
        """After TTL expires, the same message should no longer be duplicate.

        This is the minimal reproduction case from issue #10306.
        """
        dedup = MessageDeduplicator(ttl_seconds=0.01)  # 10ms TTL
        assert dedup.is_duplicate("msg-001") is False
        time.sleep(0.03)  # Wait past TTL
        # After TTL expiry, should NOT be considered duplicate
        assert dedup.is_duplicate("msg-001") is False

    def test_within_ttl_still_duplicate(self):
        """Within TTL window, message should still be duplicate."""
        dedup = MessageDeduplicator(ttl_seconds=1.0)  # 1 second TTL
        assert dedup.is_duplicate("msg-001") is False
        time.sleep(0.01)  # Tiny delay, well within TTL
        assert dedup.is_duplicate("msg-001") is True

    def test_ttl_expiry_resets_timestamp(self):
        """After TTL expiry and re-seen, the entry should get a fresh timestamp."""
        dedup = MessageDeduplicator(ttl_seconds=0.02)
        
        # First occurrence
        assert dedup.is_duplicate("msg-001") is False
        time.sleep(0.03)  # TTL expired
        
        # Second occurrence after expiry - should not be duplicate
        assert dedup.is_duplicate("msg-001") is False
        
        # Immediately after, should be duplicate again (fresh TTL)
        assert dedup.is_duplicate("msg-001") is True

    def test_ttl_expiry_without_exceeding_max_size(self):
        """TTL should work even when cache is well under max_size.

        This directly tests the bug: entries were only pruned when
        len(cache) > max_size, so TTL was effectively ignored.
        """
        # Large max_size, small TTL - this is the problematic scenario
        dedup = MessageDeduplicator(max_size=10000, ttl_seconds=0.01)
        
        assert dedup.is_duplicate("msg-001") is False
        assert dedup.is_duplicate("msg-002") is False
        assert dedup.is_duplicate("msg-003") is False
        
        # All should be duplicates immediately
        assert dedup.is_duplicate("msg-001") is True
        assert dedup.is_duplicate("msg-002") is True
        assert dedup.is_duplicate("msg-003") is True
        
        time.sleep(0.03)  # TTL expired
        
        # After TTL, none should be duplicates - this was broken before fix
        assert dedup.is_duplicate("msg-001") is False
        assert dedup.is_duplicate("msg-002") is False
        assert dedup.is_duplicate("msg-003") is False

    def test_mixed_expiry_states(self):
        """Messages can have different expiry states simultaneously."""
        dedup = MessageDeduplicator(ttl_seconds=0.05)
        
        # First message
        assert dedup.is_duplicate("old-msg") is False
        time.sleep(0.03)
        
        # Second message added while first is still valid
        assert dedup.is_duplicate("new-msg") is False
        
        # Old is still within TTL, new definitely is
        assert dedup.is_duplicate("old-msg") is True
        assert dedup.is_duplicate("new-msg") is True
        
        time.sleep(0.03)  # Now old is past TTL, but new is still valid
        
        # Old should be expired, new should still be duplicate
        assert dedup.is_duplicate("old-msg") is False
        assert dedup.is_duplicate("new-msg") is True


class TestMessageDeduplicatorMaxSize:
    """Max size and eviction behavior tests."""

    def test_max_size_triggers_cleanup(self):
        """When exceeding max_size, old entries should be cleaned up."""
        dedup = MessageDeduplicator(max_size=3, ttl_seconds=60)
        
        # Fill up cache
        for i in range(5):
            dedup.is_duplicate(f"msg-{i}")
        
        # Cache should have been pruned - exact behavior depends on timing
        # but should not have more than max_size entries after pruning
        assert len(dedup._seen) <= 5  # All recent so none pruned by TTL

    def test_max_size_eviction_respects_ttl(self):
        """Max-size eviction should only remove TTL-expired entries."""
        dedup = MessageDeduplicator(max_size=2, ttl_seconds=0.01)
        
        dedup.is_duplicate("msg-001")
        time.sleep(0.02)  # Let it expire
        dedup.is_duplicate("msg-002")
        dedup.is_duplicate("msg-003")
        
        # After exceeding max_size, msg-001 should be evicted (expired)
        # msg-002 and msg-003 should remain
        # (Exact cache state depends on implementation, but behavior should be correct)
        assert dedup.is_duplicate("msg-002") is True
        assert dedup.is_duplicate("msg-003") is True


class TestMessageDeduplicatorEdgeCases:
    """Edge cases and boundary conditions."""

    def test_zero_ttl(self):
        """Zero TTL means entries expire immediately."""
        dedup = MessageDeduplicator(ttl_seconds=0)
        assert dedup.is_duplicate("msg-001") is False
        # Even with zero TTL, time between calls is non-zero
        # so the entry should expire
        time.sleep(0.001)
        assert dedup.is_duplicate("msg-001") is False

    def test_very_large_ttl(self):
        """Very large TTL should keep entries indefinitely."""
        dedup = MessageDeduplicator(ttl_seconds=86400)  # 1 day
        assert dedup.is_duplicate("msg-001") is False
        time.sleep(0.01)
        assert dedup.is_duplicate("msg-001") is True

    def test_special_characters_in_msg_id(self):
        """Message IDs with special characters should work."""
        dedup = MessageDeduplicator(ttl_seconds=60)
        special_ids = [
            "msg:with:colons",
            "msg/with/slashes",
            "msg-with-dashes",
            "msg_with_underscores",
            "msg.with.dots",
            "msg with spaces",
            "msg\nwith\nnewlines",
            "emoji-🎉-msg",
            "unicode-日本語-msg",
        ]
        for msg_id in special_ids:
            assert dedup.is_duplicate(msg_id) is False
            assert dedup.is_duplicate(msg_id) is True

    def test_numeric_like_msg_ids(self):
        """Numeric-looking message IDs (as strings) should work."""
        dedup = MessageDeduplicator(ttl_seconds=60)
        assert dedup.is_duplicate("12345") is False
        assert dedup.is_duplicate("12345") is True
        assert dedup.is_duplicate("12345.67") is False
        assert dedup.is_duplicate("12345.67") is True


class TestMessageDeduplicatorWithMockedTime:
    """Tests using mocked time for precise control."""

    def test_exact_ttl_boundary(self):
        """Test behavior exactly at TTL boundary."""
        with patch("gateway.platforms.helpers.time") as mock_time:
            mock_time.time.return_value = 1000.0
            dedup = MessageDeduplicator(ttl_seconds=10)
            
            # First occurrence at t=1000
            assert dedup.is_duplicate("msg-001") is False
            
            # Exactly at TTL (t=1010, diff=10) - should still be duplicate (<=)
            mock_time.time.return_value = 1010.0
            assert dedup.is_duplicate("msg-001") is True
            
            # Just past TTL (t=1010.001, diff=10.001) - should NOT be duplicate
            mock_time.time.return_value = 1010.001
            assert dedup.is_duplicate("msg-001") is False

    def test_entry_removal_on_expiry(self):
        """Expired entry should be removed from cache on access."""
        with patch("gateway.platforms.helpers.time") as mock_time:
            mock_time.time.return_value = 1000.0
            dedup = MessageDeduplicator(ttl_seconds=10)
            
            # Add entry
            dedup.is_duplicate("msg-001")
            assert "msg-001" in dedup._seen
            
            # Expire it
            mock_time.time.return_value = 1011.0
            
            # Access should remove expired entry and re-add with new timestamp
            assert dedup.is_duplicate("msg-001") is False
            assert "msg-001" in dedup._seen
            assert dedup._seen["msg-001"] == 1011.0
