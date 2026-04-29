"""
Tests for Hermes Receipt System
"""

import pytest
import tempfile
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
import shutil

from receipt_system_core import ReceiptGenerator, ReceiptConfig, SessionStats


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    # Create schema
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY,
            started_at REAL,
            ended_at REAL,
            message_count INTEGER,
            tool_call_count INTEGER,
            input_tokens INTEGER,
            output_tokens INTEGER,
            cache_read_tokens INTEGER,
            cache_write_tokens INTEGER,
            reasoning_tokens INTEGER,
            estimated_cost_usd REAL,
            actual_cost_usd REAL,
            billing_provider TEXT,
            billing_mode TEXT,
            title TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            role TEXT,
            content TEXT,
            token_count INTEGER,
            timestamp REAL
        )
    ''')
    
    # Insert test data
    cursor.execute('''
        INSERT INTO sessions VALUES (
            'test_session_123',
            1700000000.0,
            1700000600.0,  # 10 minutes later
            10,
            5,
            1500,
            500,
            100,
            50,
            200,
            0.0025,
            NULL,
            'openai',
            'gpt-4',
            'Test Session'
        )
    ''')
    
    conn.commit()
    conn.close()
    
    yield db_path
    
    # Cleanup
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def temp_receipts_dir():
    """Create temporary receipts directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def receipt_generator(temp_db, temp_receipts_dir):
    """Create a ReceiptGenerator instance for testing."""
    config = ReceiptConfig(
        directory=str(temp_receipts_dir),
        enabled=True,
        auto_generate=True
    )
    return ReceiptGenerator(db_path=Path(temp_db), config=config)


class TestReceiptConfig:
    """Test ReceiptConfig class."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = ReceiptConfig()
        
        assert config.enabled is True
        assert config.auto_generate is True
        assert config.directory == "~/.hermes/receipts"
        assert config.retention_days == 30
        assert config.formats == ["json", "txt"]
        assert config.show_cost is True
        assert config.verbosity == "normal"
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = ReceiptConfig(
            enabled=False,
            auto_generate=False,
            directory="/custom/path",
            retention_days=90,
            formats=["json"],
            show_cost=False,
            verbosity="minimal"
        )
        
        assert config.enabled is False
        assert config.auto_generate is False
        assert config.directory == "/custom/path"
        assert config.retention_days == 90
        assert config.formats == ["json"]
        assert config.show_cost is False
        assert config.verbosity == "minimal"


class TestSessionStats:
    """Test SessionStats dataclass."""
    
    def test_session_stats_creation(self):
        """Test creating SessionStats instance."""
        started = datetime(2024, 1, 1, 10, 0, 0)
        ended = datetime(2024, 1, 1, 10, 10, 0)
        
        stats = SessionStats(
            session_id="test_123",
            title="Test Session",
            started_at=started,
            ended_at=ended,
            message_count=10,
            tool_call_count=5,
            input_tokens=1500,
            output_tokens=500,
            cache_read_tokens=100,
            cache_write_tokens=50,
            reasoning_tokens=200,
            estimated_cost_usd=0.0025,
            actual_cost_usd=None,
            provider="openai",
            model="gpt-4"
        )
        
        assert stats.session_id == "test_123"
        assert stats.title == "Test Session"
        assert stats.started_at == started
        assert stats.ended_at == ended
        assert stats.message_count == 10
        assert stats.tool_call_count == 5
        assert stats.input_tokens == 1500
        assert stats.output_tokens == 500
        assert stats.total_tokens == 2000
        assert stats.estimated_cost_usd == 0.0025
        assert stats.provider == "openai"
        assert stats.model == "gpt-4"
    
    def test_session_stats_total_tokens(self):
        """Test total_tokens property."""
        stats = SessionStats(
            session_id="test",
            title="Test",
            started_at=datetime.now(),
            ended_at=None,
            message_count=0,
            tool_call_count=0,
            input_tokens=1000,
            output_tokens=500
        )
        
        assert stats.total_tokens == 1500


class TestReceiptGenerator:
    """Test ReceiptGenerator class."""
    
    def test_get_session_stats(self, receipt_generator):
        """Test retrieving session statistics."""
        stats = receipt_generator.get_session_stats("test_session_123")
        
        assert stats is not None
        assert stats.session_id == "test_session_123"
        assert stats.title == "Test Session"
        assert stats.message_count == 10
        assert stats.tool_call_count == 5
        assert stats.input_tokens == 1500
        assert stats.output_tokens == 500
        assert stats.provider == "openai"
        assert stats.model == "gpt-4"
        assert stats.estimated_cost_usd == 0.0025
    
    def test_get_latest_session_stats(self, receipt_generator):
        """Test retrieving latest session statistics."""
        stats = receipt_generator.get_session_stats()  # No session_id = latest
        
        assert stats is not None
        assert stats.session_id == "test_session_123"
    
    def test_estimate_cost(self, receipt_generator):
        """Test cost estimation."""
        # Test with known provider/model
        cost = receipt_generator.estimate_cost(
            provider="openai",
            model="gpt-4",
            input_tokens=1000,
            output_tokens=500
        )
        
        assert cost is not None
        assert isinstance(cost, float)
        assert cost > 0
        
        # Test with unknown provider (should use fallback)
        cost = receipt_generator.estimate_cost(
            provider="unknown",
            model="unknown",
            input_tokens=1000,
            output_tokens=500
        )
        
        assert cost is not None
        assert isinstance(cost, float)
    
    def test_generate_receipt(self, receipt_generator):
        """Test receipt generation."""
        stats = receipt_generator.get_session_stats("test_session_123")
        receipt = receipt_generator.generate_receipt(stats)
        
        assert receipt is not None
        assert "receipt_version" in receipt
        assert "session" in receipt
        assert "usage" in receipt
        assert "cost" in receipt
        
        session = receipt["session"]
        assert session["id"] == "test_session_123"
        assert session["title"] == "Test Session"
        assert session["duration"] is not None
        
        usage = receipt["usage"]
        assert usage["tokens"]["input"] == 1500
        assert usage["tokens"]["output"] == 500
        assert usage["tokens"]["total"] == 2000
        assert usage["messages"] == 10
        assert usage["tool_calls"] == 5
        
        cost = receipt["cost"]
        assert cost["estimated_usd"] == 0.0025
        assert cost["provider"] == "openai"
        assert cost["model"] == "gpt-4"
    
    def test_save_receipt(self, receipt_generator, temp_receipts_dir):
        """Test saving receipt to files."""
        stats = receipt_generator.get_session_stats("test_session_123")
        receipt = receipt_generator.generate_receipt(stats)
        
        json_path, txt_path = receipt_generator.save_receipt(receipt, "test_session_123")
        
        # Check files exist
        assert json_path.exists()
        assert txt_path.exists()
        
        # Check JSON content
        with open(json_path, 'r', encoding='utf-8') as f:
            saved_data = json.load(f)
        
        assert saved_data["session"]["id"] == "test_session_123"
        
        # Check text content
        with open(txt_path, 'r', encoding='utf-8') as f:
            text_content = f.read()
        
        assert "HERMES AI CONVERSATION RECEIPT" in text_content
        assert "test_session_123" in text_content
    
    def test_generate_for_latest_session(self, receipt_generator, temp_receipts_dir):
        """Test generating receipt for latest session."""
        result = receipt_generator.generate_for_latest_session()
        
        assert result is not None
        json_path, txt_path = result
        
        assert json_path.exists()
        assert txt_path.exists()
        
        # Count files in receipts directory
        json_files = list(temp_receipts_dir.glob("*.json"))
        txt_files = list(temp_receipts_dir.glob("*.txt"))
        
        assert len(json_files) == 1
        assert len(txt_files) == 1
    
    def test_list_receipts(self, receipt_generator, temp_receipts_dir):
        """Test listing receipts."""
        # Generate some receipts first
        for i in range(3):
            stats = SessionStats(
                session_id=f"session_{i}",
                title=f"Test Session {i}",
                started_at=datetime.now(),
                ended_at=datetime.now() + timedelta(minutes=10),
                message_count=i * 5,
                tool_call_count=i * 2,
                input_tokens=1000 + i * 100,
                output_tokens=500 + i * 50,
                estimated_cost_usd=0.001 * (i + 1)
            )
            
            receipt = receipt_generator.generate_receipt(stats)
            receipt_generator.save_receipt(receipt, f"session_{i}")
        
        # List receipts
        receipts = receipt_generator.list_receipts(limit=2)
        
        assert len(receipts) == 2
        assert all("session_id" in r for r in receipts)
        assert all("title" in r for r in receipts)
        assert all("tokens" in r for r in receipts)
    
    def test_cleanup_old_receipts(self, receipt_generator, temp_receipts_dir):
        """Test cleaning up old receipts."""
        # Create some old receipt files
        old_time = datetime.now() - timedelta(days=31)
        
        for i in range(3):
            file_path = temp_receipts_dir / f"old_receipt_{i}.json"
            file_path.touch()
            # Set modification time to 31 days ago
            timestamp = old_time.timestamp()
            os.utime(file_path, (timestamp, timestamp))
        
        # Create some new receipt files
        for i in range(2):
            file_path = temp_receipts_dir / f"new_receipt_{i}.json"
            file_path.touch()
        
        # Clean up receipts older than 30 days
        deleted = receipt_generator.cleanup_old_receipts(days=30)
        
        assert deleted == 3  # Should delete 3 old files
        
        # Check remaining files
        remaining_files = list(temp_receipts_dir.glob("*.json"))
        assert len(remaining_files) == 2  # Should keep 2 new files
    
    def test_format_duration(self, receipt_generator):
        """Test duration formatting."""
        # Test seconds
        assert receipt_generator._format_duration(45) == "45.0s"
        
        # Test minutes
        assert receipt_generator._format_duration(125) == "2.1m"
        
        # Test hours
        assert receipt_generator._format_duration(7500) == "2.1h"
    
    def test_format_text_summary(self, receipt_generator):
        """Test text summary formatting."""
        stats = SessionStats(
            session_id="test_123",
            title="Test Session",
            started_at=datetime(2024, 1, 1, 10, 0, 0),
            ended_at=datetime(2024, 1, 1, 10, 10, 0),
            message_count=10,
            tool_call_count=5,
            input_tokens=1500,
            output_tokens=500,
            estimated_cost_usd=0.0025,
            provider="openai",
            model="gpt-4"
        )
        
        receipt = receipt_generator.generate_receipt(stats)
        text_summary = receipt_generator._format_text_summary(receipt)
        
        assert "HERMES AI CONVERSATION RECEIPT" in text_summary
        assert "Test Session" in text_summary
        assert "test_123" in text_summary
        assert "1,500" in text_summary  # Input tokens
        assert "500" in text_summary    # Output tokens
        assert "2,000" in text_summary  # Total tokens
        assert "0.0025" in text_summary  # Cost
        assert "openai" in text_summary
        assert "gpt-4" in text_summary


class TestReceiptSystemIntegration:
    """Integration tests for the receipt system."""
    
    def test_end_to_end_flow(self, temp_db, temp_receipts_dir):
        """Test complete end-to-end flow."""
        config = ReceiptConfig(directory=str(temp_receipts_dir))
        generator = ReceiptGenerator(db_path=Path(temp_db), config=config)
        
        # 1. Get session stats
        stats = generator.get_session_stats("test_session_123")
        assert stats is not None
        
        # 2. Generate receipt
        receipt = generator.generate_receipt(stats)
        assert receipt is not None
        
        # 3. Save receipt
        json_path, txt_path = generator.save_receipt(receipt, "test_session_123")
        assert json_path.exists()
        assert txt_path.exists()
        
        # 4. List receipts
        receipts = generator.list_receipts()
        assert len(receipts) == 1
        assert receipts[0]["session_id"] == "test_session_123"
        
        # 5. Cleanup (should not delete new receipt)
        deleted = generator.cleanup_old_receipts(days=1)
        assert deleted == 0
        
        # Files should still exist
        assert json_path.exists()
        assert txt_path.exists()


# Import os for utime
import os

if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])