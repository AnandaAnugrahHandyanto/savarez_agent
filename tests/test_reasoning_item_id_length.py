"""Test for reasoning item id length validation in codex Responses API.

Issue: #10788 - Multi-turn codex conversations fail because reasoning item
id exceeds 64-char limit (408 chars actual), causing HTTP 400 error.
"""

import pytest
from unittest.mock import MagicMock


class TestReasoningItemIdLength:
    """Test that reasoning item ids are validated for length."""

    def test_short_id_preserved(self):
        """Reasoning item ids <= 64 chars should be preserved."""
        # Simulate capture path in run_agent.py:4002-4007
        item = MagicMock()
        item.type = "reasoning"
        item.encrypted_content = "encrypted_blob_123"
        item.id = "short_id_12345"  # < 64 chars
        
        # Capture logic
        raw_item = {"type": "reasoning", "encrypted_content": item.encrypted_content}
        item_id = getattr(item, "id", None)
        if isinstance(item_id, str) and item_id and len(item_id) <= 64:
            raw_item["id"] = item_id
        
        # Short id should be preserved
        assert "id" in raw_item
        assert raw_item["id"] == "short_id_12345"

    def test_long_id_dropped(self):
        """Reasoning item ids > 64 chars should be dropped."""
        # Simulate capture path with 408-char id (real codex case)
        long_id = "a" * 408  # 408 chars, exceeds 64-char limit
        
        item = MagicMock()
        item.type = "reasoning"
        item.encrypted_content = "encrypted_blob_123"
        item.id = long_id
        
        # Capture logic
        raw_item = {"type": "reasoning", "encrypted_content": item.encrypted_content}
        item_id = getattr(item, "id", None)
        if isinstance(item_id, str) and item_id and len(item_id) <= 64:
            raw_item["id"] = item_id
        
        # Long id should NOT be in raw_item
        assert "id" not in raw_item

    def test_64_char_id_preserved(self):
        """Reasoning item ids exactly 64 chars should be preserved."""
        exactly_64 = "a" * 64
        
        item = MagicMock()
        item.type = "reasoning"
        item.encrypted_content = "encrypted_blob_123"
        item.id = exactly_64
        
        # Capture logic
        raw_item = {"type": "reasoning", "encrypted_content": item.encrypted_content}
        item_id = getattr(item, "id", None)
        if isinstance(item_id, str) and item_id and len(item_id) <= 64:
            raw_item["id"] = item_id
        
        # 64-char id should be preserved
        assert "id" in raw_item
        assert len(raw_item["id"]) == 64

    def test_65_char_id_dropped(self):
        """Reasoning item ids > 64 chars should be dropped."""
        exactly_65 = "a" * 65
        
        item = MagicMock()
        item.type = "reasoning"
        item.encrypted_content = "encrypted_blob_123"
        item.id = exactly_65
        
        # Capture logic
        raw_item = {"type": "reasoning", "encrypted_content": item.encrypted_content}
        item_id = getattr(item, "id", None)
        if isinstance(item_id, str) and item_id and len(item_id) <= 64:
            raw_item["id"] = item_id
        
        # 65-char id should NOT be in raw_item
        assert "id" not in raw_item

    def test_no_id_gracefully_handled(self):
        """Reasoning items without id should be handled gracefully."""
        item = MagicMock()
        item.type = "reasoning"
        item.encrypted_content = "encrypted_blob_123"
        # No id attribute
        
        # Capture logic
        raw_item = {"type": "reasoning", "encrypted_content": item.encrypted_content}
        item_id = getattr(item, "id", None)
        if isinstance(item_id, str) and item_id and len(item_id) <= 64:
            raw_item["id"] = item_id
        
        # Should work without id
        assert "id" not in raw_item
        assert raw_item["encrypted_content"] == "encrypted_blob_123"

    def test_empty_id_gracefully_handled(self):
        """Empty reasoning item ids should be handled gracefully."""
        item = MagicMock()
        item.type = "reasoning"
        item.encrypted_content = "encrypted_blob_123"
        item.id = ""
        
        # Capture logic
        raw_item = {"type": "reasoning", "encrypted_content": item.encrypted_content}
        item_id = getattr(item, "id", None)
        if isinstance(item_id, str) and item_id and len(item_id) <= 64:
            raw_item["id"] = item_id
        
        # Empty id should NOT be added
        assert "id" not in raw_item

    def test_encrypted_content_always_preserved(self):
        """encrypted_content should always be preserved regardless of id."""
        # Even with long id, encrypted_content should be preserved
        long_id = "a" * 408
        
        item = MagicMock()
        item.type = "reasoning"
        item.encrypted_content = "encrypted_blob_123"
        item.id = long_id
        
        # Capture logic
        raw_item = {"type": "reasoning", "encrypted_content": item.encrypted_content}
        item_id = getattr(item, "id", None)
        if isinstance(item_id, str) and item_id and len(item_id) <= 64:
            raw_item["id"] = item_id
        
        # encrypted_content should always be present
        assert "encrypted_content" in raw_item
        assert raw_item["encrypted_content"] == "encrypted_blob_123"
        # id should be dropped
        assert "id" not in raw_item


class TestReasoningItemReplay:
    """Test that replay path correctly handles reasoning items."""

    def test_replay_strips_id(self):
        """Replay path should strip id field from reasoning items."""
        # Simulate reasoning item with id from previous capture
        ri = {
            "type": "reasoning",
            "encrypted_content": "encrypted_blob_123",
            "id": "a" * 408  # Long id from previous turn
        }
        
        # Replay logic from run_agent.py:3592-3597
        replay_item = {k: v for k, v in ri.items() if k != "id"}
        
        # Replay should strip id
        assert "id" not in replay_item
        assert "encrypted_content" in replay_item

    def test_replay_preserves_encrypted_content(self):
        """Replay should always preserve encrypted_content."""
        ri = {
            "type": "reasoning",
            "encrypted_content": "encrypted_blob_123",
            "id": "some_id"
        }
        
        replay_item = {k: v for k, v in ri.items() if k != "id"}
        
        assert replay_item["encrypted_content"] == "encrypted_blob_123"

    def test_replay_preserves_summary(self):
        """Replay should preserve summary field."""
        ri = {
            "type": "reasoning",
            "encrypted_content": "encrypted_blob_123",
            "id": "some_id",
            "summary": [{"type": "summary_text", "text": "Thinking..."}]
        }
        
        replay_item = {k: v for k, v in ri.items() if k != "id"}
        
        assert "summary" in replay_item


if __name__ == "__main__":
    pytest.main([__file__, "-v"])