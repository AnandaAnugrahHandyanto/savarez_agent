#!/usr/bin/env python3
"""Basic test script for model deprecation functionality."""

import sys
import tempfile
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

from hermes_cli.model_deprecation import (
    ModelDeprecationRecord,
    ModelDeprecationDB,
    get_deprecation_info,
    get_deprecation_message,
    should_redirect_model,
    get_all_deprecations,
)


def test_known_deprecations():
    """Test that known deprecations work."""
    print("Testing known deprecations...")
    
    # Test deepseek-chat
    info = get_deprecation_info("deepseek-chat", "deepseek")
    assert info is not None, "deepseek-chat should be a known deprecation"
    assert info["source"] == "known", "Should be marked as known deprecation"
    assert info["redirect_model"] == "deepseek-v4-pro", "Should redirect to deepseek-v4-pro"
    print("✓ deepseek-chat deprecation info correct")
    
    # Test deprecation message
    message = get_deprecation_message("deepseek-chat", "deepseek")
    assert message is not None, "Should have deprecation message"
    assert "deprecated" in message.lower(), "Message should mention deprecation"
    assert "deepseek-v4-pro" in message, "Message should suggest redirect model"
    print("✓ deprecation message format correct")
    
    # Test redirect
    redirect = should_redirect_model("deepseek-chat", "deepseek")
    assert redirect == "deepseek-v4-pro", "Should redirect to deepseek-v4-pro"
    print("✓ model redirect correct")


def test_database_operations():
    """Test database CRUD operations."""
    print("\nTesting database operations...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_deprecations.json"
        db = ModelDeprecationDB(db_path)
        
        # Create record
        record = ModelDeprecationRecord(
            model_id="test-model",
            provider="test-provider",
            first_detected=None,  # Will be set automatically
            last_detected=None,   # Will be set automatically
            failure_count=1,
        )
        # Set the datetime fields
        from datetime import datetime
        now = datetime.now()
        record.first_detected = now
        record.last_detected = now
        
        db.update_record(record)
        print("✓ record created")
        
        # Read record
        retrieved = db.get_record("test-model", "test-provider")
        assert retrieved is not None, "Should retrieve the record"
        assert retrieved.model_id == "test-model", "Model ID should match"
        assert retrieved.failure_count == 1, "Failure count should match"
        print("✓ record retrieved")
        
        # Update record
        retrieved.failure_count = 2
        db.update_record(retrieved)
        updated = db.get_record("test-model", "test-provider")
        assert updated.failure_count == 2, "Failure count should be updated"
        print("✓ record updated")
        
        # Delete record
        db.delete_record("test-model", "test-provider")
        deleted = db.get_record("test-model", "test-provider")
        assert deleted is None, "Record should be deleted"
        print("✓ record deleted")


def test_serialization():
    """Test record serialization."""
    print("\nTesting serialization...")
    
    from datetime import datetime
    
    record = ModelDeprecationRecord(
        model_id="test-model",
        provider="test-provider",
        first_detected=datetime.now(),
        last_detected=datetime.now(),
        failure_count=1,
        status="pending",
        suggested_alternatives=["alt-1", "alt-2"],
        redirect_model="alt-1",
        error_message="Test error",
    )
    
    # Test to_dict
    data = record.to_dict()
    assert data["model_id"] == "test-model"
    assert data["failure_count"] == 1
    assert len(data["suggested_alternatives"]) == 2
    print("✓ serialization to dict works")
    
    # Test from_dict
    restored = ModelDeprecationRecord.from_dict(data)
    assert restored.model_id == record.model_id
    assert restored.failure_count == record.failure_count
    assert restored.suggested_alternatives == record.suggested_alternatives
    print("✓ deserialization from dict works")


def test_get_all_deprecations():
    """Test getting all deprecations."""
    print("\nTesting get_all_deprecations...")
    
    all_deps = get_all_deprecations()
    assert "known" in all_deps, "Should have known deprecations"
    assert "detected" in all_deps, "Should have detected deprecations section"
    assert len(all_deps["known"]) > 0, "Should have at least one known deprecation"
    print("✓ all deprecations structure correct")


def test_non_deprecated_model():
    """Test that non-deprecated models return None."""
    print("\nTesting non-deprecated models...")
    
    info = get_deprecation_info("gpt-4", "openai")
    assert info is None, "gpt-4 should not be deprecated"
    print("✓ non-deprecated model returns None")
    
    message = get_deprecation_message("gpt-4", "openai")
    assert message is None, "gpt-4 should not have deprecation message"
    print("✓ non-deprecated model has no message")
    
    redirect = should_redirect_model("gpt-4", "openai")
    assert redirect is None, "gpt-4 should not have redirect"
    print("✓ non-deprecated model has no redirect")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Model Deprecation System - Basic Tests")
    print("=" * 60)
    
    try:
        test_known_deprecations()
        test_database_operations()
        test_serialization()
        test_get_all_deprecations()
        test_non_deprecated_model()
        
        print("\n" + "=" * 60)
        print("All tests passed! ✅")
        print("=" * 60)
        return 0
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())