"""Example test file demonstrating TDD best practices for hermes-agent.

This file serves as a reference for writing tests. It demonstrates:
- Proper test structure and naming
- Use of fixtures
- Mocking external dependencies
- Testing edge cases
- Async test patterns
"""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path


# ============================================================================
# Example 1: Simple unit test with clear naming
# ============================================================================

class TestCalculatorAdd:
    """Tests for the calculator add function."""
    
    def test_add_positive_numbers_returns_sum(self):
        """Adding two positive numbers returns their sum."""
        result = 2 + 3
        assert result == 5
    
    def test_add_negative_numbers_returns_sum(self):
        """Adding negative numbers works correctly."""
        result = -2 + -3
        assert result == -5
    
    def test_add_zero_returns_other_number(self):
        """Adding zero returns the other number unchanged."""
        result = 5 + 0
        assert result == 5


# ============================================================================
# Example 2: Using fixtures for common setup
# ============================================================================

@pytest.fixture
def sample_config():
    """Return a sample configuration dict."""
    return {
        "model": "test-model",
        "timeout": 30,
        "retries": 3,
    }


@pytest.fixture
def mock_external_api():
    """Return a mocked external API client."""
    mock = MagicMock()
    mock.get.return_value = {"status": "ok", "data": [1, 2, 3]}
    return mock


class TestWithFixtures:
    """Demonstrates fixture usage."""
    
    def test_config_has_required_keys(self, sample_config):
        """Config should have all required keys."""
        assert "model" in sample_config
        assert "timeout" in sample_config
    
    def test_api_client_returns_data(self, mock_external_api):
        """API client should return data from get()."""
        result = mock_external_api.get("/endpoint")
        assert result["status"] == "ok"
        assert len(result["data"]) == 3


# ============================================================================
# Example 3: Mocking external dependencies
# ============================================================================

class TestWithMocking:
    """Demonstrates mocking patterns."""
    
    def test_file_read_with_mocked_open(self, tmp_path):
        """Test file reading without actual file system."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")
        
        content = test_file.read_text()
        assert content == "hello world"
    
    def test_api_call_with_mocked_http(self):
        """Test HTTP calls without making real requests."""
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.read.return_value = b'{"result": "success"}'
            mock_urlopen.return_value = mock_response
            
            # Simulate an HTTP call (using urllib for the example)
            import urllib.request
            response = urllib.request.urlopen("https://example.com/api")
            
            assert response.status == 200
            import json
            assert json.loads(response.read())["result"] == "success"
            mock_urlopen.assert_called_once()


# ============================================================================
# Example 4: Testing edge cases and error conditions
# ============================================================================

class TestEdgeCases:
    """Demonstrates edge case testing."""
    
    def test_empty_string_returns_empty(self):
        """Empty string input should return empty output."""
        result = "".upper()
        assert result == ""
    
    def test_none_input_raises_error(self):
        """None input should raise TypeError."""
        with pytest.raises(TypeError):
            len(None)
    
    def test_large_input_handles_correctly(self):
        """Large inputs should be handled without errors."""
        large_list = list(range(10000))
        result = sum(large_list)
        assert result == sum(range(10000))


# ============================================================================
# Example 5: Parametrized tests for multiple scenarios
# ============================================================================

@pytest.mark.parametrize("input_val,expected", [
    ("hello", "HELLO"),
    ("Hello", "HELLO"),
    ("HELLO", "HELLO"),
    ("", ""),
    ("123", "123"),
])
def test_uppercase_conversion(input_val, expected):
    """Uppercase conversion works for various inputs."""
    assert input_val.upper() == expected


@pytest.mark.parametrize("a,b,expected", [
    (1, 2, 3),
    (-1, 1, 0),
    (0, 0, 0),
    (100, -50, 50),
])
def test_addition_parametrized(a, b, expected):
    """Addition works for various number pairs."""
    assert a + b == expected


# ============================================================================
# Example 6: Async tests
# ============================================================================

import asyncio


@pytest.mark.asyncio
async def test_async_function():
    """Test async function with pytest-asyncio."""
    async def fetch_data():
        await asyncio.sleep(0.001)  # Simulate async work
        return {"data": "test"}
    
    result = await fetch_data()
    assert result["data"] == "test"


@pytest.mark.asyncio
async def test_async_with_mock():
    """Test async function with mocking."""
    mock_async = MagicMock()
    mock_async.return_value = asyncio.Future()
    mock_async.return_value.set_result("mocked")
    
    result = await mock_async()
    assert result == "mocked"


# ============================================================================
# Example 7: Using the HERMES_HOME isolation fixture
# ============================================================================

class TestHermesHomeIsolation:
    """Demonstrates HERMES_HOME fixture (automatic from conftest.py)."""
    
    def test_writes_to_hermes_home(self):
        """Tests can safely write to HERMES_HOME without affecting real config."""
        import os
        from pathlib import Path
        
        hermes_home = Path(os.environ["HERMES_HOME"])
        test_file = hermes_home / "test_file.txt"
        test_file.write_text("test content")
        
        # File exists in temp directory, not ~/.hermes/
        assert test_file.exists()
        assert test_file.read_text() == "test content"


# ============================================================================
# Example 8: Testing with markers
# ============================================================================

@pytest.mark.slow
class TestSlowOperations:
    """Tests that take longer to run. Marked with 'slow' marker."""
    
    def test_slow_computation(self):
        """This test might be slow."""
        result = sum(range(1000000))
        assert result > 0


@pytest.mark.security
def test_security_sensitive_operation():
    """Security-related test marked with 'security' marker."""
    # Test security-related functionality
    password = "secret"
    hashed = password + "_hashed"  # Simplified example
    assert "_hashed" in hashed


# ============================================================================
# Example 9: Class-based test organization
# ============================================================================

class TestUserAuthentication:
    """Tests for user authentication functionality.
    
    Group related tests in a class for better organization.
    Each test method should test one specific behavior.
    """
    
    @pytest.fixture
    def auth_service(self):
        """Create an auth service for tests."""
        return {"users": {}, "sessions": {}}
    
    def test_register_new_user_creates_account(self, auth_service):
        """Registering a new user creates an account."""
        auth_service["users"]["alice"] = {"password": "hash123"}
        assert "alice" in auth_service["users"]
    
    def test_login_valid_credentials_succeeds(self, auth_service):
        """Login with valid credentials should succeed."""
        auth_service["users"]["bob"] = {"password": "hash456"}
        user = auth_service["users"].get("bob")
        assert user is not None
        assert user["password"] == "hash456"
    
    def test_login_invalid_credentials_fails(self, auth_service):
        """Login with invalid credentials should fail."""
        user = auth_service["users"].get("nonexistent")
        assert user is None


# ============================================================================
# Example 10: Best practices summary
# ============================================================================

"""
Summary of TDD best practices demonstrated in this file:

1. Test Naming:
   - Use descriptive names: test_<what>_<condition>_<expected_result>
   - Example: test_add_positive_numbers_returns_sum

2. Test Structure:
   - Arrange: Set up test data and mocks
   - Act: Execute the code under test
   - Assert: Verify the expected outcome

3. Fixtures:
   - Use @pytest.fixture for common setup
   - Use tmp_path for temporary files
   - Use monkeypatch for environment changes

4. Mocking:
   - Mock external dependencies (APIs, filesystem, etc.)
   - Use unittest.mock.patch as a context manager
   - Verify mock calls with assert_called_once_with()

5. Edge Cases:
   - Test empty inputs, None values, large inputs
   - Test error conditions with pytest.raises()

6. Parametrization:
   - Use @pytest.mark.parametrize for multiple similar test cases
   - Reduces code duplication

7. Async:
   - Use @pytest.mark.asyncio for async tests
   - Mock async functions with asyncio.Future()

8. Organization:
   - Group related tests in classes
   - Use markers (@pytest.mark.slow, @pytest.mark.security)
   - Add docstrings explaining what the test verifies

9. Isolation:
   - Tests should be independent (no shared state)
   - Use the autouse fixtures from conftest.py
   - Clean up resources after tests

10. Coverage:
    - Aim for high coverage on new code
    - Focus on testing behavior, not implementation details
"""
