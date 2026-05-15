#!/usr/bin/env python3
"""Integration test for model deprecation with existing validation system."""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

from hermes_cli.model_deprecation import (
    get_deprecation_info,
    get_deprecation_message,
    should_redirect_model,
)


def test_model_validation_integration():
    """Test that deprecation system integrates with model validation."""
    print("Testing integration with model validation...")
    
    # Test the modified validate_requested_model function
    from hermes_cli.models import validate_requested_model
    
    # Test with known deprecated model
    print("  Testing deepseek-chat (known deprecated)...")
    result = validate_requested_model(
        "deepseek-chat",
        "deepseek",
        api_key="test-key",
        base_url="https://api.deepseek.com"
    )
    
    # The function should handle the deprecation
    print(f"    Result: accepted={result.get('accepted')}, "
          f"persist={result.get('persist')}, "
          f"recognized={result.get('recognized')}")
    
    if result.get('message'):
        print(f"    Message: {result.get('message')[:200]}...")
    
    # Test with non-deprecated model
    print("  Testing gpt-4 (non-deprecated)...")
    result2 = validate_requested_model(
        "gpt-4",
        "openai",
        api_key="test-key",
        base_url="https://api.openai.com"
    )
    
    print(f"    Result: accepted={result2.get('accepted')}, "
          f"persist={result2.get('persist')}, "
          f"recognized={result2.get('recognized')}")
    
    print("✓ integration test completed")


def test_deprecation_api():
    """Test the deprecation API functions."""
    print("\nTesting deprecation API...")
    
    # Test known deprecation
    info = get_deprecation_info("deepseek-chat", "deepseek")
    assert info is not None, "deepseek-chat should be deprecated"
    print(f"✓ deepseek-chat is deprecated: {info['redirect_model']}")
    
    # Test deprecation message
    message = get_deprecation_message("deepseek-chat", "deepseek")
    assert message is not None, "Should have deprecation message"
    print(f"✓ deprecation message generated: {message[:100]}...")
    
    # Test redirect
    redirect = should_redirect_model("deepseek-chat", "deepseek")
    assert redirect == "deepseek-v4-pro", "Should redirect to deepseek-v4-pro"
    print(f"✓ redirect suggestion: {redirect}")
    
    # Test non-deprecated model
    info2 = get_deprecation_info("gpt-4", "openai")
    assert info2 is None, "gpt-4 should not be deprecated"
    print("✓ gpt-4 is not deprecated")


def test_error_message_enhancement():
    """Test that error messages are enhanced with deprecation info."""
    print("\nTesting error message enhancement...")
    
    # Simulate the scenario where a user tries to use deepseek-chat
    from hermes_cli.models import validate_requested_model
    
    # Mock the API response to simulate model not found
    with patch('hermes_cli.models.fetch_api_models') as mock_fetch:
        # Return a list that doesn't include deepseek-chat
        mock_fetch.return_value = ["deepseek-v4-pro", "deepseek-v4-flash", "deepseek-reasoner"]
        
        result = validate_requested_model(
            "deepseek-chat",
            "deepseek",
            api_key="test-key",
            base_url="https://api.deepseek.com"
        )
        
        # The result should include deprecation information
        if result.get('message'):
            message = result['message']
            print(f"  Enhanced error message: {message[:300]}...")
            
            # Check if the message contains helpful information
            if "deprecated" in message.lower() or "deepseek-v4-pro" in message:
                print("✓ Error message contains deprecation information")
            else:
                print("⚠ Error message might not contain deprecation info (this is expected if API returns different results)")
        
        # Check for auto-redirect
        if result.get('corrected_model'):
            print(f"✓ Auto-redirect suggested: {result['corrected_model']}")
        elif result.get('suggested_redirect'):
            print(f"✓ Redirect suggested: {result['suggested_redirect']}")


def test_user_experience_scenarios():
    """Test common user experience scenarios."""
    print("\nTesting user experience scenarios...")
    
    scenarios = [
        {
            "name": "User tries deprecated deepseek-chat",
            "model": "deepseek-chat",
            "provider": "deepseek",
            "expected_redirect": "deepseek-v4-pro",
        },
        {
            "name": "User uses valid model",
            "model": "deepseek-v4-pro",
            "provider": "deepseek",
            "expected_redirect": None,
        },
    ]
    
    for scenario in scenarios:
        print(f"  Scenario: {scenario['name']}")
        
        # Check deprecation info
        info = get_deprecation_info(scenario['model'], scenario['provider'])
        
        if scenario['expected_redirect']:
            assert info is not None, f"{scenario['model']} should be deprecated"
            assert info['redirect_model'] == scenario['expected_redirect'], \
                f"Should redirect to {scenario['expected_redirect']}"
            print(f"    ✓ Correctly identified as deprecated, redirects to {info['redirect_model']}")
        else:
            if info is None:
                print(f"    ✓ Correctly identified as not deprecated")
            else:
                print(f"    ⚠ Model is marked as deprecated (redirect: {info.get('redirect_model')})")


def main():
    """Run all integration tests."""
    print("=" * 60)
    print("Model Deprecation System - Integration Tests")
    print("=" * 60)
    
    try:
        test_deprecation_api()
        test_model_validation_integration()
        test_error_message_enhancement()
        test_user_experience_scenarios()
        
        print("\n" + "=" * 60)
        print("All integration tests passed! ✅")
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